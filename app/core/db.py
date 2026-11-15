import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import APIError
from app.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine | None:
    global _engine, _session_factory
    url = get_settings().database_url.strip()
    if not url:
        return None
    if _engine is None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_db():
    if _session_factory is None:
        get_engine()
    if _session_factory is None:
        raise APIError(503, "DATABASE_UNAVAILABLE", "数据库未配置")
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def database_is_ready() -> bool:
    engine = get_engine()
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def prepare_database() -> None:
    settings = get_settings()
    if settings.testing or settings.app_env != "dev":
        return
    engine = get_engine()
    if engine is None:
        return
    Base.metadata.create_all(engine)
    # 老的开发库按模型补齐缺的列（只加列，不改不删）；新库 create_all 已经完整。
    if engine.dialect.name == "sqlite":
        _ensure_remaining_columns(engine)
        _relax_stale_not_null(engine)
    from app.seed import seed_if_empty

    seed_if_empty()


def _relax_stale_not_null(engine: Engine) -> None:
    """旧开发库里还是 NOT NULL、模型已改成可空的列：SQLite 改不了约束，只能按模型重建整张表。

    例：moderation_case.content_id 旧库必填，导致举报用户 / 房间 / 留言时插入失败。
    线上库由 alembic 迁移处理，不走这里。
    """
    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        for table_name, table in Base.metadata.tables.items():
            if table_name not in tables:
                continue
            info = conn.execute(text(f'PRAGMA table_info("{table_name}")')).all()  # (cid, name, type, notnull, default, pk)
            stale = [row[1] for row in info if row[3] and row[1] in table.columns and table.columns[row[1]].nullable]
            if not stale:
                continue
            shared = [row[1] for row in info if row[1] in table.columns]
            names = ", ".join(f'"{name}"' for name in shared)
            rows = conn.execute(text(f'SELECT {names} FROM "{table_name}"')).all()
            conn.execute(text(f'DROP TABLE "{table_name}"'))
            table.create(conn)
            if rows:
                marks = ", ".join(f":{name}" for name in shared)
                conn.execute(
                    text(f'INSERT INTO "{table_name}" ({names}) VALUES ({marks})'),
                    [dict(zip(shared, row)) for row in rows],
                )


def _sqlite_literal(value: object) -> str | None:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def _default_literal(column: sa.Column) -> str | None:
    default = column.default
    if default is not None:
        arg = getattr(default, "arg", None)
        if arg is not None and not callable(arg):
            literal = _sqlite_literal(arg)
            if literal is not None:
                return literal
    if isinstance(column.type, sa.Boolean):
        return "0"
    if isinstance(column.type, (sa.Integer, sa.Float, sa.Numeric)):
        return "0"
    if isinstance(column.type, (sa.String, sa.Text)):
        return "''"
    # 日期等没有安全兜底值的列保持 NULL，由应用侧按需处理旧数据。
    return None


def _ensure_remaining_columns(engine: Engine) -> None:
    """补齐模型已声明、但旧开发库仍缺失的列，避免重启新代码后全表查询 500。

    只做 ADD COLUMN，不改类型、不删列；不追加 NOT NULL / UNIQUE / FK 约束
    （SQLite 的 ADD COLUMN 也不支持），写入侧的约束仍由 SQLAlchemy 模型保证。
    旧行通过 DEFAULT 得到可读的兜底值；精确手工迁移保留在上面的分支里。
    """
    with engine.begin() as conn:
        tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        for table_name, table in Base.metadata.tables.items():
            if table_name not in tables:
                continue
            existing = {
                row[1] for row in conn.execute(text(f'PRAGMA table_info("{table_name}")'))
            }
            for column in table.columns:
                if column.name in existing or column.primary_key:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                literal = _default_literal(column)
                suffix = f" DEFAULT {literal}" if literal is not None else ""
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}{suffix}')
                )

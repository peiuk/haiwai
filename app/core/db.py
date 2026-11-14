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
    _ensure_sqlite_columns(engine)
    from app.seed import seed_if_empty

    seed_if_empty()


def _ensure_sqlite_columns(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "app_user" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(app_user)"))}
            if "phone" not in columns:
                conn.execute(text("ALTER TABLE app_user ADD COLUMN phone VARCHAR(32)"))
            if "handle" not in columns:
                conn.execute(text("ALTER TABLE app_user ADD COLUMN handle VARCHAR(20)"))
            if "avatar_tone" not in columns:
                conn.execute(text("ALTER TABLE app_user ADD COLUMN avatar_tone VARCHAR(1) NOT NULL DEFAULT 'a'"))
            if "city_label" not in columns:
                conn.execute(text("ALTER TABLE app_user ADD COLUMN city_label VARCHAR(12)"))
        if "moderation_case" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(moderation_case)"))}
            if "reported_user_id" not in columns:
                conn.execute(text("ALTER TABLE moderation_case ADD COLUMN reported_user_id VARCHAR(36)"))
            if "reported_channel_id" not in columns:
                conn.execute(text("ALTER TABLE moderation_case ADD COLUMN reported_channel_id VARCHAR(36)"))
            if "reported_comment_id" not in columns:
                conn.execute(text("ALTER TABLE moderation_case ADD COLUMN reported_comment_id VARCHAR(36)"))
            if "detail" not in columns:
                conn.execute(text("ALTER TABLE moderation_case ADD COLUMN detail VARCHAR(300) NOT NULL DEFAULT ''"))
        if "content" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(content)"))}
            if "city_topic" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN city_topic VARCHAR(12)"))
            if "keyword_source" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN keyword_source VARCHAR(16)"))
            if "repost_of_id" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN repost_of_id VARCHAR(36)"))
            if "video_key" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN video_key VARCHAR(64)"))
            if "rights_confirmed" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN rights_confirmed BOOLEAN NOT NULL DEFAULT 0"))
            if "author_id" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN author_id VARCHAR(36)"))
            if "body" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN body TEXT"))
            if "content_hash" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN content_hash VARCHAR(64)"))
            if "ai_status" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN ai_status VARCHAR(16) DEFAULT 'pending'"))
            if "event_cluster_id" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN event_cluster_id VARCHAR(36)"))
            if "view_count" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0"))
            if "image_keys_json" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN image_keys_json TEXT NOT NULL DEFAULT '[]'"))
        if "channel" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(channel)"))}
            if "parent_channel_id" not in columns:
                conn.execute(text("ALTER TABLE channel ADD COLUMN parent_channel_id VARCHAR(36)"))
            if "review_status" not in columns:
                conn.execute(text("ALTER TABLE channel ADD COLUMN review_status VARCHAR(16) DEFAULT 'approved'"))
            if "room_type" not in columns:
                conn.execute(text("ALTER TABLE channel ADD COLUMN room_type VARCHAR(16) NOT NULL DEFAULT 'general'"))
        if "channel_item" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(channel_item)"))}
            if "sort_key" not in columns:
                conn.execute(text("ALTER TABLE channel_item ADD COLUMN sort_key VARCHAR(16) NOT NULL DEFAULT ''"))
            if "rights_confirmed" not in columns:
                conn.execute(text("ALTER TABLE channel_item ADD COLUMN rights_confirmed BOOLEAN NOT NULL DEFAULT 0"))
            if "season" not in columns:
                conn.execute(text("ALTER TABLE channel_item ADD COLUMN season INTEGER"))
            if "episode" not in columns:
                conn.execute(text("ALTER TABLE channel_item ADD COLUMN episode INTEGER"))
            if "year" not in columns:
                conn.execute(text("ALTER TABLE channel_item ADD COLUMN year INTEGER"))
        if "user_item_progress" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(user_item_progress)"))}
            if "watch_mark" not in columns:
                conn.execute(text("ALTER TABLE user_item_progress ADD COLUMN watch_mark VARCHAR(16) NOT NULL DEFAULT ''"))
        if "channel_subscription" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(channel_subscription)"))}
            if "last_read_at" not in columns:
                conn.execute(text("ALTER TABLE channel_subscription ADD COLUMN last_read_at DATETIME"))
            if "unread_count" not in columns:
                conn.execute(text("ALTER TABLE channel_subscription ADD COLUMN unread_count INTEGER NOT NULL DEFAULT 0"))
        if "content" in tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(content)"))}
            if "title_hant" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN title_hant VARCHAR(200)"))
            if "summary_hant" not in columns:
                conn.execute(text("ALTER TABLE content ADD COLUMN summary_hant VARCHAR(500)"))
    _ensure_remaining_columns(engine)


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

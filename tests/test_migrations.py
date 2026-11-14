"""开发库按模型建表（create_all），生产库按 alembic 迁移建表：两边必须得到同样的表和列。"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.ddl.sqlite import SQLiteImpl
from sqlalchemy import create_engine, inspect

from app.models import Base

ROOT = Path(__file__).resolve().parent.parent


def test_migrations_produce_same_tables_and_columns_as_models(tmp_path, monkeypatch):
    # SQLite 不支持 ALTER 加约束（add_column 带外键时会报错）；本测试只比较表和列，约束交给 Postgres 上的真实迁移。
    monkeypatch.setattr(SQLiteImpl, "add_constraint", lambda self, const, **kw: None)
    engine = create_engine(f"sqlite:///{tmp_path / 'migrated.db'}")
    config = Config()  # 不读 alembic.ini：避免改写测试的日志配置，也不碰 .env 里的数据库
    config.set_main_option("script_location", str(ROOT / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    inspector = inspect(engine)
    migrated = {
        (table, column["name"])
        for table in inspector.get_table_names()
        if table != "alembic_version"
        for column in inspector.get_columns(table)
    }
    modeled = {(table.name, column.name) for table in Base.metadata.sorted_tables for column in table.columns}
    engine.dispose()

    assert sorted(modeled - migrated) == [], "模型里有、迁移里没有：新增字段后忘了写迁移"
    assert sorted(migrated - modeled) == [], "迁移里有、模型里没有：迁移与模型不一致"

import os

# 设置里默认是 prod；测试依赖开发环境行为（验证码、审核接口），必须在导入 app 之前显式声明。
os.environ["APP_ENV"] = "dev"
os.environ["TESTING"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth as auth_api  # noqa: E402
from app.api.v1.moderation import require_moderator  # noqa: E402
from app.core import security  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402

# 测试不读开发者本机的 .env：那里的临时开关（如 REQUIRE_PHONE_VERIFICATION=false）会让测试结果因人而异。
Settings.model_config["env_file"] = None
get_settings.cache_clear()
from app.core.db import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402

# 生产用 60 万轮哈希；测试里注册成百上千次，调低只为提速，密码格式与校验逻辑不变。
security.PBKDF2_ITERATIONS = 1_000


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    # 大多数用例只关心审核之后发生什么，不想每次先建管理员：这里让任何登录用户都能审。
    # 权限本身由 test_admin.py / test_security_hardening.py 去掉这条替换后单独测。
    app.dependency_overrides[require_moderator] = auth_api.current_user
    with TestClient(app) as test_client:
        test_client.session_factory = session_factory
        yield test_client


@pytest.fixture(autouse=True)
def _skip_media_compress(monkeypatch):
    """大多数用例上传的是几个字节的假图片，只测权限和流程；真正的转码由 test_media.py 单独测。"""
    from app.api.v1 import uploads

    monkeypatch.setattr(uploads, "compress", lambda source, content_type: (source, content_type))

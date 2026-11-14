import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.channels import router as channels_router
from app.api.v1.contents import router as contents_router
from app.api.v1.embed import router as embed_router
from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.listings import router as listings_router
from app.api.v1.me import router as me_router
from app.api.v1.messages import router as messages_router
from app.api.v1.moderation import router as moderation_router
from app.api.v1.room_social import router as room_social_router
from app.api.v1.search import router as search_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.users import router as users_router
from app.core.config import DEFAULT_SECRET_KEY, get_settings
from app.core.db import prepare_database
from app.core.errors import APIError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    prepare_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    # 非开发环境还在用写在代码里的默认密钥：任何人都能伪造任意用户的登录令牌，直接拒绝启动。
    if settings.app_env != "dev" and settings.app_secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError("APP_SECRET_KEY 还是默认值：非 dev 环境必须设置自己的随机密钥")
    app = FastAPI(title="海外圈", version="0.1.0", lifespan=lifespan)
    origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        return await call_next(request)

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(channels_router, prefix="/api/v1")
    app.include_router(contents_router, prefix="/api/v1")
    app.include_router(me_router, prefix="/api/v1")
    app.include_router(moderation_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(listings_router, prefix="/api/v1")
    app.include_router(messages_router, prefix="/api/v1")
    app.include_router(room_social_router, prefix="/api/v1")
    app.include_router(uploads_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(embed_router, prefix="/api/v1")
    return app


app = create_app()

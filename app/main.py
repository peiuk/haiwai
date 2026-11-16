import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_channels import router as admin_channels_router
from app.api.v1.admin_ops import router as admin_ops_router
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
from app.core.audit import client_ip, note_server_error, request_meta
from app.core.config import DEFAULT_SECRET_KEY, get_settings
from app.core.db import prepare_database
from app.core.errors import APIError, validation_message


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
        # 记下来源，写审计日志时用（见 core/audit.py）
        request_meta.set((client_ip(request), request.headers.get("user-agent", "")[:200] or None))
        try:
            response = await call_next(request)
        except Exception:
            note_server_error()
            raise
        if response.status_code >= 500:
            note_server_error()
        # 接口数据因人而异：没有自己声明缓存策略的 /api 响应一律不许 CDN / 浏览器缓存，免得串号
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        # 浏览器严格按声明的类型处理（不去「猜」内容）：上传的图片即使夹带网页代码也不会被当网页执行
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

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

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 前端只读 message：不转的话，校验器里写好的中文提示（「必填项不能为空」等）用户一句都看不到
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_FAILED",
                "message": validation_message(exc.errors()),
                "request_id": getattr(request.state, "request_id", ""),
                "detail": jsonable_encoder(exc.errors()),
            },
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(channels_router, prefix="/api/v1")
    app.include_router(contents_router, prefix="/api/v1")
    app.include_router(me_router, prefix="/api/v1")
    app.include_router(moderation_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(admin_channels_router, prefix="/api/v1")
    app.include_router(admin_ops_router, prefix="/api/v1")
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

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.db import database_is_ready

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
def readyz() -> JSONResponse:
    if database_is_ready():
        return JSONResponse(content={"status": "ok", "checks": {"database": "up"}})
    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "checks": {"database": "down"}},
    )

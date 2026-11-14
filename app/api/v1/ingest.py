from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.ingest import ingest_fixture
from app.models import User

router = APIRouter(prefix="/admin/ingest", tags=["ingest"])


@router.post("/fixture")
def fetch_fixture(
    _: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    if get_settings().app_env != "dev":
        raise APIError(404, "NOT_FOUND", "不存在")
    return ingest_fixture(session)

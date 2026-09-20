from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


@router.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )

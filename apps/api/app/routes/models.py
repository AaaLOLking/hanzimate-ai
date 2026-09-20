from fastapi import APIRouter, Request
from sqlalchemy import select

from app.auth import CurrentUser, SessionDependency
from app.model_usage import build_usage_summary
from app.models import ModelRegistry
from app.schemas import ModelOutput, ModelUsageOutput

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("", response_model=list[ModelOutput])
def list_models(session: SessionDependency, _: CurrentUser) -> list[ModelRegistry]:
    return list(
        session.scalars(
            select(ModelRegistry)
            .where(ModelRegistry.enabled.is_(True))
            .order_by(ModelRegistry.provider, ModelRegistry.model)
        )
    )


@router.get("/usage", response_model=ModelUsageOutput)
def get_model_usage(
    request: Request,
    session: SessionDependency,
    user: CurrentUser,
) -> dict:
    return build_usage_summary(session, user.id, request.app.state.settings)

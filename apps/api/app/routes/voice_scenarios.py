from fastapi import APIRouter

from app.auth import CurrentUser
from app.scenarios import CONVERSATION_SCENARIOS
from app.schemas import ConversationScenarioOutput

router = APIRouter(prefix="/api/v1/voice/scenarios", tags=["voice"])


@router.get("", response_model=list[ConversationScenarioOutput])
def list_conversation_scenarios(_user: CurrentUser) -> tuple[dict[str, object], ...]:
    return CONVERSATION_SCENARIOS

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelRegistry, Workspace

WORKSPACE_RECOMMENDATIONS = {
    "daily_life": ("食堂点餐", "在食堂使用数量表达完成一次自然点餐"),
    "campus": ("校园问路", "询问教学楼位置，并确认路线"),
    "hsk_exam": ("HSK 快速诊断", "用四道小题确定第一周的训练重点"),
    "internship": ("实习自我介绍", "用 60 秒介绍自己的专业和经历"),
    "social": ("认识新同学", "自然地自我介绍并提出两个问题"),
}


def create_recommended_workspace(session: Session, user_id: str, priority: str) -> Workspace:
    title, objective = WORKSPACE_RECOMMENDATIONS.get(
        priority, WORKSPACE_RECOMMENDATIONS["daily_life"]
    )
    workspace = Workspace(
        user_id=user_id,
        kind="conversation",
        title=title,
        state={"objective": objective, "source": "onboarding", "progress": 0},
    )
    session.add(workspace)
    return workspace


def seed_model_registry(
    session: Session,
    default_deepseek_model: str,
    deepseek_enabled: bool,
    qwen_realtime_model: str,
    qwen_enabled: bool,
) -> None:
    deepseek = session.scalar(select(ModelRegistry).where(ModelRegistry.provider == "deepseek"))
    if deepseek is None:
        deepseek = ModelRegistry(provider="deepseek", model=default_deepseek_model)
        session.add(deepseek)
    deepseek.model = default_deepseek_model
    deepseek.display_name = "DeepSeek · 默认文本模型"
    deepseek.capabilities = ["chat", "structured_output", "lesson_tutoring"]
    deepseek.enabled = deepseek_enabled

    local = session.scalar(select(ModelRegistry).where(ModelRegistry.provider == "local"))
    if local is None:
        local = ModelRegistry(provider="local", model="rule-summary-v1")
        session.add(local)
    local.model = "rule-summary-v1"
    local.display_name = "本机教学规则"
    local.capabilities = ["chat", "structured_output", "lesson_tutoring"]
    local.enabled = True

    qwen = session.scalar(select(ModelRegistry).where(ModelRegistry.provider == "qwen"))
    if qwen is None:
        qwen = ModelRegistry(provider="qwen", model=qwen_realtime_model)
        session.add(qwen)
    qwen.model = qwen_realtime_model
    qwen.display_name = "Qwen3.5 Omni Flash · 实时语音"
    qwen.capabilities = ["realtime_voice", "transcription", "vad", "barge_in", "webrtc"]
    qwen.enabled = qwen_enabled
    session.commit()

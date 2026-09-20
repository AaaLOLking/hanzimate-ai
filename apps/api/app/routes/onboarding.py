from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.auth import CurrentUser, SessionDependency
from app.models import Consent, LearnerMission, LearnerProfile, Workspace, utc_now
from app.schemas import OnboardingInput, OnboardingOutput
from app.services import create_recommended_workspace

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


def build_onboarding_output(session: SessionDependency, user: CurrentUser) -> OnboardingOutput:
    consent = session.scalars(
        select(Consent)
        .where(Consent.user_id == user.id)
        .order_by(Consent.granted_at.desc())
        .limit(1)
    ).first()
    mission = session.scalars(
        select(LearnerMission)
        .where(LearnerMission.user_id == user.id)
        .order_by(LearnerMission.updated_at.desc())
        .limit(1)
    ).first()
    profile = session.get(LearnerProfile, user.id)
    workspace = session.scalars(
        select(Workspace)
        .where(Workspace.user_id == user.id, Workspace.state["source"].as_string() == "onboarding")
        .order_by(Workspace.created_at.desc())
        .limit(1)
    ).first()
    return OnboardingOutput(
        complete=bool(consent and mission and profile),
        user=user,
        consent=consent,
        mission=mission,
        profile=profile,
        recommended_workspace=workspace,
    )


@router.get("", response_model=OnboardingOutput)
def get_onboarding(session: SessionDependency, user: CurrentUser) -> OnboardingOutput:
    return build_onboarding_output(session, user)


@router.put("", response_model=OnboardingOutput)
def save_onboarding(
    payload: OnboardingInput, session: SessionDependency, user: CurrentUser
) -> OnboardingOutput:
    if payload.mission.deadline and payload.mission.deadline < utc_now().date():
        raise HTTPException(status_code=422, detail="Mission deadline cannot be in the past")

    user.display_name = payload.display_name
    user.locale = payload.locale

    consent = Consent(
        user_id=user.id,
        policy_version=payload.consent.policy_version,
        privacy_acknowledged=payload.consent.privacy_acknowledged,
        learning_memory=payload.consent.learning_memory,
        audio_retention=payload.consent.audio_retention,
    )
    session.add(consent)

    mission = session.scalars(
        select(LearnerMission)
        .where(LearnerMission.user_id == user.id)
        .order_by(LearnerMission.updated_at.desc())
        .limit(1)
    ).first()
    if mission is None:
        mission = LearnerMission(user_id=user.id, **payload.mission.model_dump())
        session.add(mission)
    else:
        for field, value in payload.mission.model_dump().items():
            setattr(mission, field, value)

    profile = session.get(LearnerProfile, user.id)
    preferences = {
        "correction_mode": payload.profile.correction_mode,
        "speech_speed": payload.profile.speech_speed,
        "show_pinyin": payload.profile.show_pinyin,
        "english_first": payload.profile.english_first,
        "review_interval_days": payload.profile.review_interval_days,
    }
    profile_values = {
        "native_language": payload.profile.native_language,
        "support_language": payload.profile.support_language,
        "estimated_hsk_band": payload.profile.current_hsk_band,
        "skill_estimates": payload.profile.self_assessment,
        "preferences": preferences,
    }
    if profile is None:
        profile = LearnerProfile(user_id=user.id, **profile_values)
        session.add(profile)
    else:
        for field, value in profile_values.items():
            setattr(profile, field, value)
        profile.projection_version += 1

    workspace = session.scalars(
        select(Workspace)
        .where(Workspace.user_id == user.id, Workspace.state["source"].as_string() == "onboarding")
        .limit(1)
    ).first()
    if workspace is None:
        workspace = create_recommended_workspace(session, user.id, payload.mission.priorities[0])

    session.commit()
    return build_onboarding_output(session, user)

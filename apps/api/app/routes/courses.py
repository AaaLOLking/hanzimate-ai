from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.auth import CurrentUser, SessionDependency
from app.model_usage import (
    add_model_run,
    elapsed_ms,
    estimate_tokens,
    model_budget_block_reason,
    start_timer,
)
from app.models import (
    Course,
    CourseVersion,
    ErrorCluster,
    LearnerMission,
    LearnerProfile,
    LearningEvidence,
    LessonMessage,
    LessonProgress,
    LessonVersion,
    Workspace,
    utc_now,
)
from app.providers.lesson_tutor import (
    LessonTutorError,
    LessonTutorRequest,
    LocalLessonTutorProvider,
    build_lesson_tutor_provider,
)
from app.schemas import (
    CourseOutput,
    LessonAttemptInput,
    LessonAttemptOutput,
    LessonDetailOutput,
    LessonQuestionInput,
    LessonQuestionOutput,
)

router = APIRouter(prefix="/api/v1", tags=["courses"])

ACTIVITY_BY_STEP: dict[int, Literal["guided", "retrieval", "transfer", "completed"]] = {
    0: "guided",
    1: "retrieval",
    2: "transfer",
    3: "completed",
}
CONTENT_ACTIVITY_KEYS = {
    "guided": "guided_practice",
    "retrieval": "retrieval_practice",
    "transfer": "transfer_task",
}


@router.get("/courses", response_model=list[CourseOutput])
def list_courses(
    database_session: SessionDependency,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    published_versions = list(
        database_session.scalars(
            select(CourseVersion)
            .join(Course)
            .where(Course.status == "published", CourseVersion.status == "published")
            .order_by(CourseVersion.course_id, CourseVersion.version.desc())
        )
    )
    latest_by_course: dict[str, CourseVersion] = {}
    for version in published_versions:
        latest_by_course.setdefault(version.course_id, version)
    versions = list(latest_by_course.values())
    lesson_ids = [lesson.id for version in versions for lesson in version.lessons]
    progress_by_lesson = {
        progress.lesson_version_id: progress
        for progress in database_session.scalars(
            select(LessonProgress).where(
                LessonProgress.user_id == user.id,
                LessonProgress.lesson_version_id.in_(lesson_ids),
            )
        )
    }
    return [
        {
            "id": version.course_id,
            "slug": version.course.slug,
            "version": version.version,
            "title": version.title,
            "description": version.description,
            "framework": version.framework,
            "level": version.level,
            "lessons": [
                {
                    "id": lesson.id,
                    "slug": lesson.slug,
                    "position": lesson.position,
                    "title": lesson.title,
                    "track": lesson.content.get("track", "daily-life"),
                    "level": lesson.level,
                    "objective": lesson.objective,
                    "estimated_minutes": lesson.estimated_minutes,
                    "targets": lesson.targets,
                    "progress": progress_by_lesson.get(lesson.id),
                }
                for lesson in version.lessons
                if lesson.status == "published"
            ],
        }
        for version in versions
    ]


@router.get("/lessons/{lesson_id}", response_model=LessonDetailOutput)
def get_lesson(
    lesson_id: str,
    database_session: SessionDependency,
    user: CurrentUser,
) -> dict[str, Any]:
    lesson = _get_published_lesson(database_session, lesson_id)
    progress = _get_progress(database_session, user.id, lesson.id)
    return _lesson_detail(database_session, user.id, lesson, progress)


@router.post("/lessons/{lesson_id}/start", response_model=LessonDetailOutput, status_code=201)
def start_lesson(
    lesson_id: str,
    database_session: SessionDependency,
    user: CurrentUser,
) -> dict[str, Any]:
    lesson = _get_published_lesson(database_session, lesson_id)
    progress = _get_progress(database_session, user.id, lesson.id)
    if progress is None:
        workspace = Workspace(
            user_id=user.id,
            kind="lesson",
            title=lesson.title,
            status="active",
            state={
                "course_id": lesson.course_version.course_id,
                "lesson_version_id": lesson.id,
                "objective": lesson.objective,
                "current_step": 0,
                "progress": 5,
            },
        )
        database_session.add(workspace)
        database_session.flush()
        progress = LessonProgress(
            user_id=user.id,
            lesson_version_id=lesson.id,
            workspace_id=workspace.id,
            status="in_progress",
        )
        database_session.add(progress)
        database_session.commit()
        database_session.refresh(progress)
    else:
        progress.workspace.last_opened_at = utc_now()
        database_session.commit()
    return _lesson_detail(database_session, user.id, lesson, progress)


@router.post("/lessons/{lesson_id}/ask", response_model=LessonQuestionOutput, status_code=201)
def ask_lesson_tutor(
    lesson_id: str,
    payload: LessonQuestionInput,
    request: Request,
    database_session: SessionDependency,
    user: CurrentUser,
) -> dict[str, LessonMessage]:
    lesson = _get_published_lesson(database_session, lesson_id)
    progress = _require_progress(database_session, user.id, lesson.id)
    context_pack = _build_context_pack(database_session, user.id, lesson, progress)
    settings = request.app.state.settings
    provider = build_lesson_tutor_provider(settings)
    tutor_request = LessonTutorRequest(
        question=payload.question,
        context_pack=context_pack,
        current_step=progress.current_step,
    )
    request_tokens = estimate_tokens(
        {
            "question": payload.question,
            "context_pack": context_pack,
            "current_step": progress.current_step,
        }
    )
    fallback_from: str | None = None
    block_reason = model_budget_block_reason(
        database_session,
        user.id,
        provider.provider,
        settings,
        reserved_input_tokens=request_tokens,
        reserved_output_tokens=500,
    )
    if block_reason:
        add_model_run(
            database_session,
            settings,
            user_id=user.id,
            task="lesson_tutor",
            provider=provider.provider,
            model=provider.model,
            status="blocked",
            latency_ms=0,
            input_tokens=request_tokens,
            output_tokens=0,
            error_code=block_reason,
        )
        fallback_from = provider.provider
        provider = LocalLessonTutorProvider()

    started_at = start_timer()
    try:
        answer = provider.answer(tutor_request)
    except LessonTutorError:
        add_model_run(
            database_session,
            settings,
            user_id=user.id,
            task="lesson_tutor",
            provider=provider.provider,
            model=provider.model,
            status="failed",
            latency_ms=elapsed_ms(started_at),
            input_tokens=request_tokens,
            output_tokens=0,
            error_code="provider_error",
        )
        fallback_from = provider.provider
        provider = LocalLessonTutorProvider()
        started_at = start_timer()
        answer = provider.answer(tutor_request)

    add_model_run(
        database_session,
        settings,
        user_id=user.id,
        task="lesson_tutor",
        provider=provider.provider,
        model=provider.model,
        status="succeeded",
        latency_ms=elapsed_ms(started_at),
        input_tokens=request_tokens,
        output_tokens=estimate_tokens(answer),
        fallback_from=fallback_from,
    )

    user_message = LessonMessage(
        lesson_progress_id=progress.id,
        user_id=user.id,
        role="user",
        content=payload.question,
        provider="learner",
        model="user-input",
        citations=[],
    )
    assistant_message = LessonMessage(
        lesson_progress_id=progress.id,
        user_id=user.id,
        role="assistant",
        content=answer,
        provider=provider.provider,
        model=provider.model,
        citations=lesson.sources,
    )
    database_session.add_all([user_message, assistant_message])
    progress.updated_at = utc_now()
    database_session.commit()
    database_session.refresh(user_message)
    database_session.refresh(assistant_message)
    return {"user_message": user_message, "assistant_message": assistant_message}


@router.post("/lessons/{lesson_id}/attempts", response_model=LessonAttemptOutput, status_code=201)
def submit_lesson_attempt(
    lesson_id: str,
    payload: LessonAttemptInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> dict[str, Any]:
    lesson = _get_published_lesson(database_session, lesson_id)
    progress = _require_progress(database_session, user.id, lesson.id)
    expected_activity = ACTIVITY_BY_STEP.get(progress.current_step, "completed")
    if expected_activity == "completed":
        raise HTTPException(status_code=409, detail="Lesson is already completed")
    if payload.activity != expected_activity:
        raise HTTPException(
            status_code=409,
            detail=f"Complete the {expected_activity} activity first",
        )

    rule = lesson.assessment_config[payload.activity]
    passed, score, missing_targets = _grade_response(payload.response, rule)
    feedback = rule["success_feedback"] if passed else rule["retry_feedback"]
    content_key = CONTENT_ACTIVITY_KEYS[payload.activity]
    evidence = LearningEvidence(
        user_id=user.id,
        lesson_progress_id=progress.id,
        lesson_version_id=lesson.id,
        evidence_type=payload.activity,
        response=payload.response,
        passed=passed,
        score=score,
        feedback=feedback,
        answer_rule=lesson.content[content_key]["answer_rule"],
        skill_version=lesson.skill_version,
    )
    database_session.add(evidence)
    was_completed = progress.status == "completed"
    progress.attempt_count += 1
    progress.best_score = max(progress.best_score, score)
    if passed:
        progress.current_step += 1
    if progress.current_step >= 3:
        progress.current_step = 3
        progress.status = "completed"
        progress.completed_at = utc_now()
    progress.updated_at = utc_now()

    workspace = progress.workspace
    workspace.status = "completed" if progress.status == "completed" else "active"
    workspace.state = {
        **workspace.state,
        "current_step": progress.current_step,
        "progress": [5, 40, 72, 100][progress.current_step],
        "last_evidence_type": payload.activity,
        "last_attempt_passed": passed,
    }
    workspace.last_opened_at = utc_now()
    if progress.status == "completed" and not was_completed:
        _record_completed_lesson(database_session, user.id)
    database_session.commit()
    database_session.refresh(progress)
    database_session.refresh(evidence)
    return {
        "passed": passed,
        "score": score,
        "feedback": feedback,
        "missing_targets": missing_targets,
        "next_activity": ACTIVITY_BY_STEP[progress.current_step],
        "progress": progress,
        "evidence": evidence,
    }


def _get_published_lesson(database_session: SessionDependency, lesson_id: str) -> LessonVersion:
    lesson = database_session.scalar(
        select(LessonVersion).where(
            LessonVersion.id == lesson_id,
            LessonVersion.status == "published",
        )
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


def _get_progress(
    database_session: SessionDependency, user_id: str, lesson_id: str
) -> LessonProgress | None:
    return database_session.scalar(
        select(LessonProgress).where(
            LessonProgress.user_id == user_id,
            LessonProgress.lesson_version_id == lesson_id,
        )
    )


def _require_progress(
    database_session: SessionDependency, user_id: str, lesson_id: str
) -> LessonProgress:
    progress = _get_progress(database_session, user_id, lesson_id)
    if progress is None:
        raise HTTPException(status_code=409, detail="Start the lesson first")
    return progress


def _lesson_detail(
    database_session: SessionDependency,
    user_id: str,
    lesson: LessonVersion,
    progress: LessonProgress | None,
) -> dict[str, Any]:
    return {
        "id": lesson.id,
        "course_id": lesson.course_version.course_id,
        "course_title": lesson.course_version.title,
        "course_version": lesson.course_version.version,
        "slug": lesson.slug,
        "version": lesson.version,
        "position": lesson.position,
        "title": lesson.title,
        "framework": lesson.framework,
        "level": lesson.level,
        "objective": lesson.objective,
        "estimated_minutes": lesson.estimated_minutes,
        "targets": lesson.targets,
        "sources": lesson.sources,
        "content": _public_content(lesson.content),
        "context_pack": _build_context_pack(database_session, user_id, lesson, progress),
        "skill_version": lesson.skill_version,
        "progress": progress,
        "messages": list(progress.messages) if progress else [],
    }


def _public_content(content: dict[str, Any]) -> dict[str, Any]:
    public = {**content}
    for key in CONTENT_ACTIVITY_KEYS.values():
        activity = dict(public[key])
        activity.pop("answer_rule", None)
        public[key] = activity
    return public


def _build_context_pack(
    database_session: SessionDependency,
    user_id: str,
    lesson: LessonVersion,
    progress: LessonProgress | None,
) -> dict[str, Any]:
    mission = database_session.scalar(
        select(LearnerMission)
        .where(LearnerMission.user_id == user_id)
        .order_by(LearnerMission.created_at.desc())
    )
    profile = database_session.get(LearnerProfile, user_id)
    clusters = list(
        database_session.scalars(
            select(ErrorCluster)
            .where(ErrorCluster.user_id == user_id, ErrorCluster.status == "active")
            .order_by(ErrorCluster.last_seen_at.desc())
            .limit(20)
        )
    )
    relevant_errors = [
        {
            "canonical_key": cluster.canonical_key,
            "subtype": cluster.subtype,
            "explanation": cluster.explanation,
            "corrected_example": cluster.corrected_example,
            "occurrence_count": cluster.occurrence_count,
        }
        for cluster in clusters
        if _cluster_matches_lesson(cluster, lesson.targets)
    ][:3]
    recent_messages = (
        [
            {"role": message.role, "content": message.content}
            for message in progress.messages[-6:]
        ]
        if progress
        else []
    )
    return {
        "mission": (
            {
                "why": mission.why,
                "success_looks_like": mission.success_looks_like[:2],
                "constraints": mission.constraints[:2],
            }
            if mission
            else None
        ),
        "learner_level": profile.estimated_hsk_band if profile else "not_sure",
        "support_language": profile.support_language if profile else "English",
        "lesson": {
            "id": lesson.id,
            "version": lesson.version,
            "objective": lesson.objective,
            "targets": lesson.targets,
            "explanation": lesson.content["explanation"],
            "examples": lesson.content["examples"],
        },
        "confirmed_relevant_errors": relevant_errors,
        "recent_lesson_messages": recent_messages,
        "citations": lesson.sources,
        "teaching_policy": (
            "每次只解决当前课目标；先让学习者产出，再给一个最高价值修改并要求重试；"
            "检索和迁移任务作答前不泄露完整答案。"
        ),
        "skill_version": lesson.skill_version,
    }


def _cluster_matches_lesson(cluster: ErrorCluster, targets: list[str]) -> bool:
    searchable = " ".join(
        [cluster.canonical_key, cluster.error_type, cluster.subtype, cluster.explanation]
    ).lower()
    aliases = {
        "量词": ["measure-word", "量词"],
        "把字句": ["ba-construction", "把字句"],
        "结果补语": ["result-complement", "结果补语"],
    }
    for target in targets:
        terms = [target.lower(), *aliases.get(target, [])]
        if any(term.lower() in searchable for term in terms):
            return True
    return False


def _grade_response(response: str, rule: dict[str, Any]) -> tuple[bool, float, list[str]]:
    normalized = _normalize_answer(response)
    required_all = list(rule.get("required_all", []))
    required_any = list(rule.get("required_any", []))
    missing = [term for term in required_all if _normalize_answer(term) not in normalized]
    any_matched = not required_any or any(
        _normalize_answer(term) in normalized for term in required_any
    )
    if not any_matched:
        missing.append(f"任一：{' / '.join(required_any)}")
    total_checks = len(required_all) + (1 if required_any else 0)
    passed_checks = total_checks - len(missing)
    score = round(max(0, passed_checks) / max(1, total_checks), 2)
    return not missing, score, missing


def _normalize_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[\s，。！？、,.!?；;：:]", "", normalized)


def _record_completed_lesson(database_session: SessionDependency, user_id: str) -> None:
    profile = database_session.get(LearnerProfile, user_id)
    if profile is None:
        return
    completed = int(profile.skill_estimates.get("completed_lessons", 0)) + 1
    profile.skill_estimates = {**profile.skill_estimates, "completed_lessons": completed}
    profile.projection_version += 1

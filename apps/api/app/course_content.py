from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, CourseVersion, LessonVersion


class ActivityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    answer_rule: str = Field(min_length=1)
    feedback_rule: str = Field(min_length=1)


class ExampleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chinese: str = Field(min_length=1)
    pinyin: str | None = None
    support_text: str | None = None
    note: str = Field(min_length=1)


class LessonContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    version: int = Field(ge=1)
    title: str
    track: Literal["daily-life", "hsk"] | None = None
    framework: str
    level: str
    objective: str
    prerequisites: list[str] = Field(default_factory=list)
    estimated_minutes: int = Field(ge=5, le=20)
    targets: list[str] = Field(min_length=1)
    sources: list[str] = Field(min_length=1)
    explanation: str
    examples: list[ExampleDefinition] = Field(min_length=2)
    guided_practice: ActivityDefinition
    retrieval_practice: ActivityDefinition
    transfer_task: ActivityDefinition
    completion_evidence: str
    next_review: str | None = None


class AssessmentRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_all: list[str] = Field(default_factory=list)
    required_any: list[str] = Field(default_factory=list)
    success_feedback: str
    retry_feedback: str


class LessonAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guided: AssessmentRule
    retrieval: AssessmentRule
    transfer: AssessmentRule


class CatalogLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int = Field(ge=1)
    lesson: LessonContract
    assessment_config: LessonAssessment


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    publisher: str
    url: str


class CourseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version_id: str
    slug: str
    version: int = Field(ge=1)
    title: str
    description: str
    framework: str
    level: str
    skill_version: str = "0.1.0"


class CourseCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course: CourseDefinition
    source_catalog: list[SourceDefinition]
    lessons: list[CatalogLesson] = Field(min_length=1)


@lru_cache(maxsize=1)
def load_course_catalogs() -> tuple[CourseCatalog, ...]:
    catalog_paths = sorted((Path(__file__).parent / "content").glob("course_catalog*.json"))
    if not catalog_paths:
        raise RuntimeError("No published course catalogs found")
    catalogs = tuple(
        CourseCatalog.model_validate_json(path.read_text(encoding="utf-8"))
        for path in catalog_paths
    )
    version_ids = [catalog.course.version_id for catalog in catalogs]
    if len(version_ids) != len(set(version_ids)):
        raise RuntimeError("Course version IDs must be unique across published catalogs")
    lesson_ids = [item.lesson.id for catalog in catalogs for item in catalog.lessons]
    if len(lesson_ids) != len(set(lesson_ids)):
        raise RuntimeError("Lesson version IDs must be unique across published catalogs")
    return tuple(sorted(catalogs, key=lambda catalog: catalog.course.version))


def load_course_catalog() -> CourseCatalog:
    """Return the latest published catalog for authoring and test callers."""

    return load_course_catalogs()[-1]


def seed_course_catalog(session: Session) -> None:
    for catalog in load_course_catalogs():
        _seed_catalog(session, catalog)
    session.commit()


def _seed_catalog(session: Session, catalog: CourseCatalog) -> None:
    course_data = catalog.course
    course = session.get(Course, course_data.id)
    if course is None:
        course = Course(
            id=course_data.id,
            slug=course_data.slug,
            status="published",
        )
        session.add(course)
        session.flush()
    elif course.slug != course_data.slug:
        raise RuntimeError("Published course identity changed; create a new course instead")

    course_version = session.get(CourseVersion, course_data.version_id)
    if course_version is None:
        course_version = CourseVersion(
            id=course_data.version_id,
            course_id=course.id,
            version=course_data.version,
            title=course_data.title,
            description=course_data.description,
            framework=course_data.framework,
            level=course_data.level,
            status="published",
            source_metadata={
                "catalog": (
                    "course_catalog.json"
                    if course_data.version == 1
                    else f"course_catalog_v{course_data.version}.json"
                ),
                "skill_version": course_data.skill_version,
            },
        )
        session.add(course_version)
        session.flush()
    else:
        published_identity = (
            course_version.course_id,
            course_version.version,
            course_version.title,
            course_version.description,
            course_version.framework,
            course_version.level,
        )
        catalog_identity = (
            course.id,
            course_data.version,
            course_data.title,
            course_data.description,
            course_data.framework,
            course_data.level,
        )
        if published_identity != catalog_identity:
            raise RuntimeError(
                "Published course version changed; create a new immutable version instead"
            )

        published_lesson_ids = set(
            session.scalars(
                select(LessonVersion.id).where(
                    LessonVersion.course_version_id == course_version.id
                )
            )
        )
        catalog_lesson_ids = {item.lesson.id for item in catalog.lessons}
        if published_lesson_ids != catalog_lesson_ids:
            raise RuntimeError(
                "Published course lesson set changed; create a new immutable version instead"
            )

    sources_by_id = {source.id: source.model_dump() for source in catalog.source_catalog}
    for item in catalog.lessons:
        contract = item.lesson.model_dump(exclude_none=True)
        assessment = item.assessment_config.model_dump()
        content_hash = _content_hash(contract, assessment)
        existing = session.get(LessonVersion, item.lesson.id)
        if existing is not None:
            if existing.content_hash != content_hash:
                raise RuntimeError(
                    f"Published lesson {item.lesson.slug} changed; increment its immutable version"
                )
            continue
        missing_sources = set(item.lesson.sources) - sources_by_id.keys()
        if missing_sources:
            raise RuntimeError(f"Unknown lesson source IDs: {sorted(missing_sources)}")
        session.add(
            LessonVersion(
                id=item.lesson.id,
                course_version_id=course_version.id,
                slug=item.lesson.slug,
                version=item.lesson.version,
                position=item.position,
                title=item.lesson.title,
                framework=item.lesson.framework,
                level=item.lesson.level,
                objective=item.lesson.objective,
                estimated_minutes=item.lesson.estimated_minutes,
                targets=item.lesson.targets,
                sources=[sources_by_id[source_id] for source_id in item.lesson.sources],
                content=contract,
                assessment_config=assessment,
                content_hash=content_hash,
                status="published",
                skill_version=course_data.skill_version,
            )
        )
    session.flush()


def _content_hash(content: dict[str, object], assessment: dict[str, object]) -> str:
    serialized = json.dumps(
        {"content": content, "assessment": assessment},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

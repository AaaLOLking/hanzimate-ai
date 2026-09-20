from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

TRACKS = {"daily-life", "hsk"}
ACTIVITIES = ("guided", "retrieval", "transfer")
CONTENT_KEYS = {
    "guided": "guided_practice",
    "retrieval": "retrieval_practice",
    "transfer": "transfer_task",
}


def load_catalogs(catalog_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted(catalog_dir.glob("course_catalog*.json"))
    if not paths:
        raise ValueError(f"No course_catalog*.json files found in {catalog_dir}")
    catalogs: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise TypeError(f"{path.name}: catalog root must be an object")
        catalogs.append((path, payload))
    return catalogs


def validate_catalogs(catalogs: list[tuple[Path, dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    version_ids: set[str] = set()
    lesson_ids: set[str] = set()
    course_versions: dict[str, list[int]] = {}

    for path, catalog in catalogs:
        prefix = path.name
        course = catalog.get("course")
        lessons = catalog.get("lessons")
        sources = catalog.get("source_catalog")
        if not isinstance(course, dict):
            errors.append(f"{prefix}: course must be an object")
            continue
        if not isinstance(lessons, list) or not lessons:
            errors.append(f"{prefix}: lessons must be a non-empty array")
            continue
        if not isinstance(sources, list) or not sources:
            errors.append(f"{prefix}: source_catalog must be a non-empty array")
            continue

        version_id = course.get("version_id")
        version = course.get("version")
        course_id = course.get("id")
        if not isinstance(version_id, str) or not version_id:
            errors.append(f"{prefix}: course.version_id is required")
        elif version_id in version_ids:
            errors.append(f"{prefix}: duplicate course version ID {version_id}")
        else:
            version_ids.add(version_id)
        if not isinstance(version, int) or version < 1:
            errors.append(f"{prefix}: course.version must be a positive integer")
        elif isinstance(course_id, str):
            course_versions.setdefault(course_id, []).append(version)
        if not isinstance(course.get("skill_version"), str):
            errors.append(f"{prefix}: course.skill_version is required")

        source_ids: set[str] = set()
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get("id"), str):
                errors.append(f"{prefix}: each source needs a string ID")
                continue
            source_id = source["id"]
            if source_id in source_ids:
                errors.append(f"{prefix}: duplicate source ID {source_id}")
            source_ids.add(source_id)
            if not str(source.get("url", "")).startswith("https://"):
                errors.append(f"{prefix}: source {source_id} must use an HTTPS URL")

        positions: list[int] = []
        slugs: set[str] = set()
        for item in lessons:
            if not isinstance(item, dict) or not isinstance(item.get("lesson"), dict):
                errors.append(f"{prefix}: every lesson entry needs a lesson object")
                continue
            lesson = item["lesson"]
            position = item.get("position")
            lesson_id = lesson.get("id")
            slug = lesson.get("slug")
            label = f"{prefix}:{slug or lesson_id or '?'}"
            if not isinstance(position, int):
                errors.append(f"{label}: position must be an integer")
            else:
                positions.append(position)
            if not isinstance(lesson_id, str) or not lesson_id:
                errors.append(f"{label}: lesson.id is required")
            elif lesson_id in lesson_ids:
                errors.append(f"{label}: duplicate lesson version ID {lesson_id}")
            else:
                lesson_ids.add(lesson_id)
            if not isinstance(slug, str) or not slug:
                errors.append(f"{label}: lesson.slug is required")
            elif slug in slugs:
                errors.append(f"{label}: duplicate slug in release")
            else:
                slugs.add(slug)

            track = lesson.get("track")
            if track is not None and track not in TRACKS:
                errors.append(f"{label}: track must be daily-life or hsk")
            if isinstance(version, int) and version >= 2 and track not in TRACKS:
                errors.append(f"{label}: track is required for course version 2+")
            minutes = lesson.get("estimated_minutes")
            if not isinstance(minutes, int) or not 5 <= minutes <= 20:
                errors.append(f"{label}: estimated_minutes must be 5–20")
            if not isinstance(lesson.get("objective"), str) or not lesson["objective"].strip():
                errors.append(f"{label}: one observable objective is required")
            if not isinstance(lesson.get("targets"), list) or not lesson["targets"]:
                errors.append(f"{label}: targets must be non-empty")
            lesson_sources = lesson.get("sources")
            if not isinstance(lesson_sources, list) or not lesson_sources:
                errors.append(f"{label}: sources must be non-empty")
            else:
                unknown = set(lesson_sources) - source_ids
                if unknown:
                    errors.append(f"{label}: unknown sources {sorted(unknown)}")
            if not isinstance(lesson.get("examples"), list) or len(lesson["examples"]) < 2:
                errors.append(f"{label}: at least two examples are required")

            assessment = item.get("assessment_config")
            if not isinstance(assessment, dict):
                errors.append(f"{label}: assessment_config is required")
                continue
            for activity in ACTIVITIES:
                content = lesson.get(CONTENT_KEYS[activity])
                rule = assessment.get(activity)
                if not isinstance(content, dict):
                    errors.append(f"{label}: {CONTENT_KEYS[activity]} is required")
                elif not all(content.get(key) for key in ("prompt", "answer_rule", "feedback_rule")):
                    errors.append(f"{label}: {CONTENT_KEYS[activity]} is incomplete")
                if not isinstance(rule, dict):
                    errors.append(f"{label}: assessment {activity} is required")
                elif not rule.get("required_all") and not rule.get("required_any"):
                    errors.append(f"{label}: assessment {activity} has no observable checks")

        expected_positions = list(range(1, len(lessons) + 1))
        if sorted(positions) != expected_positions:
            errors.append(f"{prefix}: lesson positions must be exactly {expected_positions}")

    for course_id, versions in course_versions.items():
        if len(versions) != len(set(versions)):
            errors.append(f"course {course_id}: version numbers must be unique")
    return errors


def compile_wiki(
    catalogs: list[tuple[Path, dict[str, Any]]], output_dir: Path
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"format_version": 1, "releases": []}
    root_links: list[str] = ["# HanziMate Course Wiki", ""]

    for path, catalog in sorted(catalogs, key=lambda item: item[1]["course"]["version"]):
        course = catalog["course"]
        version = course["version"]
        release_dir = output_dir / f"v{version}"
        release_dir.mkdir(parents=True, exist_ok=True)
        sources = {source["id"]: source for source in catalog["source_catalog"]}
        index_lines = [
            f"# {course['title']} · v{version}",
            "",
            course["description"],
            "",
            f"- Framework: {course['framework']}",
            f"- Level: {course['level']}",
            f"- Skill: {course['skill_version']}",
            "",
            "## Lessons",
            "",
        ]
        lesson_manifest: list[dict[str, Any]] = []
        for item in sorted(catalog["lessons"], key=lambda row: row["position"]):
            lesson = item["lesson"]
            filename = f"{item['position']:02d}-{lesson['slug']}.md"
            page = _render_lesson_page(course, lesson, sources)
            (release_dir / filename).write_text(page, encoding="utf-8")
            index_lines.append(f"- [{item['position']:02d}. {lesson['title']}]({filename})")
            lesson_manifest.append(
                {
                    "id": lesson["id"],
                    "slug": lesson["slug"],
                    "track": lesson.get("track", "legacy"),
                    "sha256": _sha256_json(lesson),
                }
            )
        (release_dir / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        root_links.append(f"- [v{version} · {course['title']}](v{version}/index.md)")
        manifest["releases"].append(
            {
                "course_id": course["id"],
                "version_id": course["version_id"],
                "version": version,
                "catalog_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "lessons": lesson_manifest,
            }
        )

    (output_dir / "index.md").write_text("\n".join(root_links) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _render_lesson_page(
    course: dict[str, Any], lesson: dict[str, Any], sources: dict[str, dict[str, Any]]
) -> str:
    lines = [
        f"# {lesson['title']}",
        "",
        "> Generated public Wiki page. Assessment answers are intentionally omitted.",
        "",
        f"- Course version: {course['version']}",
        f"- Lesson version: {lesson['version']}",
        f"- Track: {lesson.get('track', 'legacy')}",
        f"- Framework / level: {lesson['framework']} / {lesson['level']}",
        f"- Estimated time: {lesson['estimated_minutes']} minutes",
        "",
        "## Objective",
        "",
        lesson["objective"],
        "",
        "## Targets",
        "",
        ", ".join(lesson["targets"]),
        "",
        "## Explanation",
        "",
        lesson["explanation"],
        "",
        "## Examples",
        "",
    ]
    for example in lesson["examples"]:
        lines.extend([f"- **{example['chinese']}** — {example['note']}"])
    lines.extend(["", "## Practice prompts", ""])
    for label, key in (
        ("Guided production", "guided_practice"),
        ("Unaided retrieval", "retrieval_practice"),
        ("Transfer", "transfer_task"),
    ):
        lines.extend([f"### {label}", "", lesson[key]["prompt"], ""])
    lines.extend(["## Sources", ""])
    for source_id in lesson["sources"]:
        source = sources[source_id]
        lines.append(f"- [{source['title']}]({source['url']}) — {source['publisher']}")
    return "\n".join(lines) + "\n"


def _sha256_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate releases and compile course Wiki pages")
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        catalogs = load_catalogs(args.catalog_dir)
    except (TypeError, ValueError) as exc:
        print(f"Course catalog validation failed:\n- {exc}")
        return 1
    errors = validate_catalogs(catalogs)
    if errors:
        print("Course catalog validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.output_dir is not None:
        manifest = compile_wiki(catalogs, args.output_dir)
        lesson_count = sum(len(release["lessons"]) for release in manifest["releases"])
        print(
            f"Compiled {len(manifest['releases'])} releases and {lesson_count} lesson pages "
            f"to {args.output_dir}"
        )
    elif not args.check:
        parser.error("provide --check or --output-dir")
    else:
        print(f"Validated {len(catalogs)} immutable course releases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

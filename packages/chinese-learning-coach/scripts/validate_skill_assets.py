from __future__ import annotations

import json
from pathlib import Path

from compile_course_wiki import load_catalogs, validate_catalogs

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
EVAL_DIR = ROOT / "evals"
COURSE_DIR = ROOT.parent.parent / "apps" / "api" / "app" / "content"


def validate_schemas() -> list[str]:
    errors: list[str] = []
    schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    if not schema_files:
        return ["No schema files found."]

    for path in schema_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue

        for key in ("$schema", "$id", "title", "type"):
            if key not in data:
                errors.append(f"{path.name}: missing {key}")
        if data.get("type") != "object":
            errors.append(f"{path.name}: root type must be object")
        if not isinstance(data.get("required"), list):
            errors.append(f"{path.name}: required must be an array")

    return errors


def validate_error_evals() -> list[str]:
    errors: list[str] = []
    path = EVAL_DIR / "gold-errors.jsonl"
    required = {
        "id",
        "learner_text",
        "expected_is_error",
        "expected_type",
        "expected_subtype",
        "acceptable_corrections",
        "note",
    }
    ids: set[str] = set()

    if not path.exists():
        return ["gold-errors.jsonl is missing."]

    rows = path.read_text(encoding="utf-8").splitlines()
    if len(rows) < 20:
        errors.append("gold-errors.jsonl must contain at least 20 seed cases.")

    for line_number, line in enumerate(rows, start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"gold-errors.jsonl:{line_number}: {exc}")
            continue

        missing = required - row.keys()
        if missing:
            errors.append(
                f"gold-errors.jsonl:{line_number}: missing {sorted(missing)}"
            )

        case_id = row.get("id")
        if case_id in ids:
            errors.append(f"gold-errors.jsonl:{line_number}: duplicate id {case_id}")
        if isinstance(case_id, str):
            ids.add(case_id)

        if row.get("expected_is_error") is False and (
            row.get("expected_type") is not None
            or row.get("expected_subtype") is not None
        ):
            errors.append(
                f"gold-errors.jsonl:{line_number}: non-error must have null type"
            )

    return errors


def main() -> int:
    course_errors = (
        validate_catalogs(load_catalogs(COURSE_DIR)) if COURSE_DIR.exists() else []
    )
    errors = [*validate_schemas(), *validate_error_evals(), *course_errors]
    if errors:
        print("Skill asset validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Skill assets are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

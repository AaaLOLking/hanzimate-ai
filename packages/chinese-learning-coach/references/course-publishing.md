# Course Publishing

Use this workflow for a multi-lesson course release. A release catalog is the auditable source; compiled Wiki pages are public, answer-free retrieval material.

## Release invariants

- A course has a stable `course.id` and slug.
- Every release has a new `course.version_id` and increasing integer `course.version`.
- Every lesson version has a globally unique ID. A lesson copied into a new course release receives a new ID; increment its lesson version when its teaching content changed.
- Published lesson content, assessment rules, sources, order, and lesson set are immutable.
- Each lesson has one track: `daily-life` or `hsk`.
- Keep answer rules and deterministic assessment configuration in the release catalog and server database only. Do not compile them into public Wiki pages or send them to the browser.
- A release cites official or licensed sources but uses original examples and tasks.

## Authoring sequence

1. Fix the release Mission, level range, track balance, and source catalog.
2. Give every lesson one observable objective and a 5–20 minute contract.
3. Write guided production, unaided retrieval, and a changed-surface transfer task.
4. Add deterministic assessment terms that test the stated answer rule. Prefer a narrow human-reviewable baseline over an opaque mastery claim.
5. Review every lesson with `rubrics/lesson-quality.md`; reject any lesson below its threshold.
6. Run the catalog compiler in check mode.
7. Compile Wiki pages and inspect the manifest hashes.
8. Publish the JSON catalog with the API. Preserve all earlier release catalogs so old workspaces remain restorable.

## Commands

~~~powershell
py -3 scripts/compile_course_wiki.py --catalog-dir <catalog-dir> --check
py -3 scripts/compile_course_wiki.py --catalog-dir <catalog-dir> --output-dir <wiki-dir>
~~~

The compiler verifies identities, positions, sources, lesson shape, tracks, activities, and assessment presence across every release. It writes an index, one Markdown page per lesson, and a deterministic manifest. The Wiki intentionally omits `answer_rule` and `assessment_config`.

## Version recovery

The learner's `LessonProgress` always points to an immutable lesson-version ID. The catalog UI may show only the latest course version, but historical workspaces and lesson URLs must remain readable. Never migrate a learner's old evidence to a new lesson version without an explicit product migration and evidence policy.

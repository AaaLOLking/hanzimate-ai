import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import Settings
from app.course_content import seed_course_catalog
from app.models import CourseVersion, LessonVersion
from app.providers.lesson_tutor import DeepSeekLessonTutorProvider, LessonTutorRequest


def _first_lesson_id(client: TestClient, headers: dict[str, str] | None = None) -> str:
    response = client.get("/api/v1/courses", headers=headers or {})
    assert response.status_code == 200
    return response.json()[0]["lessons"][0]["id"]


def test_course_catalog_is_versioned_and_does_not_leak_answer_rules(
    client: TestClient,
) -> None:
    catalog = client.get("/api/v1/courses")
    assert catalog.status_code == 200
    courses = catalog.json()
    assert len(courses) == 1
    assert courses[0]["version"] == 2
    assert courses[0]["framework"] == "GF0025-2021 + HSK3.0"
    assert len(courses[0]["lessons"]) == 12
    assert [lesson["track"] for lesson in courses[0]["lessons"]].count("daily-life") == 6
    assert [lesson["track"] for lesson in courses[0]["lessons"]].count("hsk") == 6
    assert courses[0]["lessons"][0]["title"] == "在食堂说对一碗、一份、一杯"

    lesson_id = courses[0]["lessons"][0]["id"]
    lesson = client.get(f"/api/v1/lessons/{lesson_id}")
    assert lesson.status_code == 200
    body = lesson.json()
    assert body["course_version"] == 2
    assert body["progress"] is None
    assert body["sources"][0]["publisher"].startswith("中华人民共和国教育部")
    assert "answer_rule" not in body["content"]["guided_practice"]
    assert "answer_rule" not in body["content"]["retrieval_practice"]
    assert "assessment_config" not in lesson.text

    database = client.app.state.database
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CourseVersion)) == 2
        assert session.scalar(select(func.count()).select_from(LessonVersion)) == 15

    legacy = client.get("/api/v1/lessons/12000000-0000-4000-8000-000000000001")
    assert legacy.status_code == 200
    assert legacy.json()["course_version"] == 1


def test_published_course_version_rejects_a_changed_lesson_set(
    client: TestClient,
) -> None:
    database = client.app.state.database
    with database.session_factory() as session:
        session.execute(delete(LessonVersion).where(LessonVersion.position == 3))
        session.commit()

    with database.session_factory() as session:
        with pytest.raises(RuntimeError, match="lesson set changed"):
            seed_course_catalog(session)


def test_every_latest_lesson_keeps_assessment_server_side(client: TestClient) -> None:
    lessons = client.get("/api/v1/courses").json()[0]["lessons"]
    assert len(lessons) == 12
    for summary in lessons:
        response = client.get(f"/api/v1/lessons/{summary['id']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["content"]["track"] in {"daily-life", "hsk"}
        assert len(detail["content"]["examples"]) >= 2
        assert detail["sources"]
        assert "answer_rule" not in response.text
        assert "assessment_config" not in response.text


def test_hsk_writing_lesson_completes_only_after_transfer(client: TestClient) -> None:
    lesson_id = client.get("/api/v1/courses").json()[0]["lessons"][-1]["id"]
    assert client.post(f"/api/v1/lessons/{lesson_id}/start").status_code == 201
    attempts = [
        ("guided", "我先查路线，然后坐地铁，最后到教室。"),
        ("retrieval", "她先复习生词，然后做练习，最后检查答案。"),
        ("transfer", "我先网上预约，然后到前台登记，最后见到医生。"),
    ]
    for index, (activity, response) in enumerate(attempts):
        result = client.post(
            f"/api/v1/lessons/{lesson_id}/attempts",
            json={"activity": activity, "response": response},
        )
        assert result.status_code == 201
        assert result.json()["passed"] is True
        expected_status = "completed" if index == 2 else "in_progress"
        assert result.json()["progress"]["status"] == expected_status


def test_lesson_start_is_idempotent_and_creates_one_workspace(client: TestClient) -> None:
    lesson_id = _first_lesson_id(client)
    first = client.post(f"/api/v1/lessons/{lesson_id}/start")
    second = client.post(f"/api/v1/lessons/{lesson_id}/start")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["progress"]["id"] == second.json()["progress"]["id"]
    workspaces = client.get("/api/v1/workspaces").json()
    lesson_workspaces = [workspace for workspace in workspaces if workspace["kind"] == "lesson"]
    assert len(lesson_workspaces) == 1
    assert lesson_workspaces[0]["state"]["lesson_version_id"] == lesson_id


def test_lesson_requires_production_and_persists_completion_evidence(
    client: TestClient,
) -> None:
    lesson_id = _first_lesson_id(client)
    started = client.post(f"/api/v1/lessons/{lesson_id}/start").json()
    workspace_id = started["progress"]["workspace_id"]

    failed = client.post(
        f"/api/v1/lessons/{lesson_id}/attempts",
        json={"activity": "guided", "response": "我要牛肉面。"},
    )
    assert failed.status_code == 201
    assert failed.json()["passed"] is False
    assert failed.json()["progress"]["current_step"] == 0
    assert failed.json()["missing_targets"] == ["一碗牛肉面"]

    guided = client.post(
        f"/api/v1/lessons/{lesson_id}/attempts",
        json={"activity": "guided", "response": "请给我一碗牛肉面。"},
    )
    assert guided.json()["passed"] is True
    assert guided.json()["next_activity"] == "retrieval"
    out_of_order = client.post(
        f"/api/v1/lessons/{lesson_id}/attempts",
        json={"activity": "transfer", "response": "一份炒饭和一杯茶，谢谢。"},
    )
    assert out_of_order.status_code == 409

    retrieval = client.post(
        f"/api/v1/lessons/{lesson_id}/attempts",
        json={"activity": "retrieval", "response": "我要一杯咖啡。"},
    )
    assert retrieval.json()["next_activity"] == "transfer"
    transfer = client.post(
        f"/api/v1/lessons/{lesson_id}/attempts",
        json={
            "activity": "transfer",
            "response": "麻烦给我一份炒饭和一杯茶，请少放辣。",
        },
    )
    assert transfer.status_code == 201
    assert transfer.json()["passed"] is True
    assert transfer.json()["next_activity"] == "completed"
    assert transfer.json()["progress"]["status"] == "completed"
    assert transfer.json()["evidence"]["evidence_type"] == "transfer"

    restored = client.get(f"/api/v1/lessons/{lesson_id}").json()
    assert restored["progress"]["current_step"] == 3
    assert restored["progress"]["attempt_count"] == 4
    workspace = client.get(f"/api/v1/workspaces/{workspace_id}").json()
    assert workspace["status"] == "completed"
    assert workspace["state"]["progress"] == 100


def test_lesson_chat_is_scoped_to_current_lesson_and_owner(client: TestClient) -> None:
    owner = str(uuid4())
    other = str(uuid4())
    owner_headers = {"X-Learner-ID": owner}
    other_headers = {"X-Learner-ID": other}
    lesson_id = _first_lesson_id(client, owner_headers)
    assert (
        client.post(f"/api/v1/lessons/{lesson_id}/start", headers=owner_headers).status_code
        == 201
    )
    question = client.post(
        f"/api/v1/lessons/{lesson_id}/ask",
        headers=owner_headers,
        json={"question": "为什么咖啡不能用个？"},
    )
    assert question.status_code == 201
    answer = question.json()["assistant_message"]
    assert answer["provider"] == "local"
    assert "数字和名词之间通常需要量词" in answer["content"]
    assert len(answer["citations"]) == 2

    restored = client.get(f"/api/v1/lessons/{lesson_id}", headers=owner_headers).json()
    assert [message["role"] for message in restored["messages"]] == ["user", "assistant"]
    assert restored["context_pack"]["lesson"]["id"] == lesson_id
    assert "full_history" not in restored["context_pack"]

    other_view = client.get(f"/api/v1/lessons/{lesson_id}", headers=other_headers).json()
    assert other_view["progress"] is None
    assert other_view["messages"] == []
    forbidden_attempt = client.post(
        f"/api/v1/lessons/{lesson_id}/attempts",
        headers=other_headers,
        json={"activity": "guided", "response": "我要一碗牛肉面。"},
    )
    assert forbidden_attempt.status_code == 409


def test_deepseek_lesson_tutor_keeps_secret_server_side(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "只根据本课目标回答。"}}]}
            ).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.providers.lesson_tutor.urlopen", fake_urlopen)
    provider = DeepSeekLessonTutorProvider(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
            deepseek_api_key="secret-deepseek-key",
            # 显式钉住模型名，避免本地 .env 泄漏进合同断言
            deepseek_default_model="deepseek-v4-flash",
        )
    )
    answer = provider.answer(
        LessonTutorRequest(
            question="为什么咖啡用杯？",
            context_pack={
                "mission": {"goal": "校园交流"},
                "lesson": {"id": "lesson-1", "objective": "正确使用量词"},
                "recent_messages": [],
            },
            current_step=1,
        )
    )

    sent_request = captured["request"]
    sent = json.loads(sent_request.data.decode())
    prompt = json.loads(sent["messages"][1]["content"])
    assert sent["model"] == "deepseek-v4-flash"
    assert sent["thinking"] == {"type": "disabled"}
    assert prompt["lesson_context_pack"]["lesson"]["id"] == "lesson-1"
    assert sent_request.headers["Authorization"] == "Bearer secret-deepseek-key"
    assert answer == "只根据本课目标回答。"
    assert "secret-deepseek-key" not in answer

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import AccountDeletionReceipt, User


def test_personal_data_export_is_scoped_and_hides_private_answer_rules(
    client: TestClient,
) -> None:
    owner = str(uuid4())
    other = str(uuid4())
    owner_headers = {"X-Learner-ID": owner}
    other_headers = {"X-Learner-ID": other}
    assert (
        client.post(
            "/api/v1/workspaces",
            headers=owner_headers,
            json={"kind": "conversation", "title": "Only mine"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/beta/feedback",
            headers=owner_headers,
            json={
                "area": "overall",
                "issue_type": "praise",
                "rating": 5,
                "message": "课程目标很清楚。",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/workspaces",
            headers=other_headers,
            json={"kind": "conversation", "title": "Never export this"},
        ).status_code
        == 201
    )

    lesson_id = client.get("/api/v1/courses", headers=owner_headers).json()[0]["lessons"][0][
        "id"
    ]
    assert (
        client.post(f"/api/v1/lessons/{lesson_id}/start", headers=owner_headers).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/lessons/{lesson_id}/attempts",
            headers=owner_headers,
            json={"activity": "guided", "response": "请给我一碗牛肉面。"},
        ).status_code
        == 201
    )

    response = client.get("/api/v1/account/export", headers=owner_headers)
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    archive = response.json()
    assert archive["format"] == "hanzimate-personal-data-v1"
    assert archive["account"]["id"] == owner
    assert archive["record_counts"]["workspaces"] == 2
    assert archive["record_counts"]["learning_evidence"] == 1
    assert archive["record_counts"]["beta_feedback"] == 1
    assert archive["data"]["beta_feedback"][0]["message"] == "课程目标很清楚。"
    assert "answer_rule" not in response.text
    assert "Never export this" not in response.text
    assert other not in response.text


def test_account_deletion_requires_matching_email_and_removes_owned_data(
    client: TestClient,
) -> None:
    owner = str(uuid4())
    headers = {"X-Learner-ID": owner}
    overview = client.get("/api/v1/account", headers=headers).json()
    email = overview["user"]["email"]
    assert (
        client.post(
            "/api/v1/workspaces",
            headers=headers,
            json={"kind": "conversation", "title": "Delete me"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/beta/feedback",
            headers=headers,
            json={
                "area": "overall",
                "issue_type": "bug",
                "rating": 1,
                "is_blocking": True,
                "message": "删除前的测试反馈。",
            },
        ).status_code
        == 201
    )

    wrong = client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"email": "wrong@example.com", "confirmation": "删除我的账户"},
    )
    assert wrong.status_code == 422
    assert len(client.get("/api/v1/workspaces", headers=headers).json()) == 1

    deleted = client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"email": email, "confirmation": "删除我的账户"},
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["deleted_records"]["accounts"] == 1
    assert body["deleted_records"]["workspaces"] == 1
    assert body["deleted_records"]["beta_feedback"] == 1
    assert email not in deleted.text

    database = client.app.state.database
    with database.session_factory() as session:
        assert session.get(User, owner) is None
        assert session.scalar(select(func.count()).select_from(AccountDeletionReceipt)) == 1

    assert client.get("/api/v1/workspaces", headers=headers).json() == []


def test_model_call_limit_uses_local_fallback_and_records_reason(tmp_path: Path) -> None:
    application = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'model-limit.sqlite3').as_posix()}",
            database_auto_create=True,
            deepseek_api_key="not-called",
            model_daily_external_call_limit=0,
        )
    )
    with TestClient(application) as client:
        lesson_id = client.get("/api/v1/courses").json()[0]["lessons"][0]["id"]
        assert client.post(f"/api/v1/lessons/{lesson_id}/start").status_code == 201
        answer = client.post(
            f"/api/v1/lessons/{lesson_id}/ask",
            json={"question": "请再给我一个例子。"},
        )
        assert answer.status_code == 201
        assert answer.json()["assistant_message"]["provider"] == "local"

        usage = client.get("/api/v1/models/usage").json()
        assert usage["external_calls"] == 0
        assert usage["blocked_calls"] == 1
        assert usage["remaining_external_calls"] == 0
        assert [run["status"] for run in usage["recent_runs"]] == [
            "succeeded",
            "blocked",
        ]
        assert usage["recent_runs"][0]["fallback_from"] == "deepseek"
        assert usage["recent_runs"][1]["error_code"] == "daily_call_limit"
    application.state.database.dispose()

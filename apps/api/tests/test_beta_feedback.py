from uuid import uuid4

from fastapi.testclient import TestClient


def test_beta_dashboard_tracks_completed_conversations_and_private_feedback(
    client: TestClient,
) -> None:
    owner_headers = {"X-Learner-ID": str(uuid4())}
    other_headers = {"X-Learner-ID": str(uuid4())}

    initial = client.get("/api/v1/beta", headers=owner_headers)
    assert initial.status_code == 200
    assert initial.json()["progress"] == {
        "conversations": {"current": 0, "target": 3, "complete": False},
        "lessons": {"current": 0, "target": 2, "complete": False},
        "reviews": {"current": 0, "target": 2, "complete": False},
        "feedback": {"current": 0, "target": 1, "complete": False},
    }
    assert initial.json()["ready_for_exit"] is False

    for number in range(3):
        created = client.post(
            "/api/v1/voice/sessions",
            headers=owner_headers,
            json={"scenario": f"Beta conversation {number}"},
        )
        assert created.status_code == 201
        session_id = created.json()["session"]["id"]
        finalized = client.post(
            f"/api/v1/voice/sessions/{session_id}/finalize",
            headers=owner_headers,
            json={"duration_seconds": 30},
        )
        assert finalized.status_code == 200

    submitted = client.post(
        "/api/v1/beta/feedback",
        headers=owner_headers,
        json={
            "area": "conversation",
            "issue_type": "wrong_correction",
            "rating": 2,
            "is_blocking": True,
            "message": "量词纠正不准确，影响继续练习。",
            "page_path": "/conversation/example",
        },
    )
    assert submitted.status_code == 201
    assert submitted.json()["is_blocking"] is True

    dashboard = client.get("/api/v1/beta", headers=owner_headers).json()
    assert dashboard["progress"]["conversations"] == {
        "current": 3,
        "target": 3,
        "complete": True,
    }
    assert dashboard["progress"]["feedback"]["complete"] is True
    assert len(dashboard["feedback"]) == 1
    assert dashboard["feedback"][0]["message"] == "量词纠正不准确，影响继续练习。"

    other_dashboard = client.get("/api/v1/beta", headers=other_headers).json()
    assert other_dashboard["feedback"] == []
    assert other_dashboard["progress"]["feedback"]["current"] == 0


def test_beta_feedback_rejects_external_or_query_string_page_paths(
    client: TestClient,
) -> None:
    headers = {"X-Learner-ID": str(uuid4())}
    payload = {
        "area": "overall",
        "issue_type": "idea",
        "rating": 4,
        "message": "希望增加更多校园场景。",
    }

    external = client.post(
        "/api/v1/beta/feedback",
        headers=headers,
        json={**payload, "page_path": "https://example.com/private"},
    )
    query = client.post(
        "/api/v1/beta/feedback",
        headers=headers,
        json={**payload, "page_path": "/conversation?token=secret"},
    )

    assert external.status_code == 422
    assert query.status_code == 422
    assert client.get("/api/v1/beta", headers=headers).json()["feedback"] == []

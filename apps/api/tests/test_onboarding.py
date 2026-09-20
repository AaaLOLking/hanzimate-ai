from uuid import uuid4

from fastapi.testclient import TestClient

ONBOARDING_PAYLOAD = {
    "display_name": "Alex Morgan",
    "locale": "zh-CN",
    "consent": {
        "policy_version": "2026-08",
        "privacy_acknowledged": True,
        "learning_memory": True,
        "audio_retention": False,
    },
    "mission": {
        "why": "I want to study and live independently in China.",
        "success_looks_like": ["Pass HSK 3", "Handle campus conversations"],
        "constraints": ["Three hours per week"],
        "out_of_scope": ["Business Chinese"],
        "priorities": ["campus", "hsk_exam"],
        "weekly_minutes": 180,
        "deadline": "2026-12-31",
    },
    "profile": {
        "native_language": "English",
        "support_language": "English",
        "current_hsk_band": "HSK2",
        "self_assessment": {"listening": 3, "speaking": 2, "reading": 3, "writing": 2},
        "correction_mode": "turn_end",
        "speech_speed": "slow",
        "show_pinyin": True,
        "english_first": False,
        "review_interval_days": 3,
    },
}


def test_new_learner_can_complete_onboarding_and_restore_workspace(
    client: TestClient,
) -> None:
    initial = client.get("/api/v1/onboarding")
    assert initial.status_code == 200
    assert initial.json()["complete"] is False

    saved = client.put("/api/v1/onboarding", json=ONBOARDING_PAYLOAD)
    assert saved.status_code == 200
    body = saved.json()
    assert body["complete"] is True
    assert body["profile"]["estimated_hsk_band"] == "HSK2"
    assert body["mission"]["priorities"] == ["campus", "hsk_exam"]
    assert body["recommended_workspace"]["title"] == "校园问路"

    workspaces = client.get("/api/v1/workspaces")
    assert workspaces.status_code == 200
    assert len(workspaces.json()) == 1
    workspace_id = workspaces.json()[0]["id"]

    restored = client.get(f"/api/v1/workspaces/{workspace_id}")
    assert restored.status_code == 200
    assert restored.json()["state"]["source"] == "onboarding"


def test_workspace_access_is_scoped_to_current_learner(client: TestClient) -> None:
    first_user = str(uuid4())
    second_user = str(uuid4())
    created = client.post(
        "/api/v1/workspaces",
        headers={"X-Learner-ID": first_user},
        json={"kind": "lesson", "title": "量词基础", "state": {"step": 2}},
    )
    assert created.status_code == 201

    workspace_id = created.json()["id"]
    forbidden_read = client.get(
        f"/api/v1/workspaces/{workspace_id}", headers={"X-Learner-ID": second_user}
    )
    assert forbidden_read.status_code == 404
    assert client.get("/api/v1/workspaces", headers={"X-Learner-ID": second_user}).json() == []


def test_onboarding_requires_explicit_privacy_acknowledgement(client: TestClient) -> None:
    payload = {**ONBOARDING_PAYLOAD, "consent": {**ONBOARDING_PAYLOAD["consent"]}}
    payload["consent"]["privacy_acknowledged"] = False

    response = client.put("/api/v1/onboarding", json=payload)
    assert response.status_code == 422


def test_model_registry_lists_only_enabled_models(client: TestClient) -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    assert [item["provider"] for item in response.json()] == ["local"]

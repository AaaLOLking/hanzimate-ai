from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import VoiceSession, utc_now
from app.providers.realtime import QwenRealtimeProvider, RealtimeProviderError
from app.realtime.lifecycle import sweep_stale_voice_sessions


def create_conversation_workspace(client: TestClient, learner_id: str | None = None) -> str:
    headers = {"X-Learner-ID": learner_id} if learner_id else {}
    response = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={
            "kind": "conversation",
            "title": "校园问路",
            "state": {"objective": "询问教学楼位置，并确认路线"},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize("mode", ["free", "custom"])
def test_open_practice_survives_restore_and_is_idempotent(client: TestClient, mode: str):
    workspace_id = create_conversation_workspace(client)
    payload = {
        "workspace_id": workspace_id,
        "protocol_version": "live-v1",
        "client_session_id": str(uuid4()),
        "practice_mode": mode,
    }
    if mode == "custom":
        payload["custom_objective"] = "  请扮演面试官，练习中文自我介绍  "
    response = client.post("/api/v1/voice/sessions", json=payload)
    assert response.status_code == 201
    body = response.json()
    context = body["session"]["context_pack"]
    assert context["practice_mode"] == mode
    assert context["scenario_id"] is None
    assert "教学楼" not in context["objective"]
    if mode == "custom":
        assert context["objective"] == payload["custom_objective"].strip()
        assert (
            context["objective"] in body["connection"]["session_update"]["session"]["instructions"]
        )
    else:
        assert "允许自然换话题" in body["connection"]["session_update"]["session"]["instructions"]
    session_id = body["session"]["id"]
    retry = client.post("/api/v1/voice/sessions", json=payload)
    assert retry.status_code == 200
    assert retry.json()["session"]["id"] == session_id
    resumed = client.post(f"/api/v1/voice/sessions/{session_id}/resume")
    assert resumed.json()["connection"]["session_update"] == body["connection"]["session_update"]
    restored = client.get(f"/api/v1/workspaces/{workspace_id}").json()
    assert restored["state"]["practice_mode"] == mode
    changed = {**payload, "practice_mode": "custom", "custom_objective": "练习租房"}
    assert client.post("/api/v1/voice/sessions", json=changed).status_code == 409
    # Later workspace changes must not rewrite the older session's frozen contract.
    scenario_payload = {
        "workspace_id": workspace_id,
        "protocol_version": "live-v1",
        "client_session_id": str(uuid4()),
        "scenario_id": "campus-canteen",
    }
    scenario = client.post("/api/v1/voice/sessions", json=scenario_payload)
    assert scenario.status_code == 201
    assert scenario.json()["session"]["context_pack"]["practice_mode"] == "scenario"
    assert scenario.json()["session"]["context_pack"]["custom_objective"] is None
    assert client.post("/api/v1/voice/sessions", json=payload).status_code == 200


@pytest.mark.parametrize(
    "fields",
    [
        {"practice_mode": "custom"},
        {"practice_mode": "custom", "custom_objective": "   "},
        {"practice_mode": "custom", "custom_objective": "字" * 501},
        {"practice_mode": "free", "scenario_id": "campus-canteen"},
        {"practice_mode": "free", "custom_objective": "练习面试"},
    ],
)
def test_invalid_open_practice_is_rejected(client: TestClient, fields: dict):
    assert client.post("/api/v1/voice/sessions", json=fields).status_code == 422


def test_mock_voice_session_persists_transcript_and_finalizes(client: TestClient) -> None:
    workspace_id = create_conversation_workspace(client)
    created = client.post(
        "/api/v1/voice/sessions",
        json={
            "workspace_id": workspace_id,
            "scenario": "校园问路",
            "correction_mode": "coach",
            "speech_speed": "slow",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["connection"]["mode"] == "mock"
    assert body["session"]["context_pack"]["objective"] == "询问教学楼位置，并确认路线"
    assert "Authorization" not in created.text
    voice_session_id = body["session"]["id"]

    activated = client.patch(
        f"/api/v1/voice/sessions/{voice_session_id}/status", json={"status": "active"}
    )
    assert activated.status_code == 200

    first_event = {
        "client_event_id": "turn-1-user",
        "sequence_no": 1,
        "speaker": "user",
        "transcript": "请问，图书馆怎么走？",
        "source": "browser_text",
    }
    first = client.post(f"/api/v1/voice/sessions/{voice_session_id}/utterances", json=first_event)
    assert first.status_code == 201
    duplicate = client.post(
        f"/api/v1/voice/sessions/{voice_session_id}/utterances", json=first_event
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]

    second = client.post(
        f"/api/v1/voice/sessions/{voice_session_id}/utterances",
        json={
            "client_event_id": "turn-1-assistant",
            "sequence_no": 2,
            "speaker": "assistant",
            "transcript": "一直往前走，第二个路口右转。",
            "source": "mock",
        },
    )
    assert second.status_code == 201

    finalized = client.post(
        f"/api/v1/voice/sessions/{voice_session_id}/finalize",
        json={"duration_seconds": 42},
    )
    assert finalized.status_code == 200
    final_body = finalized.json()
    assert final_body["status"] == "completed"
    assert final_body["duration_seconds"] == 42
    assert [item["sequence_no"] for item in final_body["utterances"]] == [1, 2]

    restored = client.get(f"/api/v1/voice/sessions/{voice_session_id}")
    assert restored.status_code == 200
    assert len(restored.json()["utterances"]) == 2
    restored_workspace = client.get(f"/api/v1/workspaces/{workspace_id}")
    assert restored_workspace.json()["status"] == "completed"
    assert restored_workspace.json()["state"]["last_session_id"] == voice_session_id
    assert "请问" in restored_workspace.json()["state"]["last_transcript_preview"]


def test_voice_duration_is_clipped_to_provider_budget(client: TestClient) -> None:
    created = client.post("/api/v1/voice/sessions", json={"scenario_id": "campus-canteen"}).json()
    session_id = created["session"]["id"]
    finished = client.post(
        f"/api/v1/voice/sessions/{session_id}/finalize",
        json={"duration_seconds": 800},
    )
    assert finished.status_code == 200
    assert finished.json()["duration_seconds"] == 480


def test_scenario_catalog_updates_workspace_context(client: TestClient) -> None:
    scenarios = client.get("/api/v1/voice/scenarios")
    assert scenarios.status_code == 200
    assert len(scenarios.json()) == 6
    assert {item["id"] for item in scenarios.json()} == {
        "campus-canteen",
        "convenience-store",
        "campus-directions",
        "dorm-repair",
        "hospital-registration",
        "classroom-question",
    }

    workspace_id = create_conversation_workspace(client)
    created = client.post(
        "/api/v1/voice/sessions",
        json={"workspace_id": workspace_id, "scenario_id": "hospital-registration"},
    )
    assert created.status_code == 201
    assert created.json()["session"]["context_pack"]["objective"] == (
        "说明就诊需求，询问科室和挂号流程"
    )
    workspace = client.get(f"/api/v1/workspaces/{workspace_id}").json()
    assert workspace["title"] == "医院挂号"
    assert workspace["state"]["scenario_id"] == "hospital-registration"
    assert "不提供医疗诊断" in workspace["state"]["safety_note"]


def test_session_event_ledger_is_idempotent_and_updates_metrics(client: TestClient) -> None:
    voice_session_id = client.post(
        "/api/v1/voice/sessions", json={"scenario_id": "campus-directions"}
    ).json()["session"]["id"]
    payloads = [
        {
            "client_event_id": "reconnect-1",
            "event_type": "reconnect_attempt",
            "elapsed_ms": 12_000,
            "event_payload": {"attempt": 1},
        },
        {
            "client_event_id": "interrupt-1",
            "event_type": "interruption",
            "elapsed_ms": 20_000,
        },
        {
            "client_event_id": "first-response",
            "event_type": "provider_first_response",
            "event_payload": {"latency_ms": 842},
        },
    ]
    for payload in payloads:
        assert (
            client.post(
                f"/api/v1/voice/sessions/{voice_session_id}/events", json=payload
            ).status_code
            == 201
        )

    duplicate = client.post(f"/api/v1/voice/sessions/{voice_session_id}/events", json=payloads[0])
    assert duplicate.status_code == 201

    restored = client.get(f"/api/v1/voice/sessions/{voice_session_id}").json()
    assert restored["reconnect_count"] == 1
    assert restored["interruption_count"] == 1
    assert restored["first_response_latency_ms"] == 842
    events = client.get(f"/api/v1/voice/sessions/{voice_session_id}/events")
    assert [event["event_type"] for event in events.json()] == [
        "reconnect_attempt",
        "interruption",
        "provider_first_response",
    ]


def test_session_events_are_scoped_to_owner(client: TestClient) -> None:
    first_user = str(uuid4())
    second_user = str(uuid4())
    created = client.post(
        "/api/v1/voice/sessions",
        headers={"X-Learner-ID": first_user},
        json={"scenario_id": "campus-canteen"},
    )
    session_id = created.json()["session"]["id"]
    response = client.post(
        f"/api/v1/voice/sessions/{session_id}/events",
        headers={"X-Learner-ID": second_user},
        json={"client_event_id": "lost-1", "event_type": "connection_lost"},
    )
    assert response.status_code == 404


def test_completed_voice_session_rejects_invalid_transition(client: TestClient) -> None:
    created = client.post("/api/v1/voice/sessions", json={"scenario": "食堂点餐"}).json()
    voice_session_id = created["session"]["id"]
    assert (
        client.post(f"/api/v1/voice/sessions/{voice_session_id}/finalize", json={}).status_code
        == 200
    )

    response = client.patch(
        f"/api/v1/voice/sessions/{voice_session_id}/status", json={"status": "active"}
    )
    assert response.status_code == 409


def test_voice_session_is_scoped_to_its_owner(client: TestClient) -> None:
    first_user = str(uuid4())
    second_user = str(uuid4())
    workspace_id = create_conversation_workspace(client, first_user)
    created = client.post(
        "/api/v1/voice/sessions",
        headers={"X-Learner-ID": first_user},
        json={"workspace_id": workspace_id},
    )
    voice_session_id = created.json()["session"]["id"]

    response = client.get(
        f"/api/v1/voice/sessions/{voice_session_id}",
        headers={"X-Learner-ID": second_user},
    )
    assert response.status_code == 404


def test_mock_session_does_not_accept_sdp_offer(client: TestClient) -> None:
    voice_session_id = client.post("/api/v1/voice/sessions", json={"scenario": "医院挂号"}).json()[
        "session"
    ]["id"]
    response = client.post(
        f"/api/v1/voice/sessions/{voice_session_id}/offer",
        json={"sdp": "v=0\r\n" + "a" * 30},
    )
    assert response.status_code == 409


def test_qwen_sdp_proxy_never_returns_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        QwenRealtimeProvider,
        "exchange_offer",
        lambda self, offer_sdp: "v=0\r\nmock-answer-sdp",
    )
    application = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'qwen.sqlite3').as_posix()}",
            database_auto_create=True,
            dashscope_api_key="super-secret-api-key",
            dashscope_workspace_id="workspace-123",
        )
    )
    with TestClient(application) as configured_client:
        created = configured_client.post("/api/v1/voice/sessions", json={"scenario": "便利店购物"})
        assert created.status_code == 201
        assert created.json()["connection"]["mode"] == "webrtc"
        assert "super-secret-api-key" not in created.text
        voice_session_id = created.json()["session"]["id"]

        offer = configured_client.post(
            f"/api/v1/voice/sessions/{voice_session_id}/offer",
            json={"sdp": "v=0\r\n" + "a" * 30},
        )
        assert offer.status_code == 200
        assert offer.json()["sdp"] == "v=0\r\nmock-answer-sdp"
        assert "super-secret-api-key" not in offer.text

        reconnect_event = configured_client.post(
            f"/api/v1/voice/sessions/{voice_session_id}/events",
            json={
                "client_event_id": "reconnect-attempt-1",
                "event_type": "reconnect_attempt",
                "event_payload": {"attempt": 1},
            },
        )
        assert reconnect_event.status_code == 201
        reconnected = configured_client.post(
            f"/api/v1/voice/sessions/{voice_session_id}/offer",
            json={"sdp": "v=0\r\n" + "b" * 30},
        )
        assert reconnected.status_code == 200
        restored = configured_client.get(f"/api/v1/voice/sessions/{voice_session_id}").json()
        assert restored["status"] == "active"
        assert restored["reconnect_count"] == 1
    application.state.database.dispose()


def test_qwen_offer_failure_keeps_session_available_for_text_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    def reject_offer(self, offer_sdp):
        raise RealtimeProviderError("temporary signaling failure")

    monkeypatch.setattr(QwenRealtimeProvider, "exchange_offer", reject_offer)
    application = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'qwen-fallback.sqlite3').as_posix()}",
            database_auto_create=True,
            dashscope_api_key="super-secret-api-key",
            dashscope_workspace_id="workspace-123",
        )
    )
    with TestClient(application) as configured_client:
        created = configured_client.post(
            "/api/v1/voice/sessions", json={"scenario_id": "convenience-store"}
        ).json()
        session_id = created["session"]["id"]
        offer = configured_client.post(
            f"/api/v1/voice/sessions/{session_id}/offer",
            json={"sdp": "v=0\r\n" + "a" * 30},
        )
        assert offer.status_code == 502
        restored = configured_client.get(f"/api/v1/voice/sessions/{session_id}").json()
        assert restored["status"] == "active"
        assert "temporary signaling failure" in restored["failure_reason"]
        utterance = configured_client.post(
            f"/api/v1/voice/sessions/{session_id}/utterances",
            json={
                "client_event_id": "fallback-text-1",
                "sequence_no": 1,
                "speaker": "user",
                "transcript": "请问，水在哪里？",
                "source": "browser_text",
            },
        )
        assert utterance.status_code == 201
    application.state.database.dispose()


def test_live_session_create_is_idempotent_and_builds_patient_teaching_config(
    client: TestClient,
) -> None:
    workspace_id = create_conversation_workspace(client)
    payload = {
        "client_session_id": str(uuid4()),
        "protocol_version": "live-v1",
        "workspace_id": workspace_id,
        "scenario_id": "campus-directions",
        "correction_mode": "immersion",
        "speech_speed": "slow",
        "patience": "patient",
    }
    created = client.post("/api/v1/voice/sessions", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["session"]["protocol_version"] == "live-v1"
    assert body["session"]["skill_version"] == "0.3.0"
    assert body["session"]["requested_config"]["prompt_version"] == "live-v1"
    assert body["connection"]["capabilities"]["semantic_vad"] == "unsupported"
    update = body["connection"]["session_update"]["session"]
    assert update["turn_detection"] == {
        "type": "semantic_vad",
        "threshold": 0.5,
        "silence_duration_ms": 1400,
    }
    assert "通话中不要主动做语法纠错" in update["instructions"]
    assert "明显慢于自然会话" in update["instructions"]
    assert "辅助语言：English" in update["instructions"]
    assert "input_audio_transcription" not in update

    retried = client.post("/api/v1/voice/sessions", json=payload)
    assert retried.status_code == 200
    assert retried.json()["session"]["id"] == body["session"]["id"]

    conflict = client.post(
        "/api/v1/voice/sessions",
        json={**payload, "speech_speed": "normal"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"


def test_live_signal_requires_epoch_and_does_not_activate_before_browser_ack(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        QwenRealtimeProvider,
        "exchange_offer",
        lambda self, offer_sdp: "v=0\r\nmock-answer-sdp",
    )
    application = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'live-signal.sqlite3').as_posix()}",
            database_auto_create=True,
            dashscope_api_key="super-secret-api-key",
            dashscope_workspace_id="workspace-123",
        )
    )
    with TestClient(application) as configured_client:
        created = configured_client.post(
            "/api/v1/voice/sessions",
            json={
                "client_session_id": str(uuid4()),
                "protocol_version": "live-v1",
                "scenario_id": "campus-canteen",
            },
        ).json()
        session_id = created["session"]["id"]
        stale = configured_client.post(
            f"/api/v1/voice/sessions/{session_id}/offer",
            json={"sdp": "v=0\r\n" + "a" * 30, "connection_epoch": 2},
        )
        assert stale.status_code == 409

        offer = configured_client.post(
            f"/api/v1/voice/sessions/{session_id}/offer",
            json={"sdp": "v=0\r\n" + "a" * 30, "connection_epoch": 1},
        )
        assert offer.status_code == 200
        assert offer.json()["connection_epoch"] == 1
        connecting = configured_client.get(f"/api/v1/voice/sessions/{session_id}").json()
        assert connecting["status"] == "connecting"
        assert connecting["transport_status"] == "connecting"

        activated = configured_client.patch(
            f"/api/v1/voice/sessions/{session_id}/status",
            json={"status": "active", "connection_epoch": 1},
        )
        assert activated.status_code == 200
        assert activated.json()["status"] == "active"
        assert activated.json()["deadline_at"] is not None
    application.state.database.dispose()


def test_live_transcript_epoch_idempotency_playback_and_finalize_manifest(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/voice/sessions",
        json={
            "client_session_id": str(uuid4()),
            "protocol_version": "live-v1",
            "scenario_id": "campus-canteen",
        },
    ).json()
    session_id = created["session"]["id"]
    assert (
        client.patch(
            f"/api/v1/voice/sessions/{session_id}/status",
            json={"status": "active", "connection_epoch": 0},
        ).status_code
        == 200
    )

    assistant_payload = {
        "client_event_id": "assistant-live-1",
        "sequence_no": 1,
        "connection_epoch": 0,
        "provider_item_id": "item-assistant-1",
        "provider_response_id": "response-1",
        "speaker": "assistant",
        "transcript": "你好，请问你想吃什么？",
        "source": "provider",
        "is_final": True,
        "transcript_status": "final",
        "playback_status": "unknown",
    }
    saved = client.post(f"/api/v1/voice/sessions/{session_id}/utterances", json=assistant_payload)
    assert saved.status_code == 201
    duplicate = client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances", json=assistant_payload
    )
    assert duplicate.json()["id"] == saved.json()["id"]
    provider_duplicate = client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances",
        json={
            **assistant_payload,
            "client_event_id": "assistant-live-provider-retry",
            "sequence_no": 2,
        },
    )
    assert provider_duplicate.status_code == 201
    assert provider_duplicate.json()["id"] == saved.json()["id"]
    conflict = client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances",
        json={**assistant_payload, "transcript": "不同文字"},
    )
    assert conflict.status_code == 409

    playback = client.patch(
        f"/api/v1/voice/sessions/{session_id}/utterances/{saved.json()['id']}/playback",
        json={"connection_epoch": 0, "playback_status": "interrupted"},
    )
    assert playback.status_code == 200
    assert playback.json()["playback_status"] == "interrupted"
    transcript_replay = client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances", json=assistant_payload
    )
    assert transcript_replay.status_code == 201
    assert transcript_replay.json()["id"] == saved.json()["id"]
    assert transcript_replay.json()["playback_status"] == "interrupted"
    assert (
        client.patch(
            f"/api/v1/voice/sessions/{session_id}/utterances/{saved.json()['id']}/playback",
            json={"connection_epoch": 0, "playback_status": "completed"},
        ).status_code
        == 409
    )

    ending = client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={
            "status": "ending",
            "connection_epoch": 0,
            "end_reason": "user_ended",
            "closing_manifest": {"known_client_event_ids": ["assistant-live-1"]},
        },
    )
    assert ending.status_code == 200
    rejected_new = client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances",
        json={
            "client_event_id": "late-new-item",
            "sequence_no": 2,
            "connection_epoch": 0,
            "speaker": "user",
            "transcript": "太晚到达",
            "source": "provider",
        },
    )
    assert rejected_new.status_code == 409

    finalized = client.post(
        f"/api/v1/voice/sessions/{session_id}/finalize",
        json={
            "expected_utterances": [
                {
                    "client_event_id": "assistant-live-1",
                    "transcript_status": "final",
                    "playback_status": "interrupted",
                }
            ]
        },
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "completed"


def test_live_finalize_blocks_missing_transcript_until_explicitly_abandoned(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/voice/sessions",
        json={
            "client_session_id": str(uuid4()),
            "protocol_version": "live-v1",
            "scenario_id": "campus-directions",
        },
    ).json()
    session_id = created["session"]["id"]
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={"status": "active", "connection_epoch": 0},
    )
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={
            "status": "ending",
            "connection_epoch": 0,
            "end_reason": "user_ended",
            "closing_manifest": {"known_client_event_ids": ["missing-user-1"]},
        },
    )
    pending = client.post(
        f"/api/v1/voice/sessions/{session_id}/finalize",
        json={
            "expected_utterances": [
                {
                    "client_event_id": "missing-user-1",
                    "transcript_status": "final",
                    "playback_status": "not_applicable",
                }
            ]
        },
    )
    assert pending.status_code == 409
    assert pending.json()["detail"]["code"] == "transcript_pending"

    abandoned = client.post(
        f"/api/v1/voice/sessions/{session_id}/finalize",
        json={
            "allow_incomplete": True,
            "missing_client_event_ids": ["missing-user-1"],
        },
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["end_reason"] == "save_incomplete"


def test_live_session_can_restore_connection_contract(client: TestClient) -> None:
    created = client.post(
        "/api/v1/voice/sessions",
        json={
            "client_session_id": str(uuid4()),
            "protocol_version": "live-v1",
            "scenario_id": "campus-directions",
        },
    ).json()
    session_id = created["session"]["id"]

    resumed = client.post(f"/api/v1/voice/sessions/{session_id}/resume")

    assert resumed.status_code == 200
    assert resumed.json()["session"]["id"] == session_id
    assert resumed.json()["connection"]["mode"] == "mock"
    assert resumed.json()["connection"]["session_update"]["type"] == "session.update"


def test_stale_live_session_enters_recoverable_ending(client: TestClient) -> None:
    created = client.post(
        "/api/v1/voice/sessions",
        json={
            "client_session_id": str(uuid4()),
            "protocol_version": "live-v1",
            "scenario_id": "campus-directions",
        },
    ).json()
    session_id = created["session"]["id"]
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={"status": "active", "connection_epoch": 0},
    )
    saved = client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances",
        json={
            "client_event_id": "saved-before-timeout",
            "sequence_no": 1,
            "connection_epoch": 0,
            "speaker": "user",
            "transcript": "请问，图书馆怎么走？",
            "source": "browser_text",
        },
    )
    assert saved.status_code == 201

    observed_at = utc_now()
    with client.app.state.database.session_factory() as database_session:
        voice_session = database_session.scalar(
            select(VoiceSession).where(VoiceSession.id == session_id)
        )
        assert voice_session is not None
        voice_session.last_event_at = observed_at - timedelta(seconds=91)
        voice_session.deadline_at = observed_at + timedelta(minutes=5)
        database_session.commit()
        assert sweep_stale_voice_sessions(database_session, observed_at) == 1

    restored = client.get(f"/api/v1/voice/sessions/{session_id}").json()
    assert restored["status"] == "ending"
    assert restored["end_reason"] == "client_abandoned"
    assert restored["closing_manifest"]["known_client_event_ids"] == ["saved-before-timeout"]
    events = client.get(f"/api/v1/voice/sessions/{session_id}/events").json()
    assert events[-1]["event_type"] == "session_timeout"

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.providers.summary import DeepSeekSummaryProvider, SummaryRequest


def _complete_session(
    client: TestClient,
    learner_text: str,
    *,
    learner_id: str | None = None,
) -> str:
    headers = {"X-Learner-ID": learner_id} if learner_id else {}
    created = client.post(
        "/api/v1/voice/sessions",
        headers=headers,
        json={"scenario_id": "campus-canteen"},
    )
    assert created.status_code == 201
    session_id = created.json()["session"]["id"]
    assert (
        client.patch(
            f"/api/v1/voice/sessions/{session_id}/status",
            headers=headers,
            json={"status": "active"},
        ).status_code
        == 200
    )
    utterances = [
        ("user", learner_text, "browser_text"),
        ("assistant", "好的，还需要什么？", "mock"),
        ("user", "谢谢，就这些。", "browser_text"),
    ]
    for sequence_no, (speaker, transcript, source) in enumerate(utterances, start=1):
        response = client.post(
            f"/api/v1/voice/sessions/{session_id}/utterances",
            headers=headers,
            json={
                "client_event_id": f"turn-{sequence_no}",
                "sequence_no": sequence_no,
                "speaker": speaker,
                "transcript": transcript,
                "source": source,
            },
        )
        assert response.status_code == 201
    assert (
        client.post(
            f"/api/v1/voice/sessions/{session_id}/finalize",
            headers=headers,
            json={"duration_seconds": 38},
        ).status_code
        == 200
    )
    return session_id


def test_summary_candidate_is_idempotent_and_requires_user_confirmation(
    client: TestClient,
) -> None:
    session_id = _complete_session(client, "我有三个人朋友。")
    generated = client.post(f"/api/v1/voice/sessions/{session_id}/summary")
    assert generated.status_code == 201
    body = generated.json()
    assert body["provider"] == "local"
    assert body["model"] == "rule-summary-v1"
    assert body["task_status"] == "completed"
    assert len(body["candidate_errors"]) == 1
    candidate = body["candidate_errors"][0]
    assert candidate["status"] == "candidate"
    assert candidate["learner_text"] == "三个人朋友"
    assert candidate["corrected_text"] == "三个朋友"
    assert candidate["canonical_key"] == "lexical:measure-word:朋友:个"

    repeated = client.post(f"/api/v1/voice/sessions/{session_id}/summary")
    assert repeated.status_code == 201
    assert repeated.json()["id"] == body["id"]
    assert len(client.get("/api/v1/error-clusters").json()) == 0

    confirmed = client.patch(
        f"/api/v1/errors/{candidate['id']}", json={"status": "confirmed"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    clusters = client.get("/api/v1/error-clusters").json()
    assert len(clusters) == 1
    assert clusters[0]["occurrence_count"] == 1
    assert clusters[0]["corrected_example"] == "三个朋友"


def test_incomplete_live_transcript_is_not_used_as_learning_evidence(
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
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={"status": "active", "connection_epoch": 0},
    )
    client.post(
        f"/api/v1/voice/sessions/{session_id}/utterances",
        json={
            "client_event_id": "uncertain-user-1",
            "sequence_no": 1,
            "connection_epoch": 0,
            "speaker": "user",
            "transcript": "我有三个人朋友",
            "source": "provider",
            "is_final": False,
            "transcript_status": "incomplete",
        },
    )
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={
            "status": "ending",
            "connection_epoch": 0,
            "end_reason": "save_incomplete",
            "closing_manifest": {"known_client_event_ids": ["uncertain-user-1"]},
        },
    )
    finalized = client.post(
        f"/api/v1/voice/sessions/{session_id}/finalize",
        json={
            "allow_incomplete": True,
            "expected_utterances": [
                {
                    "client_event_id": "uncertain-user-1",
                    "transcript_status": "incomplete",
                    "playback_status": "not_applicable",
                }
            ],
        },
    )
    assert finalized.status_code == 200

    summary = client.post(f"/api/v1/voice/sessions/{session_id}/summary")
    assert summary.status_code == 409
    assert summary.json()["detail"]["code"] == "no_reliable_transcript"


def test_confirmed_error_is_recalled_and_archiving_removes_it(client: TestClient) -> None:
    session_id = _complete_session(client, "给我一个水。")
    summary = client.post(f"/api/v1/voice/sessions/{session_id}/summary").json()
    event_id = summary["candidate_errors"][0]["id"]
    assert (
        client.patch(f"/api/v1/errors/{event_id}", json={"status": "confirmed"}).status_code
        == 200
    )

    repeated_session_id = _complete_session(client, "给我一个水。")
    repeated_summary = client.post(
        f"/api/v1/voice/sessions/{repeated_session_id}/summary"
    ).json()
    repeated_event_id = repeated_summary["candidate_errors"][0]["id"]
    assert (
        client.patch(
            f"/api/v1/errors/{repeated_event_id}", json={"status": "confirmed"}
        ).status_code
        == 200
    )

    recalled = client.post(
        "/api/v1/voice/sessions", json={"scenario_id": "convenience-store"}
    ).json()
    memory = recalled["session"]["context_pack"]["confirmed_errors"]
    assert len(memory) == 1
    assert memory[0]["corrected_example"] == "给我一瓶水"
    assert memory[0]["occurrence_count"] == 2
    assert "给我一瓶水" in recalled["connection"]["session_update"]["session"]["instructions"]

    cluster_id = memory[0]["id"]
    assert client.delete(f"/api/v1/error-clusters/{cluster_id}").status_code == 204
    after_archive = client.post(
        "/api/v1/voice/sessions", json={"scenario_id": "convenience-store"}
    ).json()
    assert after_archive["session"]["context_pack"]["confirmed_errors"] == []


def test_rejected_error_never_enters_memory(client: TestClient) -> None:
    session_id = _complete_session(client, "我把书看了完。")
    summary = client.post(f"/api/v1/voice/sessions/{session_id}/summary").json()
    event_id = summary["candidate_errors"][0]["id"]
    rejected = client.patch(f"/api/v1/errors/{event_id}", json={"status": "rejected"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get("/api/v1/error-clusters").json() == []
    assert (
        client.patch(f"/api/v1/errors/{event_id}", json={"status": "confirmed"}).status_code
        == 409
    )


def test_learning_memory_is_scoped_to_owner(client: TestClient) -> None:
    owner = str(uuid4())
    other = str(uuid4())
    session_id = _complete_session(client, "我有三个人朋友。", learner_id=owner)
    owner_headers = {"X-Learner-ID": owner}
    other_headers = {"X-Learner-ID": other}
    summary = client.post(
        f"/api/v1/voice/sessions/{session_id}/summary", headers=owner_headers
    ).json()
    event_id = summary["candidate_errors"][0]["id"]

    assert (
        client.get(
            f"/api/v1/voice/sessions/{session_id}/summary", headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/errors/{event_id}",
            headers=other_headers,
            json={"status": "confirmed"},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/errors", headers=other_headers).json() == []


def test_learner_can_correct_but_not_cross_edit_confirmed_memory(
    client: TestClient,
) -> None:
    owner = str(uuid4())
    other = str(uuid4())
    owner_headers = {"X-Learner-ID": owner}
    session_id = _complete_session(client, "给我一个水。", learner_id=owner)
    summary = client.post(
        f"/api/v1/voice/sessions/{session_id}/summary", headers=owner_headers
    ).json()
    client.patch(
        f"/api/v1/errors/{summary['candidate_errors'][0]['id']}",
        headers=owner_headers,
        json={"status": "confirmed"},
    )
    cluster = client.get("/api/v1/error-clusters", headers=owner_headers).json()[0]

    updated = client.patch(
        f"/api/v1/error-clusters/{cluster['id']}",
        headers=owner_headers,
        json={
            "explanation": "我想记住：液体前面要用容器量词。",
            "corrected_example": "麻烦给我一瓶水。",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["corrected_example"] == "麻烦给我一瓶水。"
    assert (
        client.patch(
            f"/api/v1/error-clusters/{cluster['id']}",
            headers={"X-Learner-ID": other},
            json={"explanation": "不能改", "corrected_example": "不能改"},
        ).status_code
        == 404
    )


def test_deepseek_json_request_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}
    now = datetime.now(UTC).isoformat()
    response_payload = {
        "session_id": "model-value-is-overridden",
        "task_result": {"status": "completed", "explanation": "完成了任务。"},
        "highlights": ["完成了两轮表达"],
        "candidate_errors": [
            {
                "source_type": "conversation",
                "source_id": "model-value-is-overridden",
                "learner_text": "给我一个水",
                "corrected_text": "给我一瓶水",
                "explanation": "使用容器量词。",
                "error_type": "lexical",
                "subtype": "measure-word",
                "severity": "major",
                "confidence": 0.96,
                "status": "candidate",
                "evidence_span": "给我一个水",
                "canonical_key": "lexical:measure-word:水:瓶",
                "hsk_tags": ["HSK2"],
                "observed_at": now,
                "model_version": "model-value-is-overridden",
                "skill_version": "model-value-is-overridden",
            },
            {
                "source_type": "conversation",
                "source_id": "model-value-is-overridden",
                "learner_text": "水",
                "corrected_text": "水",
                "explanation": "模型不应仅凭转写判断发音。",
                "error_type": "pronunciation",
                "subtype": "tone",
                "severity": "minor",
                "confidence": 0.8,
                "status": "candidate",
                "evidence_span": "水",
                "canonical_key": "pronunciation:tone:水",
                "hsk_tags": ["HSK1"],
                "observed_at": now,
                "model_version": "model-value-is-overridden",
                "skill_version": "model-value-is-overridden",
            },
        ],
        "next_step": "练习一瓶水。",
        "model_version": "model-value-is-overridden",
        "skill_version": "model-value-is-overridden",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(response_payload)}}]}
            ).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.providers.summary.urlopen", fake_urlopen)
    provider = DeepSeekSummaryProvider(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
            deepseek_api_key="secret-deepseek-key",
            # 显式钉住模型名，避免本地 .env 泄漏进合同断言
            deepseek_default_model="deepseek-v4-flash",
        )
    )
    result = provider.generate(
        SummaryRequest(
            session_id="session-123",
            objective="便利店买水",
            learner_profile={"estimated_hsk_band": "HSK2"},
            utterances=[{"speaker": "user", "text": "给我一个水"}],
            recalled_errors=[],
            skill_version="0.1.0",
        )
    )

    sent_request = captured["request"]
    sent = json.loads(sent_request.data.decode())
    assert sent["model"] == "deepseek-v4-flash"
    assert sent["thinking"] == {"type": "disabled"}
    assert sent["response_format"] == {"type": "json_object"}
    assert "json" in sent["messages"][1]["content"].lower()
    assert sent_request.headers["Authorization"] == "Bearer secret-deepseek-key"
    assert result.session_id == "session-123"
    assert result.model_version == "deepseek-v4-flash"
    assert result.candidate_errors[0].source_id == "session-123"
    assert len(result.candidate_errors) == 1
    assert "secret-deepseek-key" not in result.model_dump_json()

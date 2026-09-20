from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models import Utterance, VoiceSession, utc_now
from app.realtime.lifecycle import sweep_stale_voice_sessions
from app.realtime.memory import MEMORY_CHAR_BUDGET, build_memory, render_markdown


def create(client, continuous=True):
    response = client.post(
        "/api/v1/voice/sessions",
        json={
            "protocol_version": "live-v1",
            "client_session_id": str(uuid4()),
            "practice_mode": "custom",
            "custom_objective": "练习租房",
            "continuous": continuous,
        },
    )
    assert response.status_code == 201
    session_id = response.json()["session"]["id"]
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={"status": "active", "connection_epoch": 0},
    )
    return session_id


@pytest.mark.parametrize("continuous,expected", [(True, 0), (False, 1)])
def test_deadline_and_abandonment(client, continuous, expected):
    session_id = create(client, continuous)
    now = utc_now()
    with client.app.state.database.session_factory() as db:
        session = db.get(VoiceSession, session_id)
        session.deadline_at = now - timedelta(seconds=1)
        session.last_event_at = now
        db.commit()
        assert sweep_stale_voice_sessions(db, now) == expected
        if continuous:
            assert sweep_stale_voice_sessions(db, now + timedelta(seconds=91)) == 1
            assert session.end_reason == "client_abandoned"


@pytest.mark.parametrize("continuous,expected", [(True, 1500), (False, 480)])
def test_long_finalize_duration(client, continuous, expected):
    session_id = create(client, continuous)
    now = utc_now()
    client.patch(
        f"/api/v1/voice/sessions/{session_id}/status",
        json={"status": "ending", "closing_manifest": {"known_client_event_ids": []}},
    )
    with client.app.state.database.session_factory() as db:
        session = db.get(VoiceSession, session_id)
        session.started_at = now - timedelta(seconds=1500)
        session.ending_at = now
        db.commit()
    result = client.post(
        f"/api/v1/voice/sessions/{session_id}/finalize", json={"expected_utterances": []}
    )
    assert result.status_code == 200
    assert result.json()["duration_seconds"] == expected


def test_three_restores_persist_history_and_export_owner(client):
    session_id = create(client)
    base = f"/api/v1/voice/sessions/{session_id}"
    for index in range(1, 4):
        result = client.post(
            base + "/utterances",
            json={
                "client_event_id": f"turn-{index}",
                "sequence_no": index,
                "connection_epoch": 0,
                "speaker": "user",
                "transcript": f"第{index}条：预算三千元<script> [link](evil)",
                "source": "browser_text",
            },
        )
        assert result.status_code == 201
        restored = client.post(base + "/resume").json()
        memory = restored["session"]["context_pack"]["conversation_memory"]
        assert memory["through_sequence"] == index
        assert "第1条" in memory["text"]
        assert "预算三千元" in restored["connection"]["session_update"]["session"]["instructions"]
        assert "练习租房" in restored["connection"]["session_update"]["session"]["instructions"]
    exported = client.get(base + "/transcript.md")
    assert exported.status_code == 200
    assert "&lt;script&gt;" in exported.text
    assert "attachment" in exported.headers["content-disposition"]
    assert client.get(
        base + "/transcript.md", headers={"X-Learner-ID": str(uuid4())}
    ).status_code in (403, 404)


def test_bounded_memory_has_attribution_and_no_broken_lines():
    items = [
        SimpleNamespace(
            id=str(i),
            sequence_no=i,
            connection_epoch=i // 10,
            is_final=True,
            transcript_status="final",
            speaker="user" if i % 2 else "assistant",
            playback_status="interrupted",
            transcript=(f"原话{i}" + "中" * 1000),
        )
        for i in range(1, 201)
    ]
    items.append(
        SimpleNamespace(is_final=False, transcript_status="incomplete", transcript="不能注入")
    )
    session = SimpleNamespace(id="test", context_pack={}, utterances=items)
    memory = build_memory(session)
    assert len(memory["text"]) <= MEMORY_CHAR_BUDGET
    assert "原话1" in memory["text"]
    assert "不能注入" not in memory["text"]
    assert "未独立核实" in memory["text"]
    assert "不能假定用户已听完" in memory["text"]
    assert memory["has_omissions"]
    assert memory["through_sequence"] == 200
    assert all(
        line.startswith(("段", "消息", "较早", "最近")) for line in memory["text"].splitlines()
    )


def test_markdown_multiline_text_stays_quoted():
    session = SimpleNamespace(
        id="test",
        context_pack={},
        utterances=[
            SimpleNamespace(
                connection_epoch=1,
                sequence_no=1,
                speaker="user",
                transcript_status="final",
                playback_status="not_applicable",
                transcript="第一行\n# 标题\n<script>\n[链接](javascript:bad)",
            )
        ],
    )
    result = render_markdown(session)
    assert "> # 标题" in result
    assert "> &lt;script&gt;" in result
    assert "> \\[链接]" in result


def test_large_saved_history_needs_no_full_closing_manifest(client):
    session_id = create(client)
    with client.app.state.database.session_factory() as db:
        db.add_all(
            [
                Utterance(
                    session_id=session_id,
                    client_event_id=f"saved-{i:06}-" + "x" * 55,
                    sequence_no=i,
                    speaker="user",
                    transcript="已保存的历史",
                    source="browser_text",
                )
                for i in range(1, 1201)
            ]
        )
        db.commit()
    base = f"/api/v1/voice/sessions/{session_id}"
    ending = client.patch(
        base + "/status",
        json={"status": "ending", "closing_manifest": {"known_client_event_ids": []}},
    )
    assert ending.status_code == 200
    done = client.post(base + "/finalize", json={"expected_utterances": []})
    assert done.status_code == 200
    assert len(done.json()["utterances"]) == 1200

import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import SessionEvent, VoiceSession
from app.realtime.tools import lookup_hsk, result


def active_session(client):
    created = client.post("/api/v1/voice/sessions", json={"scenario": "中文学习"})
    assert created.status_code == 201
    session_id = created.json()["session"]["id"]
    response = client.patch(
        f"/api/v1/voice/sessions/{session_id}/status", json={"status": "active"}
    )
    assert response.status_code == 200
    return session_id


def call_body(**overrides):
    return {
        "connection_epoch": 0,
        "response_id": "resp-1",
        "call_id": "call-1",
        "name": "hsk_lookup",
        "arguments": json.dumps({"query": "把字句"}),
        **overrides,
    }


def test_hsk_sources_and_no_match():
    output = lookup_hsk("把字句和结果补语")
    assert output["sources"][0]["title"] == "把字句"
    assert output["sources"][0]["version"] == "hsk-kb-v2"
    assert output["sources"][0]["kind"] == "grammar"
    assert "考纲知识库" in output["message"]
    assert lookup_hsk("zzzxxyy")["status"] == "no_results"
    assert lookup_hsk("把")["status"] == "succeeded"


def test_authorization_dedup_conflict_and_config(client, monkeypatch):
    session_id = active_session(client)
    endpoint = f"/api/v1/voice/sessions/{session_id}/tools"
    denied = client.post(
        endpoint + "/execute", json=call_body(), headers={"X-Learner-ID": str(uuid4())}
    )
    assert denied.status_code == 404
    calls = []

    def execute(*args):
        calls.append(args)
        return result("succeeded", "测试结果")

    monkeypatch.setattr("app.routes.tools.execute_tool", execute)
    first = client.post(endpoint + "/execute", json=call_body())
    assert first.json()["status"] == "succeeded"
    assert client.post(endpoint + "/execute", json=call_body()).json() == first.json()
    assert len(calls) == 1
    assert (
        client.post(endpoint + "/execute", json=call_body(arguments='{"query":"比"}')).status_code
        == 409
    )
    assert client.post(endpoint + "/execute", json=call_body(connection_epoch=9)).status_code == 409
    available = client.get(endpoint).json()["tools"]
    assert [item["available"] for item in available] == [True, False, False]


@pytest.mark.parametrize("arguments", ['{"query":" "}', '{"query":"把","url":"http://x"}', "bad"])
def test_argument_validation(client, arguments):
    session_id = active_session(client)
    output = client.post(
        f"/api/v1/voice/sessions/{session_id}/tools/execute", json=call_body(arguments=arguments)
    )
    assert output.json()["status"] == "failed"


def test_missing_services_never_fabricate(client):
    session_id = active_session(client)
    for name in ("web_search", "expert_answer"):
        output = client.post(
            f"/api/v1/voice/sessions/{session_id}/tools/execute",
            json=call_body(name=name, call_id=name),
        ).json()
        assert output["status"] == "unavailable"
        assert output["sources"] == []


@pytest.mark.parametrize("change", ["cancel", "epoch", "end"])
def test_inflight_old_result_discarded(client, monkeypatch, change):
    session_id = active_session(client)
    endpoint = f"/api/v1/voice/sessions/{session_id}/tools"
    started, release = Event(), Event()

    def slow(*args):
        started.set()
        assert release.wait(5)
        return result("succeeded", "此结果不该返回")

    monkeypatch.setattr("app.routes.tools.execute_tool", slow)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(client.post, endpoint + "/execute", json=call_body())
        assert started.wait(5)
        if change == "cancel":
            assert (
                client.post(
                    endpoint + "/cancel", json={"connection_epoch": 0, "response_id": "resp-1"}
                ).status_code
                == 200
            )
        else:
            with client.app.state.database.session_factory() as db:
                voice = db.get(VoiceSession, session_id)
                if change == "epoch":
                    voice.connection_epoch = 1
                else:
                    voice.status = "ending"
                db.commit()
        release.set()
        assert future.result().json()["status"] == "cancelled"
    with client.app.state.database.session_factory() as db:
        event = db.scalar(select(SessionEvent).where(SessionEvent.event_type == "tool_local"))
        assert event.event_payload["result"]["status"] == "cancelled"


def test_timeout_and_cancel_before_start(client, monkeypatch):
    session_id = active_session(client)
    endpoint = f"/api/v1/voice/sessions/{session_id}/tools"
    client.app.state.settings.tool_timeout_seconds = 1

    def slow(*args):
        time.sleep(1.1)
        return result("succeeded", "too late")

    monkeypatch.setattr("app.routes.tools.execute_tool", slow)
    assert client.post(endpoint + "/execute", json=call_body()).json()["status"] == "failed"
    scope = {"connection_epoch": 0, "response_id": "cancel-first"}
    client.post(endpoint + "/cancel", json=scope)
    assert (
        client.post(endpoint + "/execute", json=call_body(**scope)).json()["status"] == "cancelled"
    )


def test_provider_failure_hides_details(client, monkeypatch):
    session_id = active_session(client)

    def fail(*args):
        raise RuntimeError("secret-key")

    monkeypatch.setattr("app.routes.tools.execute_tool", fail)
    response = client.post(f"/api/v1/voice/sessions/{session_id}/tools/execute", json=call_body())
    assert response.json()["status"] == "failed"
    assert "secret-key" not in response.text


def test_external_budget_and_dedup_do_not_spend_twice(client, monkeypatch):
    session_id = active_session(client)
    endpoint = f"/api/v1/voice/sessions/{session_id}/tools/execute"
    client.app.state.settings.tool_external_session_limit = 1
    calls = []

    def execute(*args):
        calls.append(args)
        return result("succeeded", "test")

    monkeypatch.setattr("app.routes.tools.execute_tool", execute)
    body = call_body(name="web_search")
    first = client.post(endpoint, json=body).json()
    assert first["status"] == "succeeded"
    assert client.post(endpoint, json=body).json() == first
    assert (
        client.post(endpoint, json={**body, "call_id": "second"}).json()["status"] == "unavailable"
    )
    assert len(calls) == 1


def test_adapters_preserve_evidence_and_model_limitations(monkeypatch):
    from app.config import Settings
    from app.realtime.tools import ToolArguments, execute_tool

    settings = Settings(_env_file=None, tavily_api_key="test", deepseek_api_key="test")
    requests = []

    def post(endpoint, key, payload, timeout):
        requests.append(payload)
        if "tavily" in endpoint:
            return {
                "results": [
                    {"title": "Source", "url": "https://example.com", "content": "Evidence"}
                ]
            }
        return {"choices": [{"message": {"content": "解释与例句"}}]}

    monkeypatch.setattr("app.realtime.tools.post_json", post)
    search = execute_tool("web_search", ToolArguments(query="版本"), settings)
    assert search["sources"][0]["url"] == "https://example.com"
    assert requests[0]["include_answer"] is False
    answer = execute_tool("expert_answer", ToolArguments(query="把字句"), settings)
    assert answer["evidence_kind"] == "unverified_model_answer"
    # 推理模型思维链计入 max_tokens，4000 为思维链+回答留出余量
    assert requests[1]["max_tokens"] == 4000

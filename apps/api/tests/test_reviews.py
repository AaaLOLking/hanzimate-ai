from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fsrs import Card, Rating, Scheduler
from sqlalchemy import func, select
from test_learning_memory import _complete_session

from app.models import ErrorCluster, ReviewAttempt, ReviewCard, ReviewLog, ReviewReminder
from app.review_schemas import ReviewPreferencesInput
from app.reviews import as_utc, backfill_review_cards, enqueue_due_reminders, planned_due


def confirmed_card(client, *, owner=None, text="给我一个水。"):
    headers = {"X-Learner-ID": owner} if owner else {}
    session_id = _complete_session(client, text, learner_id=owner)
    report = client.post(f"/api/v1/voice/sessions/{session_id}/summary", headers=headers).json()
    event_id = report["candidate_errors"][0]["id"]
    result = client.patch(
        f"/api/v1/errors/{event_id}", headers=headers, json={"status": "confirmed"}
    )
    assert result.status_code == 200
    cards = client.get("/api/v1/reviews", headers=headers).json()["cards"]
    return cards[0], headers


def attempt_card(client, card, headers=None, response="请给我两瓶水。", request_id=None):
    return client.post(
        f"/api/v1/reviews/{card['id']}/attempts",
        headers=headers or {},
        json={
            "request_id": request_id or str(uuid4()),
            "card_revision": card["revision"],
            "response": response,
        },
    )


def rate(client, attempt, rating="good", headers=None):
    return client.post(
        f"/api/v1/review-attempts/{attempt['id']}/rating",
        headers=headers or {},
        json={"rating": rating},
    )


def test_only_confirmed_errors_create_one_card_and_backfill_is_idempotent(client):
    session_id = _complete_session(client, "给我一个水。")
    report = client.post(f"/api/v1/voice/sessions/{session_id}/summary").json()
    assert client.get("/api/v1/reviews").json()["active_count"] == 0
    event_id = report["candidate_errors"][0]["id"]
    for _ in range(2):
        assert (
            client.patch(f"/api/v1/errors/{event_id}", json={"status": "confirmed"}).status_code
            == 200
        )
    with client.app.state.database.session_factory() as session:
        backfill_review_cards(session)
        assert session.scalar(select(func.count(ReviewCard.id))) == 1
    assert client.get("/api/v1/reviews").json()["due_count"] == 1


def test_answer_gate_pending_restore_idempotency_and_replay(client):
    card, _ = confirmed_card(client)
    public = client.get("/api/v1/reviews").text
    for private_key in ["reference_answer", "fsrs_state", '"pattern"', "两瓶水"]:
        assert private_key not in public
    request_id = str(uuid4())
    first = attempt_card(client, card, request_id=request_id)
    assert first.status_code == 201
    attempt = first.json()
    assert attempt["rule_matched"] is True
    assert "两瓶水" in attempt["reference_answer"]
    assert attempt_card(client, card, request_id=request_id).json()["id"] == attempt["id"]
    assert attempt_card(client, card, request_id=request_id, response="不同答案").status_code == 409
    assert attempt_card(client, card).status_code == 409
    restored = client.get("/api/v1/reviews").json()
    assert restored["cards"][0]["pending_attempt"]["id"] == attempt["id"]
    assert restored["reviewed_today"] == 0
    saved = rate(client, attempt)
    assert saved.status_code == 200
    assert rate(client, attempt).json()["id"] == saved.json()["id"]
    assert rate(client, attempt, "easy").status_code == 409
    assert attempt_card(client, card).status_code == 409
    dashboard = client.get("/api/v1/reviews").json()
    assert dashboard["due_count"] == 0
    assert dashboard["reviewed_today"] == 1
    assert dashboard["upcoming"][0]["pending_attempt"] is None
    assert (
        client.get("/api/v1/error-clusters").json()[0]["next_review_at"] == saved.json()["due_at"]
    )
    with client.app.state.database.session_factory() as session:
        log = session.scalar(select(ReviewLog))
        scheduler = Scheduler.from_dict(log.scheduler_config["scheduler"])
        replay, _ = scheduler.review_card(
            Card.from_dict(log.before_state), Rating.Good, review_datetime=as_utc(log.reviewed_at)
        )
        assert replay.to_dict() == log.after_state
        assert session.scalar(select(func.count(ReviewLog.id))) == 1


@pytest.mark.parametrize("rating", ["again", "hard", "good", "easy"])
def test_all_four_self_ratings_are_preserved_even_when_rule_does_not_match(client, rating):
    card, _ = confirmed_card(client)
    attempt = attempt_card(client, card, response="不会").json()
    assert attempt["rule_matched"] is False
    result = rate(client, attempt, rating)
    assert result.status_code == 200
    assert result.json()["rating"] == rating
    assert datetime.fromisoformat(result.json()["due_at"]) > datetime.now(UTC)


def test_next_revision_changes_scenario_and_restores_pending_after_prior_logs(client):
    card, _ = confirmed_card(client)
    first = attempt_card(client, card).json()
    assert rate(client, first).status_code == 200
    with client.app.state.database.session_factory() as session:
        saved_card = session.get(ReviewCard, card["id"])
        saved_card.due_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    next_card = client.get("/api/v1/reviews").json()["cards"][0]
    assert next_card["revision"] == 1
    assert next_card["prompt"] != card["prompt"]
    second = attempt_card(client, next_card, response="请给我三瓶水").json()
    pending = client.get("/api/v1/reviews").json()["cards"][0]["pending_attempt"]
    assert pending["id"] == second["id"]
    assert pending["rule_matched"] is True
    assert rate(client, second).status_code == 200


def test_reviews_are_owner_scoped_including_attempts_preferences_and_logs(client):
    owner, stranger = str(uuid4()), str(uuid4())
    card, headers = confirmed_card(client, owner=owner)
    other = {"X-Learner-ID": stranger}
    assert client.get("/api/v1/reviews", headers=other).json()["active_count"] == 0
    assert attempt_card(client, card, headers=other).status_code == 404
    attempt = attempt_card(client, card, headers=headers).json()
    assert rate(client, attempt, headers=other).status_code == 404
    assert rate(client, attempt, headers=headers).status_code == 200
    assert client.get("/api/v1/reviews", headers=other).json()["history"] == []
    preferences = ReviewPreferencesInput(schedule_mode="fixed", fixed_interval_days=9).model_dump()
    client.put("/api/v1/review-preferences", headers=headers, json=preferences)
    assert (
        client.get("/api/v1/review-preferences", headers=other).json()["schedule_mode"]
        == "adaptive"
    )


def test_archive_blocks_pending_rating_and_resume_does_not_reuse_revealed_answer(client):
    card, _ = confirmed_card(client)
    attempt = attempt_card(client, card).json()
    assert client.delete(f"/api/v1/error-clusters/{card['error_cluster_id']}").status_code == 204
    assert client.get("/api/v1/reviews").json()["due_count"] == 0
    assert rate(client, attempt).status_code == 404
    resumed, _ = confirmed_card(client)
    assert resumed["id"] == card["id"]
    assert resumed["revision"] == 1
    assert resumed["pending_attempt"] is None
    assert rate(client, attempt).status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        {"study_days": []},
        {"study_days": [1, 1]},
        {"study_days": [7]},
        {"timezone": "not/a-zone"},
        {"reminder_time": "25:70"},
        {"desired_retention": 1},
        {"fixed_interval_days": 0},
        {"fixed_interval_days": 61},
    ],
)
def test_invalid_preferences_are_rejected(client, change):
    data = ReviewPreferencesInput().model_dump() | change
    assert client.put("/api/v1/review-preferences", json=data).status_code == 422


def test_fixed_interval_and_availability_dont_rewrite_already_due_cards(client):
    card, _ = confirmed_card(client)
    preferences = ReviewPreferencesInput(schedule_mode="fixed", fixed_interval_days=6).model_dump()
    assert client.put("/api/v1/review-preferences", json=preferences).status_code == 200
    assert client.get("/api/v1/reviews").json()["cards"][0]["due_at"] == card["due_at"]
    result = rate(client, attempt_card(client, card).json()).json()
    reviewed = datetime.fromisoformat(result["reviewed_at"])
    assert datetime.fromisoformat(result["due_at"]) - reviewed == timedelta(days=6)


def test_calendar_crosses_week_boundary_and_dst_without_moving_earlier():
    preferences = ReviewPreferencesInput(timezone="America/New_York", study_days=[0])
    # Sunday at 09:00 after the autumn DST change -> Monday 09:00, not midnight.
    raw = datetime(2026, 11, 1, 14, tzinfo=UTC)
    due = planned_due(raw, raw - timedelta(days=3), "good", preferences)
    assert due == datetime(2026, 11, 2, 14, tzinfo=UTC)
    preferences = ReviewPreferencesInput(schedule_mode="fixed", fixed_interval_days=10)
    now = datetime(2026, 8, 31, 6, tzinfo=UTC)
    assert planned_due(now + timedelta(days=8), now, "again", preferences) == now + timedelta(
        days=1
    )


def test_reminder_time_opt_in_daily_dedup_dismissal_and_archive(client, monkeypatch):
    card, _ = confirmed_card(client)
    local_monday = datetime(2026, 9, 7, 11, tzinfo=UTC)  # 19:00 Shanghai
    with client.app.state.database.session_factory() as session:
        session.get(ReviewCard, card["id"]).due_at = local_monday - timedelta(days=1)
        session.commit()
        assert enqueue_due_reminders(session, local_monday) == 0  # opt-in required
    preferences = ReviewPreferencesInput(reminder_enabled=True, study_days=[0]).model_dump()
    assert client.put("/api/v1/review-preferences", json=preferences).status_code == 200
    with client.app.state.database.session_factory() as session:
        assert enqueue_due_reminders(session, local_monday - timedelta(minutes=1)) == 0
        assert enqueue_due_reminders(session, local_monday) == 1
        assert enqueue_due_reminders(session, local_monday + timedelta(minutes=1)) == 0
        assert enqueue_due_reminders(session, local_monday + timedelta(days=1)) == 0
    monkeypatch.setattr("app.routes.reviews.utc_now", lambda: local_monday)
    reminder = client.get("/api/v1/reviews").json()["reminder"]
    assert reminder["due_count"] == 1
    other = {"X-Learner-ID": str(uuid4())}
    path = f"/api/v1/review-reminders/{reminder['id']}/dismiss"
    assert client.patch(path, headers=other).status_code == 404
    assert client.patch(path).status_code == 204
    assert client.patch(path).status_code == 204
    assert client.get("/api/v1/reviews").json()["reminder"] is None
    client.delete(f"/api/v1/error-clusters/{card['error_cluster_id']}")
    with client.app.state.database.session_factory() as session:
        assert enqueue_due_reminders(session, local_monday + timedelta(days=7)) == 0
        assert session.scalar(select(func.count(ReviewReminder.id))) == 1


def test_empty_answer_cannot_reveal_reference_and_unknown_pattern_is_self_review(client):
    card, _ = confirmed_card(client)
    assert attempt_card(client, card, response="   ").status_code == 422
    with client.app.state.database.session_factory() as session:
        assert session.scalar(select(func.count(ReviewAttempt.id))) == 0
        cluster = session.get(ErrorCluster, card["error_cluster_id"])
        cluster.canonical_key = "pragmatics:custom"
        session.commit()
    attempt = attempt_card(client, card, response="麻烦您帮我一下。").json()
    assert attempt["rule_matched"] is None
    assert "暂不自动判分" in attempt["feedback"]


def test_legacy_confirmed_memory_is_backfilled_without_changing_evidence(client):
    # This simulates a pre-Week-8 row; normal confirmations already create cards.
    client.get("/api/v1/onboarding")
    user_id = client.app.state.settings.demo_user_id
    with client.app.state.database.session_factory() as session:
        cluster = ErrorCluster(
            user_id=user_id,
            canonical_key="legacy",
            error_type="grammar",
            subtype="legacy",
            explanation="历史记录",
            corrected_example="原句",
        )
        session.add(cluster)
        session.commit()
        cluster_id = cluster.id
        backfill_review_cards(session)
        backfill_review_cards(session)
        assert session.scalar(select(func.count(ReviewCard.id))) == 1
        assert session.get(ErrorCluster, cluster_id).corrected_example == "原句"

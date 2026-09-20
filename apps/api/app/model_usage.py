from __future__ import annotations

import json
from datetime import UTC, datetime, time
from time import perf_counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ModelRun, utc_now


def estimate_tokens(value: Any) -> int:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return max(1, (len(text) + 1) // 2)


def start_timer() -> float:
    return perf_counter()


def elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def estimate_cost_yuan(
    settings: Settings,
    provider: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    if provider != "deepseek":
        return 0.0
    total = (
        input_tokens * settings.deepseek_input_price_yuan_per_million_tokens
        + output_tokens * settings.deepseek_output_price_yuan_per_million_tokens
    ) / 1_000_000
    return round(total, 6)


def model_budget_block_reason(
    session: Session,
    user_id: str,
    provider: str,
    settings: Settings,
    *,
    reserved_input_tokens: int,
    reserved_output_tokens: int,
) -> str | None:
    if provider == "local":
        return None

    day_start = datetime.combine(utc_now().date(), time.min, tzinfo=UTC)
    external_calls = session.scalar(
        select(func.count(ModelRun.id)).where(
            ModelRun.user_id == user_id,
            ModelRun.provider != "local",
            ModelRun.status != "blocked",
            ModelRun.created_at >= day_start,
        )
    )
    if int(external_calls or 0) >= settings.model_daily_external_call_limit:
        return "daily_call_limit"

    spent = session.scalar(
        select(func.coalesce(func.sum(ModelRun.estimated_cost_yuan), 0.0)).where(
            ModelRun.user_id == user_id,
            ModelRun.created_at >= day_start,
        )
    )
    reserved = estimate_cost_yuan(
        settings,
        provider,
        reserved_input_tokens,
        reserved_output_tokens,
    )
    if float(spent or 0.0) + reserved > settings.model_daily_budget_yuan:
        return "daily_cost_limit"
    return None


def add_model_run(
    session: Session,
    settings: Settings,
    *,
    user_id: str,
    task: str,
    provider: str,
    model: str,
    status: str,
    latency_ms: int | None,
    input_tokens: int,
    output_tokens: int,
    error_code: str | None = None,
    fallback_from: str | None = None,
) -> ModelRun:
    run = ModelRun(
        user_id=user_id,
        task=task,
        provider=provider,
        model=model,
        status=status,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_yuan=estimate_cost_yuan(
            settings,
            provider,
            input_tokens,
            output_tokens,
        ),
        error_code=error_code,
        fallback_from=fallback_from,
    )
    session.add(run)
    return run


def build_usage_summary(session: Session, user_id: str, settings: Settings) -> dict[str, Any]:
    today = utc_now().date()
    day_start = datetime.combine(today, time.min, tzinfo=UTC)
    runs = list(
        session.scalars(
            select(ModelRun)
            .where(ModelRun.user_id == user_id, ModelRun.created_at >= day_start)
            .order_by(ModelRun.created_at.desc())
        )
    )
    external_calls = sum(
        run.provider != "local" and run.status != "blocked" for run in runs
    )
    return {
        "date": today,
        "total_calls": len(runs),
        "external_calls": external_calls,
        "failed_calls": sum(run.status == "failed" for run in runs),
        "blocked_calls": sum(run.status == "blocked" for run in runs),
        "estimated_cost_yuan": round(sum(run.estimated_cost_yuan for run in runs), 6),
        "daily_external_call_limit": settings.model_daily_external_call_limit,
        "remaining_external_calls": max(
            settings.model_daily_external_call_limit - external_calls,
            0,
        ),
        "pricing_configured": bool(
            settings.deepseek_input_price_yuan_per_million_tokens > 0
            and settings.deepseek_output_price_yuan_per_million_tokens > 0
        ),
        "recent_runs": runs[:12],
    }

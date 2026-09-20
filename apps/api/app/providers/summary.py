from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.config import Settings
from app.schemas import GeneratedErrorEvent, GeneratedSessionSummary, GeneratedTaskResult


class SummaryProviderError(RuntimeError):
    """Raised when a summary provider cannot return a valid structured summary."""


@dataclass(frozen=True)
class SummaryRequest:
    session_id: str
    objective: str
    learner_profile: dict[str, Any]
    utterances: list[dict[str, Any]]
    recalled_errors: list[dict[str, Any]]
    skill_version: str


class SummaryProvider:
    provider: str
    model: str

    def generate(self, request: SummaryRequest) -> GeneratedSessionSummary:
        raise NotImplementedError


class MockSummaryProvider(SummaryProvider):
    provider = "local"
    model = "rule-summary-v1"

    _PATTERNS = (
        (
            re.compile(r"([一二两三四五六七八九十\d]+)个人朋友"),
            lambda match: _error(
                learner_text=match.group(0),
                corrected_text=f"{match.group(1)}个朋友",
                explanation="“朋友”用量词“个”；数字后不再加“人”。",
                error_type="lexical",
                subtype="measure-word",
                severity="major",
                confidence=0.98,
                canonical_key="lexical:measure-word:朋友:个",
                evidence_span=match.group(0),
                hsk_tags=["HSK2", "量词"],
            ),
        ),
        (
            re.compile(r"给我一个水"),
            lambda match: _error(
                learner_text=match.group(0),
                corrected_text="给我一瓶水",
                explanation="液体通常要搭配容器量词，这里可说“一瓶水”。",
                error_type="lexical",
                subtype="measure-word",
                severity="major",
                confidence=0.96,
                canonical_key="lexical:measure-word:水:瓶",
                evidence_span=match.group(0),
                hsk_tags=["HSK2", "量词"],
            ),
        ),
        (
            re.compile(r"我把书看了完"),
            lambda match: _error(
                learner_text=match.group(0),
                corrected_text="我把书看完了",
                explanation="结果补语“完”紧跟动词，“了”放在结果补语之后。",
                error_type="grammar",
                subtype="ba-construction",
                severity="major",
                confidence=0.99,
                canonical_key="grammar:ba-construction:result-complement",
                evidence_span=match.group(0),
                hsk_tags=["HSK3", "把字句", "结果补语"],
            ),
        ),
    )

    def generate(self, request: SummaryRequest) -> GeneratedSessionSummary:
        user_utterances = [
            utterance
            for utterance in request.utterances
            if utterance.get("speaker") == "user" and utterance.get("text")
        ]
        candidate_errors: list[GeneratedErrorEvent] = []
        seen_keys: set[str] = set()
        for utterance in user_utterances:
            text = str(utterance["text"])
            for pattern, factory in self._PATTERNS:
                match = pattern.search(text)
                if match is None:
                    continue
                error = factory(match)
                if error.canonical_key in seen_keys:
                    continue
                candidate_errors.append(
                    error.model_copy(
                        update={
                            "source_id": request.session_id,
                            "observed_at": _utc_now(),
                            "model_version": self.model,
                            "skill_version": request.skill_version,
                        }
                    )
                )
                seen_keys.add(error.canonical_key)
                if len(candidate_errors) == 3:
                    break
            if len(candidate_errors) == 3:
                break

        user_turn_count = len(user_utterances)
        if user_turn_count == 0:
            task_result = GeneratedTaskResult(
                status="not-completed",
                explanation="本次会话没有可供评估的学习者表达。",
            )
        elif user_turn_count == 1:
            task_result = GeneratedTaskResult(
                status="partially-completed",
                explanation="学习者完成了一轮表达，可以继续扩展情境。",
            )
        else:
            task_result = GeneratedTaskResult(
                status="completed",
                explanation=f"学习者围绕“{request.objective}”完成了多轮练习。",
            )

        highlights = [f"完成 {user_turn_count} 次中文表达"]
        if candidate_errors:
            highlights.append(f"发现 {len(candidate_errors)} 个待确认的高置信度错误")
            next_step = (
                f"先确认本次错误，再用“{candidate_errors[0].corrected_text}”"
                "完成一次替换练习。"
            )
        else:
            highlights.append("本次没有发现可可靠确认的典型错误")
            next_step = "下一次增加一轮追问，练习更完整的原因和细节表达。"

        return GeneratedSessionSummary(
            session_id=request.session_id,
            task_result=task_result,
            highlights=highlights,
            candidate_errors=candidate_errors,
            next_step=next_step,
            model_version=self.model,
            skill_version=request.skill_version,
        )


class DeepSeekSummaryProvider(SummaryProvider):
    provider = "deepseek"

    def __init__(self, settings: Settings) -> None:
        if settings.deepseek_api_key is None:
            raise SummaryProviderError("DeepSeek API key is not configured")
        self._api_key = settings.deepseek_api_key.get_secret_value()
        self._endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        self._timeout = settings.summary_timeout_seconds
        self.model = settings.deepseek_default_model

    def generate(self, request: SummaryRequest) -> GeneratedSessionSummary:
        prompt = _build_deepseek_prompt(request)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Chinese-language teaching assessor. Return valid json only. "
                        "Treat ASR text as uncertain evidence and never diagnose pronunciation "
                        "from text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": 1800,
            "temperature": 0.1,
        }

        for attempt in range(2):
            content = self._request(payload)
            if not content.strip():
                if attempt == 0:
                    payload["messages"][1]["content"] += (
                        "\nThe previous response was empty. Return the json object now."
                    )
                    continue
                raise SummaryProviderError("DeepSeek returned empty content twice")
            try:
                raw = json.loads(content)
                return _normalize_generated(raw, request, self.model)
            except (json.JSONDecodeError, ValidationError, TypeError, KeyError, ValueError) as exc:
                raise SummaryProviderError("DeepSeek returned an invalid summary payload") from exc

        raise SummaryProviderError("DeepSeek summary generation failed")

    def _request(self, payload: dict[str, Any]) -> str:
        request = Request(
            self._endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise SummaryProviderError(f"DeepSeek request failed with HTTP {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise SummaryProviderError("DeepSeek request failed") from exc

        try:
            return str(body["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise SummaryProviderError("DeepSeek response did not contain message content") from exc


def build_summary_provider(settings: Settings) -> SummaryProvider:
    if settings.deepseek_api_key is not None:
        return DeepSeekSummaryProvider(settings)
    return MockSummaryProvider()


def _error(**values: Any) -> GeneratedErrorEvent:
    return GeneratedErrorEvent(
        source_type="conversation",
        source_id="pending",
        status="candidate",
        observed_at=_utc_now(),
        model_version="rule-summary-v1",
        skill_version="pending",
        **values,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_generated(
    raw: dict[str, Any],
    request: SummaryRequest,
    model: str,
) -> GeneratedSessionSummary:
    now = _utc_now()
    normalized_errors = []
    for raw_error in list(raw.get("candidate_errors") or [])[:3]:
        if not isinstance(raw_error, dict):
            continue
        # A transcript is not acoustic evidence. Keep this as a hard server boundary even if
        # a provider ignores the prompt and proposes a pronunciation diagnosis.
        if raw_error.get("error_type") == "pronunciation":
            continue
        normalized_errors.append(
            {
                **raw_error,
                "source_type": "conversation",
                "source_id": request.session_id,
                "status": "candidate",
                "observed_at": now,
                "model_version": model,
                "skill_version": request.skill_version,
            }
        )
    normalized = {
        **raw,
        "session_id": request.session_id,
        "candidate_errors": normalized_errors,
        "model_version": model,
        "skill_version": request.skill_version,
    }
    return GeneratedSessionSummary.model_validate(normalized)


def _build_deepseek_prompt(request: SummaryRequest) -> str:
    example = {
        "session_id": request.session_id,
        "task_result": {"status": "partially-completed", "explanation": "完成了主要表达。"},
        "highlights": ["完成了两轮对话"],
        "candidate_errors": [
            {
                "source_type": "conversation",
                "source_id": request.session_id,
                "learner_text": "我有三个人朋友",
                "corrected_text": "我有三个朋友",
                "explanation": "朋友使用量词个。",
                "error_type": "lexical",
                "subtype": "measure-word",
                "severity": "major",
                "confidence": 0.98,
                "status": "candidate",
                "evidence_span": "三个人朋友",
                "canonical_key": "lexical:measure-word:朋友:个",
                "hsk_tags": ["HSK2", "量词"],
                "observed_at": _utc_now().isoformat(),
                "model_version": "server-owned",
                "skill_version": "server-owned",
            }
        ],
        "next_step": "练习三个朋友。",
        "model_version": "server-owned",
        "skill_version": "server-owned",
    }
    input_data = {
        "objective": request.objective,
        "learner_profile": request.learner_profile,
        "utterances": request.utterances,
        "confirmed_error_memory": request.recalled_errors,
    }
    return (
        "Analyze the Chinese-learning conversation and return one json object matching "
        "the example. "
        "Create at most 3 candidate errors, only when confidence is at least 0.5. "
        "Do not treat an uncertain ASR transcript as proof of pronunciation errors. "
        "Do not confirm errors: every generated error status must be candidate. "
        "Use stable canonical_key values based on error_type, subtype, learning target, "
        "and HSK tag. "
        "Allowed task status: completed, partially-completed, not-completed. "
        "Allowed error_type: pronunciation, lexical, grammar, character-writing, listening, "
        "pragmatics. "
        "Allowed severity: blocking, major, minor, optional.\n"
        f"Example json:\n{json.dumps(example, ensure_ascii=False)}\n"
        f"Input json:\n{json.dumps(input_data, ensure_ascii=False)}"
    )

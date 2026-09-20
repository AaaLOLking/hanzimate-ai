from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


class LessonTutorError(RuntimeError):
    """Raised when a lesson-scoped tutor cannot produce a response."""


@dataclass(frozen=True)
class LessonTutorRequest:
    question: str
    context_pack: dict[str, Any]
    current_step: int


class LessonTutorProvider:
    provider: str
    model: str

    def answer(self, request: LessonTutorRequest) -> str:
        raise NotImplementedError


class LocalLessonTutorProvider(LessonTutorProvider):
    provider = "local"
    model = "lesson-context-v1"

    def answer(self, request: LessonTutorRequest) -> str:
        lesson = request.context_pack["lesson"]
        question = request.question.lower()
        if request.current_step in {1, 2} and any(
            phrase in question for phrase in ("答案", "answer", "直接告诉", "怎么答")
        ):
            targets = "、".join(lesson["targets"][:3])
            return f"先自己提取一次，我暂不展示完整答案。提示：注意本课目标“{targets}”。"
        if any(phrase in question for phrase in ("例子", "example", "举例")):
            examples = "；".join(item["chinese"] for item in lesson["examples"][:2])
            return f"可以对比这两个本课例子：{examples} 你也可以换一个食物或地点再造句。"
        if any(phrase in question for phrase in ("为什么", "why", "区别", "规则", "怎么用")):
            return f"{lesson['explanation']} 先只关注本课目标，不需要同时学习更多语法术语。"
        targets = "、".join(lesson["targets"])
        return (
            f"这个问题需要围绕本课的“{targets}”来回答。"
            f"本课目标是：{lesson['objective']} 你可以先写一个自己的例句，我会按这个目标反馈。"
        )


class DeepSeekLessonTutorProvider(LessonTutorProvider):
    provider = "deepseek"

    def __init__(self, settings: Settings) -> None:
        if settings.deepseek_api_key is None:
            raise LessonTutorError("DeepSeek API key is not configured")
        self._api_key = settings.deepseek_api_key.get_secret_value()
        self._endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        self._timeout = settings.summary_timeout_seconds
        self.model = settings.deepseek_default_model

    def answer(self, request: LessonTutorRequest) -> str:
        prompt = {
            "lesson_context_pack": request.context_pack,
            "current_step": request.current_step,
            "learner_question": request.question,
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Chinese teacher inside one lesson. Use only the supplied "
                        "lesson context pack. Keep the answer concise and level-appropriate. "
                        "Do not reveal a complete retrieval or transfer answer before the learner "
                        "attempts it. If the question is outside scope, say so. Never invent HSK "
                        "claims or citations."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "thinking": {"type": "disabled"},
            "max_tokens": 500,
            "temperature": 0.2,
        }
        http_request = Request(
            self._endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
            content = str(body["choices"][0]["message"]["content"] or "").strip()
        except HTTPError as exc:
            raise LessonTutorError(f"DeepSeek request failed with HTTP {exc.code}") from exc
        except (
            URLError,
            TimeoutError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise LessonTutorError("DeepSeek lesson tutor request failed") from exc
        if not content:
            raise LessonTutorError("DeepSeek lesson tutor returned empty content")
        return content


def build_lesson_tutor_provider(settings: Settings) -> LessonTutorProvider:
    if settings.deepseek_api_key is not None:
        return DeepSeekLessonTutorProvider(settings)
    return LocalLessonTutorProvider()

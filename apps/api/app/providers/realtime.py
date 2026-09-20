from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings


class RealtimeProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class RealtimeConnection:
    mode: str
    provider: str
    model: str
    voice: str
    max_duration_seconds: int
    fallback_reason: str | None = None


class RealtimeProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def connection(self) -> RealtimeConnection:
        raise NotImplementedError

    def exchange_offer(self, offer_sdp: str) -> str:
        raise RealtimeProviderError("This provider does not support WebRTC SDP exchange")


class MockRealtimeProvider(RealtimeProvider):
    @property
    def connection(self) -> RealtimeConnection:
        return RealtimeConnection(
            mode="mock",
            provider="local",
            model="browser-simulation",
            voice="browser-default",
            max_duration_seconds=self.settings.realtime_session_seconds,
            fallback_reason="DashScope credentials are not configured; using local simulation.",
        )


class QwenRealtimeProvider(RealtimeProvider):
    @property
    def connection(self) -> RealtimeConnection:
        return RealtimeConnection(
            mode="webrtc",
            provider="qwen",
            model=self.settings.qwen_realtime_model,
            voice=self.settings.qwen_realtime_voice,
            max_duration_seconds=self.settings.realtime_session_seconds,
        )

    def exchange_offer(self, offer_sdp: str) -> str:
        if not self.settings.dashscope_api_key or not self.settings.dashscope_workspace_id:
            raise RealtimeProviderError("DashScope credentials are incomplete")

        region_domain = {
            "beijing": "cn-beijing.maas.aliyuncs.com",
            "singapore": "ap-southeast-1.maas.aliyuncs.com",
        }[self.settings.dashscope_region]
        query = urlencode({"model": self.settings.qwen_realtime_model})
        endpoint = (
            f"https://{self.settings.dashscope_workspace_id}.{region_domain}"
            f"/api/v1/webrtc/realtime?{query}"
        )
        request = Request(
            endpoint,
            data=offer_sdp.encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.dashscope_api_key.get_secret_value()}",
                "Content-Type": "application/sdp",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RealtimeProviderError(
                f"Qwen signaling rejected the offer ({error.code}): {detail}"
            ) from error
        except URLError as error:
            raise RealtimeProviderError(f"Qwen signaling is unavailable: {error.reason}") from error


def resolve_realtime_provider(settings: Settings) -> RealtimeProvider:
    if settings.dashscope_api_key and settings.dashscope_workspace_id:
        return QwenRealtimeProvider(settings)
    return MockRealtimeProvider(settings)

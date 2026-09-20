"""Isolated browser probe server. No user DB, microphone or external model calls.

Run: uv run --project apps/api python apps/api/tests/continuous_probe_server.py
"""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import uvicorn  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.realtime import QwenRealtimeProvider  # noqa: E402

probe_directory = TemporaryDirectory(prefix="hanzimate-continuity-")
QwenRealtimeProvider.exchange_offer = lambda self, sdp: "probe-answer-sdp"
app = create_app(
    Settings(
        _env_file=None,
        app_env="test",
        database_url="sqlite:///" + (Path(probe_directory.name) / "probe.sqlite3").as_posix(),
        dashscope_api_key="probe-only",
        dashscope_workspace_id="probe-only",
        deepseek_api_key=None,
        tavily_api_key=None,
        realtime_session_seconds=4,
    )
)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)

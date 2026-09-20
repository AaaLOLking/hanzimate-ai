import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient]:
    settings = Settings(
        _env_file=None,
        dashscope_api_key=None,
        dashscope_workspace_id=None,
        deepseek_api_key=None,
        tavily_api_key=None,
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        database_auto_create=True,
    )
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client
    application.state.database.dispose()

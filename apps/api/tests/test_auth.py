from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_development_user_bootstrap_is_safe_under_parallel_requests(tmp_path: Path) -> None:
    database_path = (tmp_path / "parallel.sqlite3").as_posix()
    application = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite:///{database_path}",
            database_auto_create=True,
        )
    )

    with TestClient(application) as client:
        paths = ["/api/v1/onboarding", "/api/v1/workspaces", "/api/v1/models"]
        with ThreadPoolExecutor(max_workers=3) as executor:
            responses = list(executor.map(client.get, paths))

    application.state.database.dispose()
    assert [response.status_code for response in responses] == [200, 200, 200]

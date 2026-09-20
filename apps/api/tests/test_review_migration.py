import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_reviews import attempt_card, confirmed_card, rate

from app.config import Settings
from app.main import create_app
from app.models import ReviewLog


def test_review_migration_roundtrip_preserves_old_tables(tmp_path):
    database_path = tmp_path / "migration.sqlite3"
    environment = dict(os.environ, DATABASE_URL=f"sqlite:///{database_path.as_posix()}")
    api_directory = Path(__file__).resolve().parents[1]

    def migrate(*arguments):
        subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=api_directory,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )

    migrate("upgrade", "20260824_0005")
    with sqlite3.connect(database_path) as database:
        database.execute(
            "INSERT INTO users (id,email,display_name,locale,created_at) VALUES (?,?,?,?,?)",
            ("preserved", "test@local", "Old learner", "zh-CN", "2026-08-01 00:00:00"),
        )
    migrate("upgrade", "head")
    migrate("check")
    with sqlite3.connect(database_path) as database:
        assert database.execute("SELECT display_name FROM users").fetchone()[0] == "Old learner"
        assert (
            database.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                == "20260908_0009"
        )
        assert database.execute("SELECT count(*) FROM review_logs").fetchone()[0] == 0
        assert database.execute("SELECT count(*) FROM model_runs").fetchone()[0] == 0
        assert database.execute(
            "SELECT count(*) FROM account_deletion_receipts"
        ).fetchone()[0] == 0
    # Only this disposable database is downgraded; no user database is touched.
    migrate("downgrade", "20260824_0005")
    migrate("upgrade", "head")


def test_simultaneous_same_rating_commits_one_log(tmp_path):
    settings = Settings(
        app_env="test", database_url=f"sqlite:///{(tmp_path / 'race.db').as_posix()}"
    )
    application = create_app(settings)
    with TestClient(application) as client:
        card, _ = confirmed_card(client)
        attempt = attempt_card(client, card).json()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: rate(client, attempt), range(2)))
        assert [result.status_code for result in results] == [200, 200]
        assert results[0].json()["id"] == results[1].json()["id"]
        with application.state.database.session_factory() as session:
            assert session.scalar(select(func.count(ReviewLog.id))) == 1
    application.state.database.dispose()

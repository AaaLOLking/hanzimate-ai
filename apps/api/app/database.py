from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        engine_options: dict[str, object] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            engine_options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                engine_options["poolclass"] = StaticPool
            else:
                database_path = url.removeprefix("sqlite:///")
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(url, **engine_options)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()


def get_session(request: Request) -> Generator[Session]:
    database: Database = request.app.state.database
    with database.session_factory() as session:
        yield session

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.course_content import seed_course_catalog
from app.database import Database
from app.models import Base  # noqa: F401
from app.realtime.lifecycle import voice_session_lifecycle_worker
from app.reviews import backfill_review_cards, reminder_worker
from app.routes.account import router as account_router
from app.routes.beta import router as beta_router
from app.routes.courses import router as courses_router
from app.routes.health import router as health_router
from app.routes.memory import router as memory_router
from app.routes.models import router as models_router
from app.routes.onboarding import router as onboarding_router
from app.routes.reviews import router as reviews_router
from app.routes.summaries import router as summaries_router
from app.routes.tools import router as tools_router
from app.routes.voice import router as voice_router
from app.routes.voice_scenarios import router as voice_scenarios_router
from app.routes.workspaces import router as workspaces_router
from app.services import seed_model_registry


def create_app(settings=None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application):
        with application.state.database.session_factory() as session:
            backfill_review_cards(session)
        workers = []
        if settings.app_env != "test":
            workers = [
                asyncio.create_task(reminder_worker(application.state.database)),
                asyncio.create_task(
                    voice_session_lifecycle_worker(application.state.database)
                ),
            ]
        try:
            yield
        finally:
            for worker in workers:
                worker.cancel()
            for worker in workers:
                with suppress(asyncio.CancelledError):
                    await worker

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    database = Database(settings.database_url)
    application.state.database = database
    application.state.settings = settings
    if settings.database_auto_create:
        database.create_schema()
        with database.session_factory() as session:
            seed_model_registry(
                session,
                settings.deepseek_default_model,
                bool(settings.deepseek_api_key),
                settings.qwen_realtime_model,
                bool(settings.dashscope_api_key and settings.dashscope_workspace_id),
            )
            seed_course_catalog(session)

    application.include_router(health_router)
    application.include_router(account_router)
    application.include_router(beta_router)
    application.include_router(courses_router)
    application.include_router(onboarding_router)
    application.include_router(workspaces_router)
    application.include_router(models_router)
    application.include_router(voice_scenarios_router)
    application.include_router(voice_router)
    application.include_router(tools_router)
    application.include_router(summaries_router)
    application.include_router(memory_router)
    application.include_router(reviews_router)
    return application


app = create_app()

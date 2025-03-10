from asyncio import run
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from . import tasks
from .admin import register_admin
from .check_source import CheckSourceService
from .config import config
from .db import async_sessionmaker, init_db
from .routers import check_source, models

scheduler = BackgroundScheduler()
check_source_service = CheckSourceService(session=async_sessionmaker())

scheduler.add_job(
    lambda: run(tasks.check_all_sources(check_source_service)),
    IntervalTrigger(seconds=config.check_source_interval),
    id="check_all_sources",
    name="Check all sources for new content",
    replace_existing=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    try:
        await init_db()
        scheduler.start()
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(
    lifespan=lifespan,
    debug=config.debug,
    title=config.app_name,
    description=config.app_description,
    version=config.app_version,
)
app.include_router(models.router, prefix="/api/v1/data")
app.include_router(check_source.router, prefix="/api/v1/check-source")
register_admin(app)


@app.get("/", include_in_schema=False)
async def docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")

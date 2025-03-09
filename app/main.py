from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .admin import register_admin
from .config import config
from .db import init_db
from .routers import check_source, models


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    await init_db()
    yield


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

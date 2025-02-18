from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from . import api
from .admin import register_admin
from .config import config
from .db import init_db


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
app.include_router(api.router)
register_admin(app)

from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Query
from sqlmodel import Session, SQLModel, select

from db import get_engine
from models.sources import Site

engine = get_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def get_session() -> Generator[Session, Any, None]:
    with Session(engine) as session:
        yield session


app = FastAPI(lifespan=lifespan)


@app.get("/sites/", response_model=list[Site])
async def read_sites(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    sites = session.exec(select(Site).offset(offset).limit(limit))
    return sites

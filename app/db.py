import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import config

async_engine = create_async_engine(config.db_uri, future=True)
async_sessionmaker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

logger = logging.getLogger(__name__)


async def init_db():
    async with async_engine.begin() as conn:
        if config.dev_drop_db:
            logger.warning("!!! - Dropping Database - !!!")
            await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

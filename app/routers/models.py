from collections.abc import Callable, Coroutine, Sequence
from enum import Enum
from typing import Annotated, Any, Self
from uuid import UUID

import starlette.status as http_status
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import get_async_session
from ..models import articles, sources
from ..models.base import SQLCreate, SQLPublic, SQLTable
from ..models.model_service import ModelContainer, ModelService

ModelServiceFactory = Callable[[AsyncSession], Coroutine[Any, Any, ModelService]]


def get_model_service(table: type[SQLTable]) -> ModelServiceFactory:
    async def fn(session: AsyncSession = Depends(get_async_session)) -> ModelService:
        return ModelService(table=table, session=session)

    return fn


class ModelEndpointConfig(BaseModel):
    """
    Pydantic model configuration class for FastAPI endpoints that interact with SQLAlchemy models.

    This class provides configuration for creating RESTful API endpoints that handle database operations
    for a specific SQLAlchemy model.

    Attributes
    ----------
    path : str
        The URL path for the endpoint.
    table : type[SQLTable]
        SQLAlchemy model class representing the database table.
    create : type[SQLCreate]
        Pydantic model class for creating new records.
    response_model : type[SQLPublic]
        Pydantic model class for API responses.
    service : ModelServiceFactory
        Service factory class handling database operations.
    tags : list[str | Enum]
        List of tags for API documentation grouping.

    Methods
    -------
    from_table(table, tags=None)
        Class method that creates an endpoint configuration from a SQLAlchemy table class.
    """

    path: str
    table: type[SQLTable]
    create: type[SQLCreate]
    response_model: type[SQLPublic]
    service: ModelServiceFactory
    tags: list[str | Enum]

    @classmethod
    def from_table(cls, table: type[SQLTable], tags: list[str | Enum] | None = None) -> Self:
        """Creates an endpoint configuration from a SQLAlchemy table class.

        Parameters
        ----------
        table : type[SQLTable]
            SQLAlchemy model class representing the database table.
        tags : list[str | Enum], optional
            List of tags for API documentation grouping.

        Returns
        -------
        Self
            An instance of ModelEndpointConfig.
        """
        models_ = ModelContainer.from_table(table=table)
        return cls(
            path=f"/{models_.table.__tablename__}",
            table=models_.table,
            create=models_.create,
            response_model=models_.public,
            service=get_model_service(models_.table),
            tags=tags if tags is not None else [str(models_.table.__tablename__)],
        )


def add_create_model_endpoint(
    router_: APIRouter, config_: ModelEndpointConfig, decorator_extra_kwargs: dict | None = None
) -> None:
    @router_.put(
        path=config_.path,
        response_model=config_.response_model,
        status_code=http_status.HTTP_201_CREATED,
        tags=config_.tags,
        **(decorator_extra_kwargs or {}),
    )
    async def create(
        response: Response, data: Annotated[SQLCreate, config_.create], service: ModelService = Depends(config_.service)
    ) -> SQLTable:
        created = await service.create(data=data)
        response.headers["Location"] = f"{router_.prefix}{config_.path}/{created.uuid}"
        return created


def add_read_all_model_endpoint(
    router_: APIRouter, config_: ModelEndpointConfig, decorator_extra_kwargs: dict | None = None
) -> None:
    @router_.get(
        path=config_.path,
        response_model=list[config_.response_model],
        status_code=http_status.HTTP_200_OK,
        tags=config_.tags,
        **(decorator_extra_kwargs or {}),
    )
    async def read_all(
        service: ModelService = Depends(config_.service), offset: int = 0, limit: Annotated[int, Query(le=100)] = 100
    ) -> Sequence[SQLTable]:
        return await service.read_all(limit=limit, offset=offset)


def add_read_model_endpoint(
    router_: APIRouter, config_: ModelEndpointConfig, decorator_extra_kwargs: dict | None = None
) -> None:
    @router_.get(
        path=f"{config_.path}/{{uuid}}",
        response_model=config_.response_model,
        status_code=http_status.HTTP_200_OK,
        tags=config_.tags,
        **(decorator_extra_kwargs or {}),
    )
    async def read(
        uuid: Annotated[UUID, Depends(config_.service)], service: ModelService = Depends(config_.service)
    ) -> SQLTable:
        entity = await service.read(uuid=uuid)
        if entity is None:
            raise HTTPException(status_code=404, detail="Model not found")
        return entity


def add_update_model_endpoint(
    router_: APIRouter, config_: ModelEndpointConfig, decorator_extra_kwargs: dict | None = None
) -> None:
    @router_.patch(
        path=config_.path,
        response_model=config_.response_model,
        status_code=http_status.HTTP_200_OK,
        tags=config_.tags,
        **(decorator_extra_kwargs or {}),
    )
    async def update(data: SQLPublic, service: ModelService = Depends(config_.service)):
        return await service.update(data=data)


def add_delete_model_endpoint(
    router_: APIRouter, config_: ModelEndpointConfig, decorator_extra_kwargs: dict | None = None
) -> None:
    @router_.delete(
        path=f"{config_.path}/{{uuid}}",
        response_model=config_.response_model,
        status_code=http_status.HTTP_200_OK,
        tags=config_.tags,
        **(decorator_extra_kwargs or {}),
    )
    async def delete(uuid: UUID, service: ModelService = Depends(config_.service)) -> SQLTable:
        return await service.delete(uuid=uuid)


router = APIRouter()

model_endpoint_configs: list[ModelEndpointConfig] = [
    ModelEndpointConfig.from_table(table=sources.Site),
    ModelEndpointConfig.from_table(table=sources.Source),
    ModelEndpointConfig.from_table(table=articles.WatchLog),
    ModelEndpointConfig.from_table(table=articles.Article),
]


for config in model_endpoint_configs:
    add_create_model_endpoint(router, config)
    add_read_all_model_endpoint(router, config)
    add_read_model_endpoint(router, config)
    add_update_model_endpoint(router, config)
    add_delete_model_endpoint(router, config)

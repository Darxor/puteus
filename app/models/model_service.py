from collections.abc import Sequence
from typing import Self
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .base import SQLCreate, SQLPublic, SQLTable


class ModelContainer(BaseModel):
    """A container class holding SQLAlchemy model-related classes.

    This class serves as a container for related SQLAlchemy model classes, including the main table class,
    its public representation, and creation schema.

    Adapted from: https://github.com/wergstatt/endpoint-generator

    Attributes
    ----------
    table (type[SQLTable]): The main SQLAlchemy table model class
    public (type[SQLPublic]): The public representation class of the model
    create (type[SQLCreate]): The creation schema class for the model

    Class Methods
    -------------
    from_table(table: type[SQLTable]) -> Self:
        Creates a ModelContainer instance from a given table class by automatically
        finding its corresponding Public and Create classes based on naming conventions.

        Args:
            table (type[SQLTable]): The main SQLAlchemy table model class

        Returns:
            ModelContainer: A new instance containing the table and its related classes
    """
    table: type[SQLTable]
    public: type[SQLPublic]
    create: type[SQLCreate]

    @classmethod
    def from_table(cls, table: type[SQLTable]) -> Self:
        public_classes = [c for c in table.__bases__ if c.__name__.endswith("Public")]
        if not public_classes:
            raise ValueError(f"No public class found for table {table.__name__}")
        public = public_classes[0]

        create_classes = [c for c in public.__bases__ if c.__name__.endswith("Create")]
        if not create_classes:
            raise ValueError(f"No create class found for public class {public.__name__}")
        create = create_classes[0]

        return cls(table=table, public=public, create=create)


class ModelService:
    """Model service for handling database operations.

    This service provides CRUD operations for SQLModel-based database tables using SQLAlchemy async sessions.
    Adapted from: https://github.com/wergstatt/endpoint-generator

    Attributes
    ----------
    table (type[SQLTable]): The SQLModel table class to operate on
    session (AsyncSession): SQLAlchemy async session for database operations
    models (ModelContainer): Container for the table models and schemas
    """
    def __init__(self, table: type[SQLTable], session: AsyncSession):
        self.table = table
        self.session = session

        self.models = ModelContainer.from_table(table=self.table)

    async def create(self, data: SQLCreate) -> SQLTable:
        """
        Create a new record in the database.

        Parameters
        ----------
        data : SQLCreate
            The data to create the new record with. Must be a Pydantic model instance
            with model_dump() method.

        Returns
        -------
        SQLTable
            The newly created database record.
        """
        model = self.models.table(**data.model_dump())
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def read_all(self, offset: int = 0, limit: int | None = None) -> Sequence[SQLTable]:
        """Retrieve all active records from the database with pagination.

        Parameters
        ----------
        offset : int, optional
            Number of records to skip before starting to return rows, by default 0
        limit : int | None, optional
            Maximum number of records to return, by default None

        Returns
        -------
        Sequence[SQLTable]
            A sequence of active database records of the specified table type

        Notes
        -----
        Only retrieves records where the `active` flag is `True`.
        """
        stmt = select(self.models.table).where(self.models.table.active).offset(offset).limit(limit)
        return (await self.session.exec(stmt)).all()

    async def read(self, uuid: UUID) -> SQLTable | None:
        """
        Retrieve an active record from the database by UUID.

        Parameters
        ----------
        uuid : UUID
            The UUID of the record to retrieve.

        Returns
        -------
        SQLTable or None
            The retrieved record if found and active, None otherwise.
        """
        stmt = select(self.models.table).where(self.models.table.uuid == uuid, self.models.table.active)
        return (await self.session.exec(stmt)).one_or_none()

    async def update(self, data: SQLPublic) -> SQLTable:
        """
        Update an existing SQL model in the database.

        Parameters
        ----------
        data : SQLPublic
            The updated model data to persist, must include a UUID.

        Returns
        -------
        SQLTable
            The updated model instance.

        Raises
        ------
        HTTPException
            If no model is found with the given UUID (404).
        """
        model = await self.read(uuid=data.uuid)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        model.sqlmodel_update(data.model_dump())
        self.session.add(model)
        await self.session.commit()
        return model

    async def delete(self, uuid: UUID) -> SQLTable:
        """
        Soft delete a model from the database.

        Parameters
        ----------
        uuid : UUID
            Unique identifier of the model to delete.

        Returns
        -------
        SQLTable
            The deleted model instance.

        Raises
        ------
        HTTPException
            If model with given UUID is not found (404).
        """
        model = await self.read(uuid=uuid)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        model.sqlmodel_update({"active": False})
        self.session.add(model)
        await self.session.commit()
        return model

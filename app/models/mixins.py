import uuid
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field


class UUIDMixin:
    uuid: UUID = Field(default_factory=uuid.uuid4, primary_key=True, allow_mutation=False, unique=True, index=True)


class TimeAuditMixin:
    """TimeAuditMixin adds automatic timestamp tracking to SQLAlchemy models.

    This mixin adds created_at and updated_at timestamp fields that are automatically
    set when records are created and updated.

    Parameters
    ----------
    created_at : datetime, optional
        Timestamp when the record was created. Set automatically on creation.
    updated_at : datetime, optional
        Timestamp when the record was last updated. Updates automatically.

    Examples
    --------
    >>> from sqlmodel import SQLModel
    >>> class User(TimeAuditMixin, SQLModel, table=True):
    ...     id: Optional[int] = Field(default=None, primary_key=True)
    ...     name: str
    >>>
    >>> user = User(name='John')
    >>> session.add(user)
    >>> session.commit()
    >>> print(user.created_at)  # Shows creation timestamp
    >>> print(user.updated_at)  # Shows last update timestamp
    """

    created_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now()},
    )

    updated_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now(), "onupdate": sa.func.now()},
    )


class SoftDeletionMixin:
    """Mixin class to add soft deletion capability to SQLAlchemy models.

    This mixin adds 'deleted_at' and 'active' fields to track soft deletion state.
    When an object is soft deleted, it's marked as inactive and timestamped rather
    than being permanently removed from the database.

    Attributes
    ----------
    deleted_at : datetime, optional
        Timestamp when the object was soft deleted
    active : bool
        Flag indicating if the object is active (not soft deleted)

    Methods
    -------
    soft_delete()
        Mark the object as soft deleted by setting `deleted_at` and `active` flag

    Notes
    -----
    Has an *update* event listener to automatically set the `deleted_at` timestamp when the
    `active` flag is set to `False` and to remove it, when `active` is set to `True` again.

    Freshly created inactive objects will not have a `deleted_at` timestamp.
    """

    deleted_at: datetime | None = Field(
        default=None,
        nullable=True,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
    )
    active: bool = Field(default=True, nullable=False, sa_type=sa.Boolean)

    @classmethod
    def __declare_last__(cls) -> None:
        """Register the before_update event listener for the class.

        This hook method is called by SQLAlchemy after mappings are completed.
        """
        sa.event.listen(cls, "before_update", cls._update_deleted_at)

    @staticmethod
    def _update_deleted_at(mapper, connection: sa.Connection, target: "SoftDeletionMixin") -> None:
        """Event listener to set the deleted_at timestamp if needed.

        Parameters
        ----------
        mapper : sqlalchemy.orm.Mapper
            The mapper managing the target.
        connection : sqlalchemy.Connection
            The database connection being used.
        target : SoftDeletionMixin
            The instance being updated.
        """
        if target.active is False and target.deleted_at is None:
            target.deleted_at = connection.scalar(sa.func.now())
        elif target.active is True and target.deleted_at is not None:
            target.deleted_at = None

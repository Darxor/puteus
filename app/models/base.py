from sqlmodel import SQLModel

from .mixins import SoftDeletionMixin, TimeAuditMixin, UUIDMixin


class SQLCreate(SQLModel): ...


class SQLPublic(SQLCreate, UUIDMixin): ...


class SQLTable(SQLCreate, UUIDMixin, TimeAuditMixin, SoftDeletionMixin): ...



import enum
import uuid
from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


class Locale(enum.StrEnum):
    RU_RU = "ru-RU"
    EN_US = "en-US"
    EN_GB = "en-GB"


class BaseEntry(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    active: bool = Field(default=True, nullable=False)


class Site(BaseEntry, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    home_url: str = Field(..., description="The home URL of the site")
    title: str = Field(..., description="The title of the site")
    description: str | None = Field(..., description="The description of the site", nullable=True)
    country: str | None = Field(..., description="The country of the site", nullable=True)
    sources: list["Source"] = Relationship(back_populates="site")


class SourceType(enum.StrEnum):
    RSS = enum.auto()


class Source(BaseEntry, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    site_id: uuid.UUID | None = Field(None, foreign_key="site.id", description="The site ID")
    site: Site | None = Relationship(back_populates="sources")
    type: SourceType = Field(..., description="The type of the source")
    locale: Locale | None = Field(..., nullable=True, description="The locale of the site")
    uri: str = Field(..., description="The URI of the source")

import enum
import uuid

from pydantic_extra_types import country as pydantic_country
from pydantic_extra_types import language_code as pydantic_lang
from sqlmodel import AutoString, Field, Relationship

from .base import SQLCreate, SQLPublic, SQLTable
from .urls import AnyUrl


class SiteCreate(SQLCreate):
    url: AnyUrl = Field(..., description="The home URL of the site", sa_type=AutoString)
    name: str = Field(..., description="The name of the site")
    description: str | None = Field(None, description="The description of the site", nullable=True)
    country: pydantic_country.CountryAlpha3 | None = Field(
        None,
        description="The country of the site in ISO 3166-1 alpha-3 format",
        nullable=True,
        sa_type=AutoString,
        schema_extra={"examples": ["USA", "RUS"]},
    )


class SitePublic(SiteCreate, SQLPublic): ...


class Site(SitePublic, SQLTable, table=True):
    sources: list["Source"] = Relationship(back_populates="site")


class SourceType(enum.StrEnum):
    RSS = enum.auto()


class SourceCreate(SQLCreate):
    site_uuid: uuid.UUID | None = Field(None, foreign_key="site.uuid", description="The site ID")
    type: SourceType = Field(..., description="The type of the source")
    locale: pydantic_lang.LanguageAlpha2 | None = Field(
        None,
        nullable=True,
        description="The locale of the source in ISO 639-1 alpha-2 format",
        sa_type=AutoString,
        schema_extra={"examples": ["en", "ru", "de"]},
    )
    uri: AnyUrl = Field(..., description="The URI of the source", sa_type=AutoString)


class SourcePublic(SourceCreate, SQLPublic): ...


class Source(SourcePublic, SQLTable, table=True):
    site: Site | None = Relationship(back_populates="sources")

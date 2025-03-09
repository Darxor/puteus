import uuid
from typing import TYPE_CHECKING

from sqlmodel import AutoString, Field, Relationship

from .base import SQLCreate, SQLPublic, SQLTable
from .urls import AnyUrl

if TYPE_CHECKING:
    from .sources import Source


class WatchLogCreate(SQLCreate):
    source_uuid: uuid.UUID | None = Field(None, foreign_key="source.uuid", description="The source ID")
    previous_uuid: uuid.UUID | None = Field(
        None, description="The previous Article Watchlog UUID", foreign_key="watchlog.uuid"
    )
    content_hash: str | None = Field(
        None,
        description="The hash of the content of the article. Used to check if the article has changed.",
        nullable=True,
    )


class WatchLogPublic(WatchLogCreate, SQLPublic): ...


class WatchLog(WatchLogPublic, SQLTable, table=True):
    source: "Source" = Relationship(back_populates="watchlogs")
    article: "Article" = Relationship(back_populates="watchlog")


class ArticleCreate(SQLCreate):
    watchlog_uuid: uuid.UUID | None = Field(None, foreign_key="watchlog.uuid", description="The watchlog ID")
    title: str = Field(..., description="The title of the article")
    uri: AnyUrl = Field(..., description="The URI of the article", sa_type=AutoString)
    description: str | None = Field(None, description="The description of the article", nullable=True)
    is_newsworthy: bool = Field(
        default=False, description="Whether the article is newsworthy or not. Set to True if the article is newsworthy."
    )


class ArticlePublic(ArticleCreate, SQLPublic): ...


class Article(ArticlePublic, SQLTable, table=True):
    watchlog: WatchLog = Relationship(back_populates="article")

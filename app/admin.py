from fastapi import FastAPI
from sqladmin import Admin, ModelView

from .config import config
from .db import async_sessionmaker
from .models import articles, sources


class BaseView(ModelView):
    form_excluded_columns = ["created_at", "updated_at", "deleted_at"]


class SiteAdmin(BaseView, model=sources.Site):
    icon = "fa-solid fa-house-chimney"
    column_list = ["id", "name", "url", "active"]
    column_searchable_list = ["name", "url", "description"]
    column_filters = ["active"]


class SourceAdmin(BaseView, model=sources.Source):
    icon = "fa-solid fa-plug"
    column_list = ["id", "site", "type", "uri", "active"]
    column_searchable_list = ["site", "uri"]
    column_filters = ["site", "type", "active"]
    column_formatters = {"site": lambda m, a: f"{m.site.name} ({m.site.uuid})"}


class ArticleAdmin(BaseView, model=articles.Article):
    icon = "fa-solid fa-newspaper"
    column_list = ["id", "title", "uri", "is_newsworthy"]
    column_searchable_list = ["title", "uri", "description"]
    column_filters = ["is_newsworthy"]


class WatchLogAdmin(BaseView, model=articles.WatchLog):
    icon = "fa-solid fa-clock"
    column_list = ["id", "source", "article", "created_at"]
    column_searchable_list = ["source", "article"]
    column_filters = ["source", "article"]
    column_formatters = {"source": lambda m, a: f"{m.source.name} ({m.source.uuid})"}


def register_admin(app: FastAPI, admin_kwargs: dict | None = None) -> Admin:
    """
    Register the admin panel with the FastAPI application.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance.
    admin_kwargs : dict, optional
        Additional keyword arguments to pass to the Admin constructor, by default None

    Returns
    -------
    Admin
        The Admin instance.
    """
    admin_kwargs = {"debug": config.debug, **(admin_kwargs or {})}
    admin = Admin(app, session_maker=async_sessionmaker, **admin_kwargs)
    for view in [SiteAdmin, SourceAdmin, ArticleAdmin, WatchLogAdmin]:
        admin.add_view(view)
    return admin

from fastapi import FastAPI
from sqladmin import Admin, ModelView

from .config import config
from .db import async_sessionmaker
from .models.sources import Site, Source


class BaseView(ModelView):
    form_excluded_columns = ["created_at", "updated_at", "deleted_at"]


class SiteAdmin(BaseView, model=Site):
    icon = "fa-solid fa-house-chimney"
    column_list = ["id", "name", "url", "active"]
    column_searchable_list = ["name", "url", "description"]
    column_filters = ["active"]

class SourceAdmin(BaseView, model=Source):
    icon = "fa-solid fa-plug"
    column_list = ["id", "site", "type", "uri", "active"]
    column_searchable_list = ["site", "uri"]
    column_filters = ["site", "type", "active"]
    column_formatters = {"site": lambda m, a: f"{m.site.name} ({m.site.uuid})"}


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
    for view in [SiteAdmin, SourceAdmin]:
        admin.add_view(view)
    return admin

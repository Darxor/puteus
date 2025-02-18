from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models.urls import AnyUrl


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="puteus_", env_file=".env", extra="ignore")

    db_uri: AnyUrl = AnyUrl("sqlite+aiosqlite:///db.sqlite")
    debug: bool = False
    dev_drop_db: bool = False

    app_name: str = "Puteus"
    app_description: str = "Drain the web one drop at a time."
    app_version: str = "0.2.0"

    @field_validator("dev_drop_db", mode="after")
    @classmethod
    def check_drop_only_debug(cls, value: bool, info: ValidationInfo):
        if value and not info.data["debug"]:
            raise ValueError("dev_drop_db can only be set to True when debug is True.")


config = Config()

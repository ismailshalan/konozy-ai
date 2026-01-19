from __future__ import annotations

from typing import Optional

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import SettingsConfigDict

from .base import BaseAppSettings, cached_settings


class OdooSettings(BaseAppSettings):
    """
    Odoo connection settings.

    - تقرأ من الـ ENV:
      ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
    - عندك defaults معقولة علشان التطوير.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="ODOO_",
    )

    # IMPORTANT:
    # نحافظ على نفس الشكل اللي فعلياً شغال عندك دلوقتي:
    # URL: http://localhost:8069
    # DB: TWFEK_TEST
    # USER: admin
    # PASS: admin  (أنت بالفعل غيّرتها في الـ env للي تحب)

    url: AnyHttpUrl = "http://localhost:8069"   # من ODOO_URL
    db: str = "odoo18"                          # من ODOO_DB
    username: str = "admin"                     # من ODOO_USERNAME
    password: str = "admin"                     # من ODOO_PASSWORD

    timeout_seconds: int = 30

    @field_validator("db")
    @classmethod
    def _strip_db(cls, v: str) -> str:
        return v.strip()

    @field_validator("username", "password")
    @classmethod
    def _strip_creds(cls, v: str) -> str:
        return v.strip()


@cached_settings
def get_odoo_settings() -> OdooSettings:
    """
    Cached singleton-style accessor.
    """
    return OdooSettings()

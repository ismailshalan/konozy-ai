# core/settings/odoo_settings.py
from pydantic import Field
from .base import KonozyBaseSettings

class OdooSettings(KonozyBaseSettings):
    url: str = Field("http://localhost:8069/", env="ODOO_URL")
    db: str = Field("odoo18", env="ODOO_DB")
    username: str = Field("admin", env="ODOO_USERNAME")
    password: str = Field("admin", env="ODOO_PASSWORD")

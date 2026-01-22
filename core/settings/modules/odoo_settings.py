from __future__ import annotations

from pydantic import Field
from core.settings.base_settings import KonozyBaseSettings


class OdooSettings(KonozyBaseSettings):
    """
    Settings for Odoo XML-RPC connection.
    Loaded from .env with exact variable name matching.
    """

    odoo_url: str = Field(..., alias="ODOO_URL")
    odoo_db: str = Field(..., alias="ODOO_DB")
    odoo_username: str = Field(..., alias="ODOO_USERNAME")
    odoo_password: str = Field(..., alias="ODOO_PASSWORD")

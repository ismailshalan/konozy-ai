from __future__ import annotations

from pydantic import Field

from core.settings.base_settings import KonozyBaseSettings


class WarehouseSettings(KonozyBaseSettings):
    """
    Warehouse settings.
    Loaded from .env file with exact variable name matching.
    """

    amazon_location_id: int = Field(..., alias="AMAZON_LOCATION_ID")
    merchant_warehouse_id: int = Field(..., alias="MERCHANT_WAREHOUSE_ID")
    konozy_warehouse_id: int = Field(..., alias="KONOZY_WAREHOUSE_ID")
    noon_warehouse_id: int = Field(..., alias="NOON_WAREHOUSE_ID")
    amazon_warehouse_id: int = Field(..., alias="AMAZON_WAREHOUSE_ID")

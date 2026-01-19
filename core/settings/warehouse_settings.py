# core/settings/warehouse_settings.py
from pydantic import Field
from .base import KonozyBaseSettings

class WarehouseSettings(KonozyBaseSettings):
    konozy_warehouse_id: int = Field(..., env="KONOZY_WAREHOUSE_ID")
    merchant_warehouse_id: int = Field(..., env="MERCHANT_WAREHOUSE_ID")
    amazon_warehouse_id: int = Field(..., env="AMAZON_WAREHOUSE_ID")
    noon_warehouse_id: int = Field(..., env="NOON_WAREHOUSE_ID")

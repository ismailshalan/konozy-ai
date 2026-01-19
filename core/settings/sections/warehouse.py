from pydantic_settings import BaseSettings
from pydantic import Field


class WarehouseSettings(BaseSettings):
    """
    Warehouse settings.
    Loaded from .env file with exact variable name matching.
    """
    
    amazon_location_id: int = Field(..., alias="AMAZON_LOCATION_ID")
    merchant_warehouse_id: int = Field(..., alias="MERCHANT_WAREHOUSE_ID")
    konozy_warehouse_id: int = Field(..., alias="KONOZY_WAREHOUSE_ID")
    noon_warehouse_id: int = Field(..., alias="NOON_WAREHOUSE_ID")
    amazon_warehouse_id: int = Field(..., alias="AMAZON_WAREHOUSE_ID")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

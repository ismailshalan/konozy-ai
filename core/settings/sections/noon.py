from pydantic_settings import BaseSettings
from pydantic import Field


class NoonSettings(BaseSettings):
    """
    Noon integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    # API Credentials
    email: str = Field(..., alias="NOON_EMAIL")
    password: str = Field(..., alias="NOON_PASSWORD")
    
    # Partner & Warehouse
    partner_id: int = Field(..., alias="NOON_PARTNER_ID")
    warehouse_id: int = Field(..., alias="NOON_WAREHOUSE_ID")
    
    # Accounting
    account_id: int = Field(..., alias="NOON_ACCOUNT_ID")
    sales_id: int = Field(..., alias="NOON_SALES_ID")
    commissions_id: int = Field(..., alias="NOON_COMMISSIONS_ID")
    logistics_fee_id: int = Field(..., alias="NOON_LOGISTICS_FEE_ID")
    
    # Journal
    sales_journal_id: int = Field(..., alias="NOON_SALES_JOURNAL_ID")
    
    # Analytics
    analytic_sales_id: int = Field(..., alias="NOON_ANALYTIC_SALES_ID")
    analytic_commissions_id: int = Field(..., alias="NOON_COMMISSIONS_ANALYTIC_ID")
    analytic_logistics_id: int = Field(..., alias="NOON_LOGISTICS_ANALYTIC_ID")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class AmazonSettings(BaseSettings):
    """
    Amazon integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    # API Credentials
    seller_id: str = Field(..., alias="SELLER_ID")
    refresh_token: str = Field(..., alias="REFRESH_TOKEN")
    access_key: str = Field(..., alias="AMAZON_ACCESS_KEY")
    secret_key: str = Field(..., alias="AMAZON_SECRET_KEY")
    role_arn: str = Field(..., alias="ROLE_ARN")
    role_session_name: str = Field(default="konozy-session", alias="ROLE_SESSION_NAME")
    marketplace: str = Field(default="EG", alias="MARKETPLACE")

    # Warehouses
    amazon_location_id: int = Field(..., alias="AMAZON_LOCATION_ID")
    merchant_warehouse_id: int = Field(..., alias="MERCHANT_WAREHOUSE_ID")
    konozy_warehouse_id: int = Field(..., alias="KONOZY_WAREHOUSE_ID")
    noon_warehouse_id: int = Field(..., alias="NOON_WAREHOUSE_ID")
    amazon_warehouse_id: int = Field(..., alias="AMAZON_WAREHOUSE_ID")

    # Accounts & Fees
    account_id: int = Field(..., alias="AMAZON_ACCOUNT_ID")
    sales_id: int = Field(..., alias="AMAZON_SALES_ID")
    commissions_id: int = Field(..., alias="AMAZON_COMMISSIONS_ID")
    fees_product_id: int = Field(..., alias="AMAZON_FEES_PRODUCT_ID")
    promo_rebates_id: int = Field(..., alias="AMAZON_PROMO_REBATES_ID")
    fba_pick_pack_fee_id: int = Field(..., alias="AMAZON_FBA_PICK_PACK_FEE_ID")
    cod_fee_id: int = Field(..., alias="AMAZON_COD_FEE_ID")
    fba_fee_account_id: int = Field(..., alias="AMAZON_FBA_FEE_ACCOUNT_ID")
    inventory_loss_id: int = Field(..., alias="INVENTORY_LOSS_DAMAGED_GOODS_ID")
    amazon_partner_id: int = Field(..., alias="AMAZON_PARTNER_ID")

    # Journal
    journal_id: int = Field(..., alias="AMAZON_JOURNAL_ID")

    # Analytics
    analytic_shipping_cost_id: int = Field(..., alias="AMAZON_ANALYTIC_SHIPPING_COST_ID")
    analytic_sales_id: int = Field(..., alias="AMAZON_ANALYTIC_SALES_ID")
    analytic_commissions_id: int = Field(..., alias="AMAZON_ANALYTIC_COMMISSIONS_ID")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

# core/settings/amazon_settings.py
from pydantic import Field
from .base import KonozyBaseSettings

class AmazonSettings(KonozyBaseSettings):
    # API Credentials
    seller_id: str = Field(..., env="SELLER_ID")
    refresh_token: str = Field(..., env="REFRESH_TOKEN")
    access_key: str = Field(..., env="AMAZON_ACCESS_KEY")
    secret_key: str = Field(..., env="AMAZON_SECRET_KEY")

    role_arn: str = Field(..., env="ROLE_ARN")
    role_session_name: str = Field("konozy-session", env="ROLE_SESSION_NAME")
    marketplace: str = Field("EG", env="MARKETPLACE")

    # Warehouses
    warehouse_id: int = Field(2, env="AMAZON_WAREHOUSE_ID")
    location_id: int = Field(14, env="AMAZON_LOCATION_ID")
    partner_id: int = Field(19, env="AMAZON_PARTNER_ID")

    # Accounts / Journals
    account_id: int = Field(..., env="AMAZON_ACCOUNT_ID")
    sales_id: int = Field(..., env="AMAZON_SALES_ID")
    commissions_id: int = Field(..., env="AMAZON_COMMISSIONS_ID")
    promo_rebates_id: int = Field(..., env="AMAZON_PROMO_REBATES_ID")
    fba_fee_account_id: int = Field(..., env="AMAZON_FBA_FEE_ACCOUNT_ID")
    fba_pick_pack_fee_id: int = Field(..., env="AMAZON_FBA_PICK_PACK_FEE_ID")
    cod_fee_id: int = Field(..., env="AMAZON_COD_FEE_ID")
    damaged_goods_account_id: int = Field(..., env="INVENTORY_LOSS_DAMAGED_GOODS_ID")

    journal_id: int = Field(..., env="AMAZON_JOURNAL_ID")

    # Analytics
    analytic_sales_id: int = Field(..., env="AMAZON_ANALYTIC_SALES_ID")
    analytic_commissions_id: int = Field(..., env="AMAZON_ANALYTIC_COMMISSIONS_ANALYTIC_ID")
    analytic_shipping_cost_id: int = Field(..., env="AMAZON_ANALYTIC_SHIPPING_COST_ID")

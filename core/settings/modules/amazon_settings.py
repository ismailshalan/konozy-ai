from __future__ import annotations

from pydantic import Field

from core.settings.base_settings import KonozyBaseSettings


class AmazonSettings(KonozyBaseSettings):
    """
    Amazon integration settings.
    Loaded from .env file with exact variable name matching.
    """

    # API Credentials / Auth
    seller_id: str = Field(..., alias="SELLER_ID")
    refresh_token: str = Field(..., alias="REFRESH_TOKEN")

    # LWA (Login with Amazon)
    lwa_app_id: str = Field(..., alias="LWA_APP_ID")
    lwa_client_secret: str = Field(..., alias="LWA_CLIENT_SECRET")

    # AWS credentials for SigV4 signing
    amazon_access_key: str = Field(..., alias="AMAZON_ACCESS_KEY")
    amazon_secret_key: str = Field(..., alias="AMAZON_SECRET_KEY")

    # STS AssumeRole (if used)
    role_arn: str = Field(..., alias="ROLE_ARN")
    role_session_name: str = Field(..., alias="ROLE_SESSION_NAME")

    # Marketplace
    marketplace: str = Field(..., alias="MARKETPLACE")

    # Accounts & Fees
    account_id: int = Field(..., alias="AMAZON_ACCOUNT_ID")
    sales_id: int = Field(..., alias="AMAZON_SALES_ID")
    amazon_partner_id: int = Field(..., alias="AMAZON_PARTNER_ID")
    commissions_id: int = Field(..., alias="AMAZON_COMMISSIONS_ID")
    fees_product_id: int = Field(..., alias="AMAZON_FEES_PRODUCT_ID")
    promo_rebates_id: int = Field(..., alias="AMAZON_PROMO_REBATES_ID")
    inventory_loss_id: int = Field(..., alias="INVENTORY_LOSS_DAMAGED_GOODS_ID")
    fba_pick_pack_fee_id: int = Field(..., alias="AMAZON_FBA_PICK_PACK_FEE_ID")
    cod_fee_id: int = Field(..., alias="AMAZON_COD_FEE_ID")
    fba_fee_account_id: int = Field(..., alias="AMAZON_FBA_FEE_ACCOUNT_ID")

    # Journal
    journal_id: int = Field(..., alias="AMAZON_JOURNAL_ID")

    # Analytics
    analytic_sales_id: int = Field(..., alias="AMAZON_ANALYTIC_SALES_ID")
    analytic_shipping_cost_id: int = Field(
        ..., alias="AMAZON_ANALYTIC_SHIPPING_COST_ID"
    )
    analytic_commissions_id: int = Field(
        ..., alias="AMAZON_ANALYTIC_COMMISSIONS_ID"
    )

    spapi_host: str = Field(..., alias="SPAPI_HOST")
    spapi_region: str = Field(..., alias="SPAPI_REGION")

# core/settings/noon_settings.py
from pydantic import Field
from .base import KonozyBaseSettings

class NoonSettings(KonozyBaseSettings):
    email: str = Field(..., env="NOON_EMAIL")
    password: str = Field(..., env="NOON_PASSWORD")

    partner_id: int = Field(..., env="NOON_PARTNER_ID")
    warehouse_id: int = Field(..., env="NOON_WAREHOUSE_ID")

    # Accounting
    account_id: int = Field(..., env="NOON_ACCOUNT_ID")
    sales_id: int = Field(..., env="NOON_SALES_ID")
    commissions_id: int = Field(..., env="NOON_COMMISSIONS_ID")
    logistics_fee_id: int = Field(..., env="NOON_LOGISTICS_FEE_ID")

    # Journals
    journal_id: int = Field(..., env="NOON_SALES_JOURNAL_ID")

    # Analytics
    analytic_sales_id: int = Field(..., env="NOON_ANALYTIC_SALES_ID")
    analytic_commissions_id: int = Field(..., env="NOON_COMMISSIONS_ANALYTIC_ID")
    analytic_logistics_id: int = Field(..., env="NOON_LOGISTICS_ANALYTIC_ID")

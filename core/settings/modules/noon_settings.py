from __future__ import annotations

from pydantic import Field

from core.settings.base_settings import KonozyBaseSettings


class NoonSettings(KonozyBaseSettings):
    """
    Noon integration settings.
    Loaded from .env file with exact variable name matching.
    """

    # API Credentials
    email: str = Field(..., alias="NOON_EMAIL")
    password: str = Field(..., alias="NOON_PASSWORD")

    # Partner
    partner_id: int = Field(..., alias="NOON_PARTNER_ID")

    # Accounting
    account_id: int = Field(..., alias="NOON_ACCOUNT_ID")
    sales_id: int = Field(..., alias="NOON_SALES_ID")
    commissions_id: int = Field(..., alias="NOON_COMMISSIONS_ID")
    logistics_fee_id: int = Field(..., alias="NOON_LOGISTICS_FEE_ID")

    # Journal
    sales_journal_id: int = Field(..., alias="NOON_SALES_JOURNAL_ID")

    # Analytics
    analytic_sales_id: int = Field(..., alias="NOON_ANALYTIC_SALES_ID")
    analytic_commissions_id: int = Field(
        ..., alias="NOON_COMMISSIONS_ANALYTIC_ID"
    )
    analytic_logistics_id: int = Field(..., alias="NOON_LOGISTICS_ANALYTIC_ID")

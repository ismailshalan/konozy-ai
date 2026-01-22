from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from core.settings.modules.amazon_settings import AmazonSettings
from core.settings.modules.bank_settings import BankSettings
from core.settings.modules.integrations_settings import (
    NotionSettings,
    SlackSettings,
    TelegramSettings,
    WhatsAppSettings,
)
from core.settings.modules.noon_settings import NoonSettings
from core.settings.modules.odoo_settings import OdooSettings
from core.settings.modules.warehouse_settings import WarehouseSettings


class IntegrationsSettings(BaseModel):
    """Aggregates integrations settings as nested objects."""

    model_config = ConfigDict(extra="ignore")

    telegram: TelegramSettings
    whatsapp: WhatsAppSettings
    slack: SlackSettings
    notion: NotionSettings


class AppSettings(BaseModel):
    """
    Application settings aggregator.

    NOTE: We keep a couple of compatibility properties (`warehouses`, `telegram`, ...)
    so existing modules can continue to read settings without a huge refactor.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    amazon: AmazonSettings
    odoo: OdooSettings
    noon: NoonSettings
    warehouse: WarehouseSettings
    bank: BankSettings
    integrations: IntegrationsSettings

    # ---------------------------------------------------------------------
    # Compatibility shims (old code used plural and direct integration attrs)
    # ---------------------------------------------------------------------

    @property
    def warehouses(self) -> WarehouseSettings:
        return self.warehouse

    @property
    def telegram(self) -> TelegramSettings:
        return self.integrations.telegram

    @property
    def whatsapp(self) -> WhatsAppSettings:
        return self.integrations.whatsapp

    @property
    def slack(self) -> SlackSettings:
        return self.integrations.slack

    @property
    def notion(self) -> NotionSettings:
        return self.integrations.notion


@lru_cache()
def get_app_settings() -> AppSettings:
    return AppSettings(
        amazon=AmazonSettings(),
        odoo=OdooSettings(),
        noon=NoonSettings(),
        warehouse=WarehouseSettings(),
        bank=BankSettings(),
        integrations=IntegrationsSettings(
            telegram=TelegramSettings(),
            whatsapp=WhatsAppSettings(),
            slack=SlackSettings(),
            notion=NotionSettings(),
        ),
    )


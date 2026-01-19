# core/settings/app.py
from functools import lru_cache

# Sections
from core.settings.sections.odoo import OdooSettings
from core.settings.sections.amazon import AmazonSettings
from core.settings.sections.noon import NoonSettings
from core.settings.sections.bank import BankSettings
from core.settings.sections.integrations import (
    TelegramSettings,
    WhatsAppSettings,
    SlackSettings,
    NotionSettings,
)
from core.settings.sections.warehouse import WarehouseSettings


class AppSettings:
    """
    Central application settings aggregator.
    Settings are loaded lazily inside __init__
    to prevent eager evaluation at import time.
    """

    def __init__(self):
        # Load each settings class ONLY when AppSettings is instantiated
        self.odoo = OdooSettings()
        self.amazon = AmazonSettings()
        self.noon = NoonSettings()
        self.bank = BankSettings()
        self.warehouses = WarehouseSettings()

        self.telegram = TelegramSettings()
        self.whatsapp = WhatsAppSettings()
        self.slack = SlackSettings()
        self.notion = NotionSettings()


@lru_cache()
def get_app_settings() -> AppSettings:
    """Return cached global settings for the entire app."""
    return AppSettings()

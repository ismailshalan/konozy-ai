from __future__ import annotations

from pydantic import Field

from core.settings.base_settings import KonozyBaseSettings


class TelegramSettings(KonozyBaseSettings):
    """
    Telegram integration settings.
    Loaded from .env file with exact variable name matching.
    """

    enabled: bool = Field(..., alias="KONOZY_TELEGRAM_ENABLED")
    token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    chat_id: int = Field(..., alias="TELEGRAM_CHAT_ID")
    prefix: str = Field(..., alias="KONOZY_TELEGRAM_PREFIX")
    min_severity: int = Field(..., alias="KONOZY_TELEGRAM_MIN_SEVERITY")


class WhatsAppSettings(KonozyBaseSettings):
    """
    WhatsApp integration settings.
    Loaded from .env file with exact variable name matching.
    """

    enabled: bool = Field(..., alias="KONOZY_WHATSAPP_ENABLED")
    provider: str = Field(..., alias="WHATSAPP_PROVIDER")
    access_token: str = Field(..., alias="WHATSAPP_ACCESS_TOKEN")
    phone_number_id: int = Field(..., alias="WHATSAPP_PHONE_NUMBER_ID")
    waba_id: int = Field(..., alias="WHATSAPP_WABA_ID")
    to: str = Field(..., alias="WHATSAPP_TO")


class SlackSettings(KonozyBaseSettings):
    """
    Slack integration settings.
    Loaded from .env file with exact variable name matching.
    """

    enabled: bool = Field(..., alias="KONOZY_SLACK_ENABLED")
    bot_token: str = Field(..., alias="SLACK_BOT_TOKEN")
    channel_id: str = Field(..., alias="SLACK_CHANNEL_ID")
    webhook_url: str = Field(..., alias="SLACK_WEBHOOK_URL")
    prefix: str = Field(..., alias="KONOZY_SLACK_PREFIX")


class NotionSettings(KonozyBaseSettings):
    """
    Notion integration settings.
    Loaded from .env file with exact variable name matching.
    """

    token: str = Field(..., alias="NOTION_TOKEN")
    database_id: str = Field(..., alias="NOTION_DATABASE_ID")

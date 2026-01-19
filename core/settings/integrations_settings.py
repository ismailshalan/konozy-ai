# core/settings/integrations_settings.py
from pydantic import Field
from .base import KonozyBaseSettings

class TelegramSettings(KonozyBaseSettings):
    token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    chat_id: str = Field(..., env="TELEGRAM_CHAT_ID")
    enabled: bool = Field(True, env="KONOZY_TELEGRAM_ENABLED")
    min_severity: int = Field(80, env="KONOZY_TELEGRAM_MIN_SEVERITY")
    prefix: str = Field("[KONOZY INVENTORY]", env="KONOZY_TELEGRAM_PREFIX")


class WhatsAppSettings(KonozyBaseSettings):
    provider: str = Field("meta", env="WHATSAPP_PROVIDER")
    access_token: str = Field(..., env="WHATSAPP_ACCESS_TOKEN")
    phone_number_id: str = Field(..., env="WHATSAPP_PHONE_NUMBER_ID")
    waba_id: str = Field(..., env="WHATSAPP_WABA_ID")
    to: str = Field(..., env="WHATSAPP_TO")
    enabled: bool = Field(True, env="KONOZY_WHATSAPP_ENABLED")


class SlackSettings(KonozyBaseSettings):
    bot_token: str = Field(..., env="SLACK_BOT_TOKEN")
    channel_id: str = Field(..., env="SLACK_CHANNEL_ID")
    webhook_url: str = Field(..., env="SLACK_WEBHOOK_URL")
    enabled: bool = Field(True, env="KONOZY_SLACK_ENABLED")
    prefix: str = Field("[KONOZY]", env="KONOZY_SLACK_PREFIX")


class NotionSettings(KonozyBaseSettings):
    token: str = Field(..., env="NOTION_TOKEN")
    database_id: str = Field(..., env="NOTION_DATABASE_ID")

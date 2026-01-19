from pydantic_settings import BaseSettings
from pydantic import Field


class TelegramSettings(BaseSettings):
    """
    Telegram integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    enabled: bool = Field(default=True, alias="KONOZY_TELEGRAM_ENABLED")
    token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    chat_id: str = Field(..., alias="TELEGRAM_CHAT_ID")
    prefix: str = Field(default="[KONOZY INVENTORY]", alias="KONOZY_TELEGRAM_PREFIX")
    min_severity: int = Field(default=80, alias="KONOZY_TELEGRAM_MIN_SEVERITY")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class WhatsAppSettings(BaseSettings):
    """
    WhatsApp integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    enabled: bool = Field(default=True, alias="KONOZY_WHATSAPP_ENABLED")
    provider: str = Field(default="meta", alias="WHATSAPP_PROVIDER")
    access_token: str = Field(..., alias="WHATSAPP_ACCESS_TOKEN")
    phone_number_id: str = Field(..., alias="WHATSAPP_PHONE_NUMBER_ID")
    waba_id: str = Field(..., alias="WHATSAPP_WABA_ID")
    to: str = Field(..., alias="WHATSAPP_TO")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class SlackSettings(BaseSettings):
    """
    Slack integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    enabled: bool = Field(default=True, alias="KONOZY_SLACK_ENABLED")
    bot_token: str = Field(..., alias="SLACK_BOT_TOKEN")
    channel_id: str = Field(..., alias="SLACK_CHANNEL_ID")
    webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    prefix: str = Field(default="[KONOZY]", alias="KONOZY_SLACK_PREFIX")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class NotionSettings(BaseSettings):
    """
    Notion integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    token: str = Field(..., alias="NOTION_TOKEN")
    database_id: str = Field(..., alias="NOTION_DATABASE_ID")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

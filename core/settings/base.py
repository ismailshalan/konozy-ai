# core/settings/base.py
from pydantic_settings import BaseSettings

class KonozyBaseSettings(BaseSettings):
    class Config:
        env_file = "/mnt/storage/Konozy_ai/.env"
        env_file_encoding = "utf-8"

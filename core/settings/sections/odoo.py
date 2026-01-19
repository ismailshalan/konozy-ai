from pydantic_settings import BaseSettings


class OdooSettings(BaseSettings):
    """
    Settings for Odoo XML-RPC connection.
    Loaded automatically from .env with prefix ODOO_*
    """

    url: str = "http://localhost:8069"
    db: str = "odoo18"
    username: str = "admin"
    password: str = "admin"

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "env_prefix": "ODOO_",
        "extra": "ignore",
    }

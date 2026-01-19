from pydantic_settings import BaseSettings
from pydantic import Field


class BankSettings(BaseSettings):
    """
    Bank integration settings.
    Loaded from .env file with exact variable name matching.
    """
    
    cib_company_account_id: int = Field(..., alias="CIB_BANK_ACCOUNT_COMPANY_ID")
    cib_personal_account_id: int = Field(..., alias="CIB_BANK_ACCOUNT_PERSONAL_ID")

    bank_journal_company_id: int = Field(..., alias="BANK_JOURNAL_ID")
    bank_journal_personal_id: int = Field(..., alias="BANK_JOURNAL_CIB_PERSONAL_ID")

    cib_csv_path_company: str = Field(..., alias="CIB_CSV_PATH_ELSHOROUK")
    cib_csv_path_personal: str = Field(..., alias="CIB_CSV_PATH")

    model_config = {
        "env_file": "/mnt/storage/Konozy_ai/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

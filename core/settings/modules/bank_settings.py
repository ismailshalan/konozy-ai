from __future__ import annotations

from pydantic import Field

from core.settings.base_settings import KonozyBaseSettings


class BankSettings(KonozyBaseSettings):
    """
    Bank / CIB settings.
    Loaded from .env file with exact variable name matching.
    """

    bank_journal_id: int = Field(..., alias="BANK_JOURNAL_ID")
    bank_journal_cib_personal_id: int = Field(..., alias="BANK_JOURNAL_CIB_PERSONAL_ID")

    cib_bank_account_company_id: int = Field(..., alias="CIB_BANK_ACCOUNT_COMPANY_ID")
    cib_bank_account_personal_id: int = Field(..., alias="CIB_BANK_ACCOUNT_PERSONAL_ID")

    cib_csv_path: str = Field(..., alias="CIB_CSV_PATH")
    cib_csv_path_elshorouk: str = Field(..., alias="CIB_CSV_PATH_ELSHOROUK")


from __future__ import annotations

import os
from dataclasses import dataclass

from core.settings.odoo import get_odoo_settings
from core.settings.base import BaseAppSettings


def _get_int(env_name: str, default: int) -> int:
    value = os.getenv(env_name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# ============================================================
# 1) Odoo Connection Settings (NEW via Settings Architecture)
# ============================================================


@dataclass
class odoo_connection_config:
    """
    Adapter-level view فوق OdooSettings.

    بدل ما نعتمد على os.getenv مباشرة، بنقرأ من Settings Layer:
    - core.settings.odoo.OdooSettings
    """

    url: str
    db: str
    username: str
    password: str

    @classmethod
    def from_settings(cls) -> "odoo_connection_config":
        s = get_odoo_settings()
        return cls(
            url=str(s.url),
            db=s.db,
            username=s.username,
            password=s.password,
        )


# واحد بس ثابت في الموديول كله – زي القديم
ODOO_CONN_CFG = odoo_connection_config.from_settings()


# ============================================================
# 2) Accounting / Analytics / Marketplace Config
#    (مؤقتاً لسه شغالة بـ os.getenv علشان ما نكسرش حاجة)
#    نقدر ننقلها لاحقاً إلى Settings Architecture بنفس الأسلوب.
# ============================================================


@dataclass
class accounting_config:
    """
    Accounting configuration for Amazon / Noon integration.

    IMPORTANT:
    - إنت حر تغيّر القيم من خلال الـ ENV
    - الأرقام هنا Default علشان ما يعملش Crash لو نسيت متغير
    """

    amazon_journal_id: int = _get_int("AMAZON_JOURNAL_ID", 1)
    amazon_account_id: int = _get_int("AMAZON_ACCOUNT_ID", 1)

    amazon_commissions_id: int = _get_int("AMAZON_COMMISSIONS_ID", 1)
    amazon_fba_pick_pack_fee_id: int = _get_int("AMAZON_FBA_PICK_PACK_FEE_ID", 1)
    amazon_cod_fee_id: int = _get_int("AMAZON_COD_FEE_ID", 1)

    inventory_loss_damaged_goods_id: int = _get_int(
        "INVENTORY_LOSS_DAMAGED_GOODS_ID", 1
    )


@dataclass
class analytics_config:
    """
    Analytic accounts mapping for Amazon integration.
    """

    amazon_commissions_analytic_id: int = _get_int(
        "AMAZON_COMMISSIONS_ANALYTIC_ID", 1
    )
    analytic_amazon_shipping_cost_id: int = _get_int(
        "ANALYTIC_AMAZON_SHIPPING_COST_ID", 1
    )


@dataclass
class marketplace_config:
    """
    Misc marketplace-related IDs (partners / warehouses, ...).
    """

    amazon_partner_id: int = _get_int("AMAZON_PARTNER_ID", 19)
    amazon_warehouse_id: int = _get_int("AMAZON_WAREHOUSE_ID", 1)


# Module-level singletons (نفس فكرة ACCOUNTING_CFG القديمة)
ACCOUNTING_CFG = accounting_config()
ANALYTICS_CFG = analytics_config()
MARKETPLACE_CFG = marketplace_config()

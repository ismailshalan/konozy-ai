from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AmazonSettings(BaseSettings):
    """
    Settings خاصة بتكامل أمازون.

    مبدأ التصميم:
    - كل فيلد اسمه مطابق تقريبًا لاسم المتغير في .env لكن بصيغة snake_case.
    - BaseSettings هتقرأ المتغيرات من environment تلقائيًا:
      FIELD_NAME -> ENV VAR NAME = FIELD_NAME.upper()
      مثال:
        amazon_account_id  -> AMAZON_ACCOUNT_ID
        amazon_sales_id    -> AMAZON_SALES_ID
    """

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    # === Core Accounts / Partners / Warehouse ===
    amazon_account_id: int = 1031          # AMAZON_ACCOUNT_ID
    amazon_sales_id: int = 1075            # AMAZON_SALES_ID
    amazon_partner_id: int = 19            # AMAZON_PARTNER_ID
    amazon_warehouse_id: int = 2           # AMAZON_WAREHOUSE_ID
    amazon_journal_id: int = 472           # AMAZON_JOURNAL_ID

    # === Fees / Promo / Inventory Loss ===
    amazon_commissions_id: int = 1133      # AMAZON_COMMISSIONS_ID
    amazon_fees_product_id: int = 640      # AMAZON_FEES_PRODUCT_ID
    amazon_promo_rebates_id: int = 1100    # AMAZON_PROMO_REBATES_ID
    amazon_fba_fee_account: int = 1145     # Amazon_FBA_Fee_Account (مهم نعدّل اسمه في .env لاحقًا)
    inventory_loss_damaged_goods_id: int = 1146  # INVENTORY_LOSS_DAMAGED_GOODS_ID

    # === Analytic Accounts ===
    amazon_analytic_sales_id: int = 2          # AMAZON_ANALYTIC_SALES_ID
    amazon_commissions_analytic_id: int = 8    # AMAZON_COMMISSIONS_ANALYTIC_ID

    # ملاحظة: في .env المتغير اسمه حاليًا "analytical_Amazon_shipping_cost_id" بصيغة غريبة.
    # الأفضل توحيد الاسم إلى: ANALYTICAL_AMAZON_SHIPPING_COST_ID مستقبلاً.
    analytical_amazon_shipping_cost_id: int = 43  # ANALYTICAL_AMAZON_SHIPPING_COST_ID

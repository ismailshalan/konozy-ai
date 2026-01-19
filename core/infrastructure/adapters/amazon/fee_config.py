"""
Odoo account mappings for Amazon fee types.

CRITICAL: These values are PRODUCTION configuration from legacy system.
DO NOT MODIFY without approval from accounting team.

Source: docs/QUICK_REFERENCE.md
"""
from core.domain.value_objects.financial import AmazonFeeType, OdooAccountMapping


# ==============================================================================
# PRODUCTION ODOO ACCOUNT MAPPINGS (FROM LEGACY SYSTEM)
# ==============================================================================

AMAZON_FEE_MAPPINGS = {
    AmazonFeeType.FBA_FULFILLMENT: OdooAccountMapping(
        account_id=1133,
        analytic_account_id=8
    ),
    AmazonFeeType.COMMISSION: OdooAccountMapping(
        account_id=1133,
        analytic_account_id=8
    ),
    AmazonFeeType.REFUND_COMMISSION: OdooAccountMapping(
        account_id=1133,
        analytic_account_id=8
    ),
    AmazonFeeType.SHIPPING_CHARGE: OdooAccountMapping(
        account_id=1075,
        analytic_account_id=43
    ),
    AmazonFeeType.PROMO_REBATE: OdooAccountMapping(
        account_id=1100,
        analytic_account_id=2
    ),
    AmazonFeeType.STORAGE_FEE: OdooAccountMapping(
        account_id=1133,
        analytic_account_id=8
    ),
}

# Principal (revenue) account mapping
PRINCIPAL_MAPPING = OdooAccountMapping(account_id=1075, analytic_account_id=None)

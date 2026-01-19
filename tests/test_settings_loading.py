"""
Test settings loading from .env file.

This test verifies that all settings sections load correctly
from the .env file and that all fields are properly typed.
"""
import pytest
from core.settings.app import get_app_settings


def test_odoo_settings_load():
    """Test OdooSettings loads correctly."""
    settings = get_app_settings()
    
    # Verify all fields exist and are correct types
    assert isinstance(settings.odoo.url, str)
    assert isinstance(settings.odoo.db, str)
    assert isinstance(settings.odoo.username, str)
    assert isinstance(settings.odoo.password, str)
    
    # Verify values are loaded (not just defaults)
    assert settings.odoo.url.startswith("http")
    assert len(settings.odoo.db) > 0
    assert len(settings.odoo.username) > 0
    
    print(f"\n✅ OdooSettings loaded:")
    print(f"  URL: {settings.odoo.url}")
    print(f"  DB: {settings.odoo.db}")
    print(f"  Username: {settings.odoo.username}")


def test_amazon_settings_load():
    """Test AmazonSettings loads correctly."""
    settings = get_app_settings()
    
    # API Credentials
    assert isinstance(settings.amazon.seller_id, str)
    assert isinstance(settings.amazon.refresh_token, str)
    assert isinstance(settings.amazon.access_key, str)
    assert isinstance(settings.amazon.secret_key, str)
    assert isinstance(settings.amazon.role_arn, str)
    assert isinstance(settings.amazon.marketplace, str)
    
    # Warehouses (integers)
    assert isinstance(settings.amazon.amazon_location_id, int)
    assert isinstance(settings.amazon.merchant_warehouse_id, int)
    assert isinstance(settings.amazon.konozy_warehouse_id, int)
    assert isinstance(settings.amazon.noon_warehouse_id, int)
    assert isinstance(settings.amazon.amazon_warehouse_id, int)
    
    # Accounts & Fees (integers)
    assert isinstance(settings.amazon.account_id, int)
    assert isinstance(settings.amazon.sales_id, int)
    assert isinstance(settings.amazon.commissions_id, int)
    assert isinstance(settings.amazon.fees_product_id, int)
    assert isinstance(settings.amazon.promo_rebates_id, int)
    assert isinstance(settings.amazon.fba_pick_pack_fee_id, int)
    assert isinstance(settings.amazon.cod_fee_id, int)
    assert isinstance(settings.amazon.fba_fee_account_id, int)
    assert isinstance(settings.amazon.inventory_loss_id, int)
    assert isinstance(settings.amazon.amazon_partner_id, int)
    
    # Journal (integer)
    assert isinstance(settings.amazon.journal_id, int)
    
    # Analytics (integers)
    assert isinstance(settings.amazon.analytic_shipping_cost_id, int)
    assert isinstance(settings.amazon.analytic_sales_id, int)
    assert isinstance(settings.amazon.analytic_commissions_id, int)
    
    print(f"\n✅ AmazonSettings loaded:")
    print(f"  Seller ID: {settings.amazon.seller_id}")
    print(f"  Warehouse ID: {settings.amazon.amazon_warehouse_id}")
    print(f"  Account ID: {settings.amazon.account_id}")
    print(f"  Journal ID: {settings.amazon.journal_id}")


def test_noon_settings_load():
    """Test NoonSettings loads correctly."""
    settings = get_app_settings()
    
    # API Credentials
    assert isinstance(settings.noon.email, str)
    assert isinstance(settings.noon.password, str)
    
    # Partner & Warehouse (integers)
    assert isinstance(settings.noon.partner_id, int)
    assert isinstance(settings.noon.warehouse_id, int)
    
    # Accounting (integers)
    assert isinstance(settings.noon.account_id, int)
    assert isinstance(settings.noon.sales_id, int)
    assert isinstance(settings.noon.commissions_id, int)
    assert isinstance(settings.noon.logistics_fee_id, int)
    
    # Journal (integer)
    assert isinstance(settings.noon.sales_journal_id, int)
    
    # Analytics (integers)
    assert isinstance(settings.noon.analytic_sales_id, int)
    assert isinstance(settings.noon.analytic_commissions_id, int)
    assert isinstance(settings.noon.analytic_logistics_id, int)
    
    print(f"\n✅ NoonSettings loaded:")
    print(f"  Partner ID: {settings.noon.partner_id}")
    print(f"  Warehouse ID: {settings.noon.warehouse_id}")
    print(f"  Account ID: {settings.noon.account_id}")
    print(f"  Journal ID: {settings.noon.sales_journal_id}")


def test_bank_settings_load():
    """Test BankSettings loads correctly."""
    settings = get_app_settings()
    
    # Account IDs (integers)
    assert isinstance(settings.bank.cib_company_account_id, int)
    assert isinstance(settings.bank.cib_personal_account_id, int)
    
    # Journal IDs (integers)
    assert isinstance(settings.bank.bank_journal_company_id, int)
    assert isinstance(settings.bank.bank_journal_personal_id, int)
    
    # CSV Paths (strings)
    assert isinstance(settings.bank.cib_csv_path_company, str)
    assert isinstance(settings.bank.cib_csv_path_personal, str)
    
    print(f"\n✅ BankSettings loaded:")
    print(f"  Company Account ID: {settings.bank.cib_company_account_id}")
    print(f"  Personal Account ID: {settings.bank.cib_personal_account_id}")
    print(f"  Company CSV Path: {settings.bank.cib_csv_path_company}")


def test_warehouse_settings_load():
    """Test WarehouseSettings loads correctly."""
    settings = get_app_settings()
    
    # All warehouse IDs should be integers
    assert isinstance(settings.warehouses.amazon_location_id, int)
    assert isinstance(settings.warehouses.merchant_warehouse_id, int)
    assert isinstance(settings.warehouses.konozy_warehouse_id, int)
    assert isinstance(settings.warehouses.noon_warehouse_id, int)
    assert isinstance(settings.warehouses.amazon_warehouse_id, int)
    
    print(f"\n✅ WarehouseSettings loaded:")
    print(f"  Amazon Location ID: {settings.warehouses.amazon_location_id}")
    print(f"  Konozy Warehouse ID: {settings.warehouses.konozy_warehouse_id}")
    print(f"  Amazon Warehouse ID: {settings.warehouses.amazon_warehouse_id}")


def test_telegram_settings_load():
    """Test TelegramSettings loads correctly."""
    settings = get_app_settings()
    
    assert isinstance(settings.telegram.enabled, bool)
    assert isinstance(settings.telegram.token, str)
    assert isinstance(settings.telegram.chat_id, str)
    assert isinstance(settings.telegram.prefix, str)
    assert isinstance(settings.telegram.min_severity, int)
    
    print(f"\n✅ TelegramSettings loaded:")
    print(f"  Enabled: {settings.telegram.enabled}")
    print(f"  Chat ID: {settings.telegram.chat_id}")
    print(f"  Min Severity: {settings.telegram.min_severity}")


def test_whatsapp_settings_load():
    """Test WhatsAppSettings loads correctly."""
    settings = get_app_settings()
    
    assert isinstance(settings.whatsapp.enabled, bool)
    assert isinstance(settings.whatsapp.provider, str)
    assert isinstance(settings.whatsapp.access_token, str)
    assert isinstance(settings.whatsapp.phone_number_id, str)
    assert isinstance(settings.whatsapp.waba_id, str)
    assert isinstance(settings.whatsapp.to, str)
    
    print(f"\n✅ WhatsAppSettings loaded:")
    print(f"  Enabled: {settings.whatsapp.enabled}")
    print(f"  Provider: {settings.whatsapp.provider}")
    print(f"  Phone Number ID: {settings.whatsapp.phone_number_id}")


def test_slack_settings_load():
    """Test SlackSettings loads correctly."""
    settings = get_app_settings()
    
    assert isinstance(settings.slack.enabled, bool)
    assert isinstance(settings.slack.bot_token, str)
    assert isinstance(settings.slack.channel_id, str)
    assert isinstance(settings.slack.webhook_url, str)
    assert isinstance(settings.slack.prefix, str)
    
    print(f"\n✅ SlackSettings loaded:")
    print(f"  Enabled: {settings.slack.enabled}")
    print(f"  Channel ID: {settings.slack.channel_id}")
    print(f"  Prefix: {settings.slack.prefix}")


def test_notion_settings_load():
    """Test NotionSettings loads correctly."""
    settings = get_app_settings()
    
    assert isinstance(settings.notion.token, str)
    assert isinstance(settings.notion.database_id, str)
    
    print(f"\n✅ NotionSettings loaded:")
    print(f"  Database ID: {settings.notion.database_id}")


def test_all_settings_cached():
    """Test that get_app_settings() returns cached instance."""
    settings1 = get_app_settings()
    settings2 = get_app_settings()
    
    # Should be the same instance (cached)
    assert settings1 is settings2
    
    print(f"\n✅ Settings are properly cached")


def test_settings_load_from_env_file():
    """Test that settings are loaded from .env file, not just defaults."""
    settings = get_app_settings()
    
    # Verify that at least one setting is loaded from .env (not default)
    # Odoo URL should be loaded from .env
    assert settings.odoo.url != "http://localhost:8069" or settings.odoo.db != "odoo18"
    
    print(f"\n✅ Settings loaded from .env file")


if __name__ == "__main__":
    """
    Run tests directly without pytest.
    Useful for debugging settings loading issues.
    """
    print("=" * 60)
    print("Testing Settings Loading from .env")
    print("=" * 60)
    
    try:
        test_odoo_settings_load()
        test_amazon_settings_load()
        test_noon_settings_load()
        test_bank_settings_load()
        test_warehouse_settings_load()
        test_telegram_settings_load()
        test_whatsapp_settings_load()
        test_slack_settings_load()
        test_notion_settings_load()
        test_all_settings_cached()
        test_settings_load_from_env_file()
        
        print("\n" + "=" * 60)
        print("✅ All settings tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error loading settings: {e}")
        import traceback
        traceback.print_exc()
        raise

from konozy_odoo_sdk.core.logger import get_logger

logger = get_logger("AmazonOrders")


class AmazonOrderParser:

    @staticmethod
    def normalize_order(order):
        """Normalize Amazon SP-API order into unified structure."""
        return {
            "amazon_order_id": order.get("AmazonOrderId"),
            "purchase_date": order.get("PurchaseDate"),
            "status": order.get("OrderStatus"),
            "buyer_email": order.get("BuyerInfo", {}).get("BuyerEmail"),
        }

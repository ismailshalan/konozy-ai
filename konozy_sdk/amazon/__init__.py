"""Amazon SP-API SDK module."""

from .client import AmazonAPI
from .orders import AmazonOrderParser
from .financial_source import AmazonFinancialSource

# Export as AmazonOrders for backward compatibility (as per prompt requirements)
AmazonOrders = AmazonOrderParser

__all__ = ["AmazonAPI", "AmazonOrders", "AmazonOrderParser", "AmazonFinancialSource"]

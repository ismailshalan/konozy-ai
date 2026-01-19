"""
PARITY TESTS - New Implementation vs Legacy System

CRITICAL: These tests validate that new fee extraction logic produces
IDENTICAL output to legacy system. All tests must pass with ZERO discrepancies.

Any failure = MISSION FAILURE = Financial accuracy compromised.
"""
import pytest
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Any, List

from core.infrastructure.adapters.amazon.fee_mapper import AmazonFeeMapper
from core.domain.value_objects import FinancialBreakdown
from core.infrastructure.adapters.amazon.fee_config import PRINCIPAL_MAPPING

logger = logging.getLogger(__name__)


class TestFeeMapperParity:
    """Verify new implementation matches legacy output EXACTLY."""
    
    def _calculate_total_sales(self, breakdown: FinancialBreakdown) -> Decimal:
        """
        Calculate total sales (Principal + ShippingCharge + PaymentMethodFee).
        
        In legacy system, إجمالي_المبيعات = Principal + Shipping + PaymentMethodFee
        """
        # Principal
        total = breakdown.principal.amount
        
        # Add charges (ShippingCharge is a charge)
        charges = breakdown.get_charges()
        for charge in charges:
            total += charge.amount.amount
        
        return total
    
    def _calculate_total_fees(self, breakdown: FinancialBreakdown) -> Decimal:
        """Calculate total fees (all fee-type financial lines)."""
        fees = breakdown.get_fees()
        return sum(fee.amount.amount for fee in fees)
    
    def _calculate_total_promos(self, breakdown: FinancialBreakdown) -> Decimal:
        """Calculate total promotions (all promo-type financial lines)."""
        promos = breakdown.get_promos()
        return sum(promo.amount.amount for promo in promos)
    
    def _find_shipment_event(
        self,
        raw_events: Dict[str, Any],
        order_id: str
    ) -> Dict[str, Any]:
        """Find shipment event for given order ID."""
        events = raw_events["الأحداث_المالية"]["ShipmentEventList"]
        for event in events:
            if event["AmazonOrderId"] == order_id:
                return event
        raise ValueError(f"Order {order_id} not found in raw events")
    
    def _find_ground_truth_entry(
        self,
        ground_truth: List[Dict[str, Any]],
        order_id: str,
        sku: str
    ) -> Dict[str, Any]:
        """Find ground truth entry for given order ID and SKU."""
        for entry in ground_truth:
            if entry["رقم_الطلب"] == order_id and entry["كود_المنتج"] == sku:
                return entry
        raise ValueError(f"Ground truth entry not found for order {order_id}, SKU {sku}")
    
    @pytest.mark.parametrize("order_id,sku,expected_sales,expected_fees,expected_promos,expected_net", [
        ("407-6483514-6801140", "A8-RV0C-B73K", 428.0, -101.38, -20.0, 306.62),
        ("403-4215579-3567536", "G30-GOLD", 619.0, -47.26, -20.0, 551.74),
        ("402-5601926-2929934", "iQIBLA - Smart_blk_18m", 909.0, -113.64, -20.0, 775.36),
    ])
    def test_order_parity(
        self,
        raw_financial_events,
        ground_truth,
        order_id,
        sku,
        expected_sales,
        expected_fees,
        expected_promos,
        expected_net
    ):
        """
        Test complete parity for individual orders.
        
        Validates:
        - Total Sales (Principal + Shipping + PaymentMethodFee)
        - Total Fees (all fee types)
        - Total Promotions
        - Net Proceeds
        """
        # Find shipment event
        shipment_event = self._find_shipment_event(raw_financial_events, order_id)
        
        # Extract financial breakdown using new implementation
        financial_events = {"ShipmentEventList": [shipment_event]}
        breakdown = AmazonFeeMapper.parse_financial_events(
            financial_events,
            order_id
        )
        
        # Calculate totals
        total_sales = self._calculate_total_sales(breakdown)
        total_fees = self._calculate_total_fees(breakdown)
        total_promos = self._calculate_total_promos(breakdown)
        net_proceeds = breakdown.net_proceeds.amount
        
        # Find ground truth entry
        gt_entry = self._find_ground_truth_entry(ground_truth, order_id, sku)
        
        # Validate totals match ground truth
        TOLERANCE = Decimal("0.01")
        
        assert abs(total_sales - Decimal(str(gt_entry["إجمالي_المبيعات"]))) < TOLERANCE, \
            f"Total Sales mismatch for {order_id}: got {total_sales}, expected {gt_entry['إجمالي_المبيعات']}"
        
        assert abs(total_fees - Decimal(str(gt_entry["إجمالي_العمولات"]))) < TOLERANCE, \
            f"Total Fees mismatch for {order_id}: got {total_fees}, expected {gt_entry['إجمالي_العمولات']}"
        
        assert abs(total_promos - Decimal(str(gt_entry["إجمالي_الخصومات"]))) < TOLERANCE, \
            f"Total Promos mismatch for {order_id}: got {total_promos}, expected {gt_entry['إجمالي_الخصومات']}"
        
        assert abs(net_proceeds - Decimal(str(gt_entry["صافي_المبلغ"]))) < TOLERANCE, \
            f"Net Proceeds mismatch for {order_id}: got {net_proceeds}, expected {gt_entry['صافي_المبلغ']}"
        
        # Validate balance equation
        assert breakdown.validate_balance(), \
            f"Balance equation failed for {order_id}"
    
    def test_all_orders_parity(self, raw_financial_events, ground_truth):
        """
        Test parity for all orders in ground truth.
        
        This is a comprehensive test that validates all entries.
        """
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        
        # Build order_id -> shipment_event mapping
        shipment_events_by_order = {
            event["AmazonOrderId"]: event
            for event in events_list
        }
        
        failures = []
        
        for gt_entry in ground_truth:
            order_id = gt_entry["رقم_الطلب"]
            sku = gt_entry["كود_المنتج"]
            
            # Skip if order not in raw events
            if order_id not in shipment_events_by_order:
                continue
            
            try:
                # Extract financial breakdown
                shipment_event = shipment_events_by_order[order_id]
                financial_events = {"ShipmentEventList": [shipment_event]}
                
                # Check if this is a multi-item order (multiple SKUs in ground truth)
                # For multi-item orders, calculate per-SKU breakdown
                skus_in_order = [
                    e["كود_المنتج"] 
                    for e in ground_truth 
                    if e["رقم_الطلب"] == order_id
                ]
                
                if len(skus_in_order) > 1:
                    # Multi-item order: calculate per-SKU breakdown
                    sku_breakdown = AmazonFeeMapper.calculate_sku_breakdown(
                        financial_events,
                        order_id,
                        sku
                    )
                    
                    total_sales = sku_breakdown["total_sales"]
                    total_fees = sku_breakdown["fees"]
                    total_promos = sku_breakdown["promos"]
                    net_proceeds = sku_breakdown["net_proceeds"]
                    
                    # Balance validation not applicable for per-SKU breakdown
                    balance_valid = True
                else:
                    # Single-item order: use aggregate breakdown
                    breakdown = AmazonFeeMapper.parse_financial_events(
                        financial_events,
                        order_id
                    )
                    
                    # Calculate totals
                    total_sales = self._calculate_total_sales(breakdown)
                    total_fees = self._calculate_total_fees(breakdown)
                    total_promos = self._calculate_total_promos(breakdown)
                    net_proceeds = breakdown.net_proceeds.amount
                    balance_valid = breakdown.validate_balance()
                
                # Validate
                TOLERANCE = Decimal("0.01")
                
                sales_match = abs(total_sales - Decimal(str(gt_entry["إجمالي_المبيعات"]))) < TOLERANCE
                fees_match = abs(total_fees - Decimal(str(gt_entry["إجمالي_العمولات"]))) < TOLERANCE
                promos_match = abs(total_promos - Decimal(str(gt_entry["إجمالي_الخصومات"]))) < TOLERANCE
                net_match = abs(net_proceeds - Decimal(str(gt_entry["صافي_المبلغ"]))) < TOLERANCE
                
                # If all validations pass, publish FinancialParityVerified event to Redis Stream
                if all([sales_match, fees_match, promos_match, net_match, balance_valid]):
                    # Publish to Redis Stream (decouple validation from sync)
                    asyncio.run(self._publish_parity_verified(
                        order_id=order_id,
                        sku=sku,
                        net_proceeds=net_proceeds,
                        account_id=PRINCIPAL_MAPPING.account_id
                    ))
                
                if not all([sales_match, fees_match, promos_match, net_match, balance_valid]):
                    failures.append({
                        "order_id": order_id,
                        "sku": sku,
                        "total_sales": (float(total_sales), gt_entry["إجمالي_المبيعات"], sales_match),
                        "total_fees": (float(total_fees), gt_entry["إجمالي_العمولات"], fees_match),
                        "total_promos": (float(total_promos), gt_entry["إجمالي_الخصومات"], promos_match),
                        "net_proceeds": (float(net_proceeds), gt_entry["صافي_المبلغ"], net_match),
                        "balance_valid": balance_valid,
                    })
            
            except Exception as e:
                failures.append({
                    "order_id": order_id,
                    "sku": sku,
                    "error": str(e),
                })
        
        # Report failures
        if failures:
            error_msg = "\n".join([
                f"Order {f['order_id']} (SKU: {f.get('sku', 'N/A')}): "
                f"{f.get('error', 'Validation failed')}"
                for f in failures
            ])
            pytest.fail(f"Parity validation failed for {len(failures)} order(s):\n{error_msg}")
        
        # All passed
        assert len(failures) == 0, "All parity checks must pass"
    
    def test_balance_equation_all_orders(self, raw_financial_events):
        """
        Test that balance equation holds for all orders.
        
        Balance equation: principal + sum(financial_lines) = net_proceeds
        """
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        
        failures = []
        
        for event in events_list:
            order_id = event["AmazonOrderId"]
            
            try:
                financial_events = {"ShipmentEventList": [event]}
                breakdown = AmazonFeeMapper.parse_financial_events(
                    financial_events,
                    order_id
                )
                
                if not breakdown.validate_balance():
                    failures.append(order_id)
            
            except Exception as e:
                failures.append(f"{order_id} (error: {str(e)})")
        
        assert len(failures) == 0, \
            f"Balance equation validation failed for {len(failures)} order(s): {failures}"
    
    async def _publish_parity_verified(
        self,
        order_id: str,
        sku: str,
        net_proceeds: Decimal,
        account_id: int
    ) -> None:
        """
        Publish FinancialParityVerified event to Redis Stream.
        
        This decouples validation from Odoo synchronization,
        eliminating SQLAlchemy async issues.
        
        Args:
            order_id: Amazon order ID
            sku: Product SKU
            net_proceeds: Net proceeds amount
            account_id: Odoo account ID
        """
        try:
            from core.infrastructure.bus.redis_stream_publisher import (
                get_redis_stream_publisher
            )
            
            publisher = get_redis_stream_publisher()
            
            # Publish event (non-blocking, with error handling)
            msg_id = await publisher.publish_financial_parity_verified(
                order_id=order_id,
                sku=sku,
                net_proceeds=net_proceeds,
                account_id=account_id
            )
            
            logger.info(
                f"✅ Published FinancialParityVerified: "
                f"order={order_id}, sku={sku}, net={net_proceeds}, "
                f"account={account_id}, msg_id={msg_id}"
            )
        
        except ImportError:
            # Redis not available - skip publishing (non-critical)
            logger.debug(
                f"Redis Stream Publisher not available - skipping event publish "
                f"for order={order_id}, sku={sku}"
            )
        
        except Exception as e:
            # Log error but don't fail the test (non-critical)
            logger.warning(
                f"Failed to publish FinancialParityVerified event: {e} "
                f"(order={order_id}, sku={sku})"
            )
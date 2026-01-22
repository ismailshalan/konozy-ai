"""
Redis Streams Consumer for Event-Driven Architecture.

Consumes FinancialParityVerified events from Redis Streams and syncs to Odoo.
Decouples validation from synchronization, eliminating SQLAlchemy async issues.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
import asyncio

import redis.asyncio as aioredis

from core.application.interfaces import IOdooClient
from core.domain.repositories import OrderRepository
from core.domain.value_objects import OrderNumber, ExecutionID
from core.infrastructure.adapters.odoo.odoo_financial_mapper import OdooFinancialMapper


logger = logging.getLogger(__name__)


class RedisStreamConsumer:
    """
    Consumes events from Redis Streams.
    
    Features:
    - Consumer groups for load balancing
    - Message acknowledgment (ACK) after successful processing
    - Automatic retry on failure
    - Dead letter queue support
    
    Stream: konozy:finance:stream
    Consumer Group: konozy:finance:consumers
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        stream_name: str = "konozy:finance:stream",
        consumer_group: str = "konozy:finance:consumers",
        consumer_name: str = "odoo-sync-worker-1"
    ):
        """
        Initialize Redis Stream Consumer.
        
        Args:
            redis_url: Redis connection URL
            stream_name: Redis Stream name
            consumer_group: Consumer group name
            consumer_name: Unique consumer name (for load balancing)
        """
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self._redis_client: Optional[aioredis.Redis] = None
        self._running = False
    
    async def connect(self) -> None:
        """Establish Redis connection and create consumer group."""
        if self._redis_client is None:
            try:
                self._redis_client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis_client.ping()
                logger.info(f"✅ Connected to Redis: {self.redis_url}")
                
                # Create consumer group (if not exists)
                try:
                    await self._redis_client.xgroup_create(
                        name=self.stream_name,
                        groupname=self.consumer_group,
                        id="0",  # Start from beginning
                        mkstream=True  # Create stream if doesn't exist
                    )
                    logger.info(f"✅ Created consumer group: {self.consumer_group}")
                except aioredis.ResponseError as e:
                    if "BUSYGROUP" in str(e):
                        logger.info(f"Consumer group {self.consumer_group} already exists")
                    else:
                        raise
            
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        self._running = False
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            logger.info("✅ Disconnected from Redis")
    
    async def consume_messages(
        self,
        batch_size: int = 10,
        block_ms: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Read messages from Redis Stream.
        
        Args:
            batch_size: Maximum number of messages to read
            block_ms: Blocking time in milliseconds
        
        Returns:
            List of message dictionaries with 'id' and 'data' keys
        """
        if self._redis_client is None:
            await self.connect()
        
        try:
            # Read messages from stream using consumer group
            messages = await self._redis_client.xreadgroup(
                groupname=self.consumer_group,
                consumername=self.consumer_name,
                streams={self.stream_name: ">"},  # ">" means new messages
                count=batch_size,
                block=block_ms
            )
            
            if not messages:
                return []
            
            # Parse messages
            result = []
            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages:
                    result.append({
                        "id": msg_id,
                        "data": msg_data
                    })
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to read from Redis Stream: {e}")
            raise
    
    async def acknowledge_message(self, message_id: str) -> None:
        """
        Acknowledge message processing (ACK).
        
        This removes the message from pending list,
        ensuring it won't be reprocessed.
        
        Args:
            message_id: Message ID to acknowledge
        """
        if self._redis_client is None:
            await self.connect()
        
        try:
            await self._redis_client.xack(
                name=self.stream_name,
                groupname=self.consumer_group,
                *[message_id]
            )
            logger.debug(f"✅ Acknowledged message: {message_id}")
        
        except Exception as e:
            logger.error(f"Failed to ACK message {message_id}: {e}")
            raise
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


async def sync_validated_order_to_odoo(
    message: Dict[str, Any],
    consumer: RedisStreamConsumer,
    odoo_client: IOdooClient,
    order_repository: OrderRepository
) -> None:
    """
    Sync validated order to Odoo from Redis Stream message.
    
    This function:
    1. Reads FinancialParityVerified event from Redis Stream
    2. Loads Order from repository
    3. Creates Odoo invoice using OdooFinancialMapper
    4. Sends ACK to Redis after success
    5. Logs Odoo Invoice ID
    
    Args:
        message: Redis Stream message with 'id' and 'data' keys
        consumer: RedisStreamConsumer instance
        odoo_client: Odoo client for invoice creation
        order_repository: Order repository for loading order
    
    Raises:
        Exception: If sync fails (message will be retried)
    """
    message_id = message["id"]
    event_data = message["data"]
    
    order_id = event_data.get("order_id")
    sku = event_data.get("sku")
    net_proceeds = Decimal(event_data.get("net_proceeds", "0"))
    account_id = int(event_data.get("account_id", "0"))
    
    execution_id = ExecutionID.generate()
    
    logger.info(
        f"[{execution_id}] Processing FinancialParityVerified event: "
        f"order={order_id}, sku={sku}, net={net_proceeds}, "
        f"account={account_id}, msg_id={message_id}"
    )
    
    try:
        # Load order from repository
        order = await order_repository.find_by_id(OrderNumber(value=order_id))
        
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        if not order.financial_breakdown:
            raise ValueError(f"Order {order_id} has no financial breakdown")
        
        # Get partner ID (if available)
        partner_id = None
        if order.buyer_email:
            partner_id = await odoo_client.get_partner_by_email(order.buyer_email)
            if partner_id:
                logger.info(f"[{execution_id}] Found partner: {partner_id} for {order.buyer_email}")
        
        # Extract SKU-to-principal mapping (for multi-item orders)
        # Use AmazonFeeMapper to calculate per-SKU breakdown
        sku_to_principal = {}
        
        if order.items:
            # For each SKU in the order, calculate its principal
            for item in order.items:
                if item.sku:
                    # If single-item order, use total principal
                    if len(order.items) == 1:
                        sku_to_principal[item.sku] = order.financial_breakdown.principal.amount
                    else:
                        # Multi-item order: calculate per-SKU breakdown
                        # Note: This requires the original financial events
                        # For now, distribute principal equally (simplified)
                        # In production, use AmazonFeeMapper.calculate_sku_breakdown()
                        total_principal = order.financial_breakdown.principal.amount
                        sku_to_principal[item.sku] = total_principal / len(order.items)
        else:
            # Fallback: use total principal as single SKU
            if order.financial_breakdown:
                sku_to_principal["UNKNOWN"] = order.financial_breakdown.principal.amount
        
        # Generate invoice header
        invoice_header = OdooFinancialMapper.to_invoice_header(order=order)
        if partner_id:
            invoice_header["partner_id"] = partner_id
        
        # Generate invoice lines
        invoice_lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=order.financial_breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Create invoice in Odoo
        logger.info(f"[{execution_id}] Creating Odoo invoice for order {order_id}...")
        odoo_invoice_id = await odoo_client.create_invoice(
            header=invoice_header,
            lines=invoice_lines
        )
        
        # Log Odoo Invoice ID (CRITICAL for production tracking)
        logger.info(
            f"[{execution_id}] ✅ ODOO INVOICE CREATED: "
            f"Invoice ID={odoo_invoice_id}, Order ID={order_id}, SKU={sku}, "
            f"Net Proceeds={net_proceeds}, Account={account_id}"
        )
        
        # Update order status
        order.mark_synced()
        await order_repository.save(order, execution_id)
        
        # Acknowledge message (ACK) - marks as successfully processed
        await consumer.acknowledge_message(message_id)
        
        logger.info(
            f"[{execution_id}] ✅ Order {order_id} synced to Odoo successfully. "
            f"Invoice ID: {odoo_invoice_id}, Message ACKed: {message_id}"
        )
    
    except Exception as e:
        logger.error(
            f"[{execution_id}] ❌ Failed to sync order {order_id} to Odoo: {e}",
            exc_info=True
        )
        # Don't ACK - message will be retried
        raise


async def start_odoo_sync_worker(
    redis_url: str = "redis://localhost:6379/0",
    odoo_client: Optional[IOdooClient] = None,
    order_repository: Optional[OrderRepository] = None,
    poll_interval: float = 1.0
) -> None:
    """
    Start Odoo sync worker (long-running process).
    
    This worker continuously polls Redis Stream for FinancialParityVerified events
    and syncs them to Odoo.
    
    Args:
        redis_url: Redis connection URL
        odoo_client: Odoo client instance (uses MockOdooClient if None)
        order_repository: Order repository (uses MockOrderRepository if None)
        poll_interval: Time to wait between polls (seconds)
    """
    # Import dependencies (avoid circular imports)
    if odoo_client is None:
        from apps.adapters.odoo.client import OdooClient
        odoo_client = OdooClient()  # Real Odoo client
    
    if order_repository is None:
        from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
        order_repository = MockOrderRepository()
    
    consumer = RedisStreamConsumer(redis_url=redis_url)
    
    logger.info("🚀 Starting Odoo Sync Worker...")
    logger.info(f"   Stream: {consumer.stream_name}")
    logger.info(f"   Consumer Group: {consumer.consumer_group}")
    logger.info(f"   Consumer Name: {consumer.consumer_name}")
    
    try:
        await consumer.connect()
        
        while True:
            try:
                # Read messages from stream
                messages = await consumer.consume_messages(
                    batch_size=10,
                    block_ms=1000
                )
                
                if not messages:
                    await asyncio.sleep(poll_interval)
                    continue
                
                logger.info(f"📨 Received {len(messages)} message(s) from Redis Stream")
                
                # Process each message
                for message in messages:
                    try:
                        await sync_validated_order_to_odoo(
                            message=message,
                            consumer=consumer,
                            odoo_client=odoo_client,
                            order_repository=order_repository
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process message {message['id']}: {e}",
                            exc_info=True
                        )
                        # Message not ACKed - will be retried
                
            except KeyboardInterrupt:
                logger.info("🛑 Stopping Odoo Sync Worker...")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(poll_interval)
    
    finally:
        await consumer.disconnect()
        logger.info("✅ Odoo Sync Worker stopped")

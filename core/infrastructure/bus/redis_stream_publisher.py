"""
Redis Streams Publisher for Event-Driven Architecture.

Publishes domain events to Redis Streams for reliable message delivery.
Decouples validation from synchronization, eliminating SQLAlchemy async issues.
"""
import json
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

import redis.asyncio as aioredis


logger = logging.getLogger(__name__)


class RedisStreamPublisher:
    """
    Publishes events to Redis Streams.
    
    Uses Redis Streams for reliable message delivery with:
    - Persistence (messages survive Redis restart)
    - Consumer groups (load balancing)
    - Message acknowledgment (reliability)
    - Time-ordered delivery
    
    Stream format: konozy:finance:stream
    Message format: {
        "order_id": str,
        "sku": str,
        "net_proceeds": str,  # Decimal as string
        "account_id": int,
        "timestamp": str,  # ISO format
    }
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        stream_name: str = "konozy:finance:stream"
    ):
        """
        Initialize Redis Stream Publisher.
        
        Args:
            redis_url: Redis connection URL
            stream_name: Redis Stream name
        """
        self.redis_url = redis_url
        self.stream_name = stream_name
        self._redis_client: Optional[aioredis.Redis] = None
    
    async def connect(self) -> None:
        """Establish Redis connection."""
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
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            logger.info("✅ Disconnected from Redis")
    
    async def publish_financial_parity_verified(
        self,
        order_id: str,
        sku: str,
        net_proceeds: Decimal,
        account_id: int
    ) -> str:
        """
        Publish FinancialParityVerified event to Redis Stream.
        
        This event is published when:
        - Parity test passes for an order/SKU
        - Financial validation is complete
        - Ready for Odoo synchronization
        
        Args:
            order_id: Amazon order ID
            sku: Product SKU
            net_proceeds: Net proceeds amount (Decimal)
            account_id: Odoo account ID for this SKU
        
        Returns:
            Message ID from Redis Stream
        
        Example:
            >>> publisher = RedisStreamPublisher()
            >>> await publisher.connect()
            >>> msg_id = await publisher.publish_financial_parity_verified(
            ...     order_id="171-5168422-9744326",
            ...     sku="G30-RED",
            ...     net_proceeds=Decimal("529.03"),
            ...     account_id=1075
            ... )
        """
        if self._redis_client is None:
            await self.connect()
        
        # Build message payload
        message: Dict[str, Any] = {
            "event_type": "FinancialParityVerified",
            "order_id": order_id,
            "sku": sku,
            "net_proceeds": str(net_proceeds),  # Decimal as string for JSON
            "account_id": str(account_id),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            # Publish to Redis Stream
            msg_id = await self._redis_client.xadd(
                self.stream_name,
                message,
                maxlen=10000  # Keep last 10k messages
            )
            
            logger.info(
                f"✅ Published FinancialParityVerified event: "
                f"order={order_id}, sku={sku}, net={net_proceeds}, "
                f"account={account_id}, msg_id={msg_id}"
            )
            
            return msg_id
        
        except Exception as e:
            logger.error(
                f"Failed to publish to Redis Stream: {e}",
                exc_info=True
            )
            raise
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Global publisher instance (lazy initialization)
_global_publisher: Optional[RedisStreamPublisher] = None


def get_redis_stream_publisher(
    redis_url: Optional[str] = None,
    stream_name: Optional[str] = None
) -> RedisStreamPublisher:
    """
    Get or create global Redis Stream Publisher instance.
    
    Args:
        redis_url: Optional Redis URL (uses default if None)
        stream_name: Optional stream name (uses default if None)
    
    Returns:
        Global RedisStreamPublisher instance
    """
    global _global_publisher
    
    if _global_publisher is None:
        _global_publisher = RedisStreamPublisher(
            redis_url=redis_url or "redis://localhost:6379/0",
            stream_name=stream_name or "konozy:finance:stream"
        )
    
    return _global_publisher

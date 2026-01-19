"""
Snapshot Store Implementation.

Manages aggregate snapshots for Event Sourcing optimization.
Snapshots allow rebuilding aggregates without replaying all events.

Architecture:
- Part of Event Sourcing optimization
- Reduces event replay overhead
- Maintains backward compatibility (works without snapshots)
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from core.infrastructure.database.models import SnapshotModel


logger = logging.getLogger(__name__)


class SnapshotStore:
    """
    Snapshot Store for aggregate snapshots.
    
    Features:
    - Store aggregate state snapshots
    - Retrieve latest snapshot for aggregate
    - Support snapshot versioning
    - Optimize event replay performance
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize snapshot store.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def save_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        snapshot_data: Dict[str, Any],
        sequence_number: int,
        snapshot_version: int = 1
    ) -> None:
        """
        Save aggregate snapshot.
        
        Args:
            aggregate_id: Aggregate identifier
            aggregate_type: Type of aggregate (e.g., "Order")
            snapshot_data: Complete aggregate state as dictionary
            sequence_number: Last event sequence number included in snapshot
            snapshot_version: Snapshot schema version
        """
        logger.info(
            f"Saving snapshot for {aggregate_type} {aggregate_id} "
            f"(sequence: {sequence_number})"
        )
        
        snapshot = SnapshotModel(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            snapshot_data=snapshot_data,
            sequence_number=sequence_number,
            snapshot_version=snapshot_version,
        )
        
        try:
            self.session.add(snapshot)
            await self.session.flush()
            
            logger.info(
                f"✅ Snapshot saved: {aggregate_type} {aggregate_id} "
                f"(sequence: {sequence_number})"
            )
        
        except IntegrityError as e:
            logger.warning(
                f"Snapshot already exists for {aggregate_id} at sequence {sequence_number}: {e}"
            )
            # Rollback and continue (snapshot might already exist)
            await self.session.rollback()
            raise
    
    async def get_latest_snapshot(
        self,
        aggregate_id: str
    ) -> Optional[SnapshotModel]:
        """
        Get latest snapshot for aggregate.
        
        Args:
            aggregate_id: Aggregate identifier
        
        Returns:
            Latest snapshot model, or None if no snapshot exists
        """
        query = select(SnapshotModel).where(
            SnapshotModel.aggregate_id == aggregate_id
        ).order_by(
            SnapshotModel.sequence_number.desc()
        ).limit(1)
        
        result = await self.session.execute(query)
        snapshot = result.scalar_one_or_none()
        
        if snapshot:
            logger.debug(
                f"Found snapshot for {aggregate_id} "
                f"at sequence {snapshot.sequence_number}"
            )
        else:
            logger.debug(f"No snapshot found for {aggregate_id}")
        
        return snapshot
    
    async def snapshot_exists(
        self,
        aggregate_id: str,
        sequence_number: int
    ) -> bool:
        """
        Check if snapshot exists for aggregate at specific sequence.
        
        Args:
            aggregate_id: Aggregate identifier
            sequence_number: Sequence number to check
        
        Returns:
            True if snapshot exists, False otherwise
        """
        query = select(func.count(SnapshotModel.id)).where(
            SnapshotModel.aggregate_id == aggregate_id,
            SnapshotModel.sequence_number == sequence_number
        )
        
        result = await self.session.execute(query)
        count = result.scalar()
        
        return count > 0
    
    async def get_snapshot_count(self, aggregate_id: str) -> int:
        """
        Get number of snapshots for aggregate.
        
        Args:
            aggregate_id: Aggregate identifier
        
        Returns:
            Number of snapshots
        """
        query = select(func.count(SnapshotModel.id)).where(
            SnapshotModel.aggregate_id == aggregate_id
        )
        
        result = await self.session.execute(query)
        count = result.scalar()
        
        return count or 0

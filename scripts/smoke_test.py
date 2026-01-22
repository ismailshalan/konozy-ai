"""Konozy AI Smoke Test - Async Version"""

import asyncio
import uuid
import traceback
import sys
from pathlib import Path
from typing import Tuple

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.database.lifecycle import (
    init_database,
    get_session_factory,
    close_database,
)
from core.infrastructure.database.event_store import EventStore
from core.domain.events.order_events import OrderCreatedEvent


async def smoke_test() -> Tuple[bool, str]:
    """Run async smoke test."""
    try:
        print("=" * 80)
        print("🚀 KONOZY AI SMOKE TEST (ASYNC)")
        print("=" * 80)

        print("\n[1/5] Initializing database...")
        await init_database()
        session_factory = get_session_factory()
        print("✅ Database initialized")

        print("\n[2/5] Creating async session...")
        async with session_factory() as session:
            print("✅ Session created")

            print("\n[3/5] Creating EventStore...")
            store = EventStore(session)
            order_id = f"SMOKE-{uuid.uuid4()}"
            event = OrderCreatedEvent(
                order_id=order_id,
                marketplace="SmokeTest",
                buyer_email="smoke@test.com",
                purchase_date="2024-01-01",
            )
            print(f"✅ Event created: {order_id}")

            print("\n[4/5] Appending event...")
            await store.append(event)
            await session.commit()
            print("✅ Event appended and committed")

            print("\n[5/5] Retrieving events...")
            events = await store.get_events(order_id)

            assert len(events) == 1, f"Expected 1 event, got {len(events)}"
            assert events[0].aggregate_id == order_id
            assert events[0].event_type == "OrderCreatedEvent"
            print("✅ Event retrieved and validated")

        print("\n" + "=" * 80)
        print("✅ SMOKE TEST PASSED: System is healthy")
        print("=" * 80)

        return True, "All tests passed"

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ SMOKE TEST FAILED")
        print("=" * 80)
        print(f"\nError: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        return False, str(e)

    finally:
        await close_database()


async def main() -> int:
    """Main entry point."""
    success, _ = await smoke_test()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

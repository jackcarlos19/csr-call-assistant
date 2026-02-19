import asyncio
import os
import sys
import uuid

sys.path.append(os.getcwd())

from app.models.call_session import CallSession
from app.services.rule_service import RuleService


async def verify_engine():
    print("1. Instantiating RuleService...")
    service = RuleService()

    mock_session = CallSession(
        id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        tenant_id="default",
    )

    test_text = "I can guarantee we will have someone there today."
    print(f"2. Analyzing text: {test_text}")

    events = await service.evaluate_segment(mock_session, test_text)

    print(f"\n--- Result: {len(events)} Rule Violations Found ---")
    for event in events:
        print(f"Type: {event.type}")
        print(f"Rule ID: {event.payload.get('rule_id')}")
        print(f"Message: {event.payload.get('message')}")


if __name__ == "__main__":
    asyncio.run(verify_engine())

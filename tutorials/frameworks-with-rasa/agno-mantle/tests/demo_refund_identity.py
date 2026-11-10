"""Deliberately break the demo customer mapping while keeping policy unchanged.

This uses the pinned native invoker and fixture contexts, not a model turn.
The altered resolver exists only inside the patch context and is restored.
"""
import asyncio
import json
from unittest.mock import patch

from test_refund_binding import RefundBinding
from shop_adviser.scope_binding import CustomerScope


async def demonstrate():
    fixture = RefundBinding("runTest")
    fixture.setUp()
    before = await fixture.ask("willow-b-chat", order_ref="WS-RETURN-01")
    with patch.object(fixture.tools, "resolve_demo_scope",
                      return_value=CustomerScope("customer-a", "deliberately-wrong")):
        broken = await fixture.ask("willow-b-chat", order_ref="WS-RETURN-01")
    restored = await fixture.ask("willow-b-chat", order_ref="WS-RETURN-01")
    assert before == restored == {"status": "unknown_order"}
    assert broken == {"status": "full_refund_offer", "amount_minor": 1299,
                      "currency": "GBP"}
    return {"sender": "willow-b-chat", "order_ref": "WS-RETURN-01",
            "correct_mapping": before, "deliberately_wrong_mapping": broken,
            "restored_mapping": restored}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(demonstrate()), indent=2))

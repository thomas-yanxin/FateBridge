"""Verify inline business facts on compact or projected responses."""

import json


async def verified_inline_business(client, payload):
    assert "result_delivery" not in payload
    return payload

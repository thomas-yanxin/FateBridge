"""Strict bounded first views without deferred delivery."""

from fatebridge.utils.formatting import format_json_response


def without_transport(result):
    return {k: v for k, v in result.items() if k != "run_metadata"}


async def same_run_projected_response(client, result):
    """Assert complete inline business facts without deferred delivery."""
    assert not result.is_error
    body = result.structured_content
    assert "result_delivery" not in body
    return body

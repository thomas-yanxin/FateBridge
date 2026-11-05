"""The selected local time type is checked before every public projection."""

import asyncio

import pytest

from tests.support.meihua_unspecified_clock_reference import load
from tests.support.transports import SPECS, call_cli, native, rest

SPEC = SPECS["meihua_analysis"]
ROWS = load()


def replies(row, rest, tmp_path, capsys):
    response = rest.post(
        SPEC.rest_path,
        json=row["arguments"],
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "unspecified-clock",
            "response_char_limit": "0",
        },
    )
    reply = asyncio.run(
        native(
            SPEC,
            row["arguments"],
            fields=["analysis_type"],
            strict_fields=True,
            trace_id="unspecified-clock",
        )
    )
    code, cli = call_cli(
        SPEC,
        row["arguments"],
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--trace-id",
            "unspecified-clock",
            "--response-char-limit",
            "0",
        ],
    )
    return response, reply, code, [response.json(), reply.structured_content, cli]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["case"]["id"])
def test_original355_requests_keep_frozen_outcomes_before_projection(
    row, rest, tmp_path, capsys
):
    response, reply, code, values = replies(row, rest, tmp_path, capsys)
    if row["case"]["expected_clock_resolvable"]:
        assert response.status_code == 200 and not reply.is_error and code == 0
        for value in values:
            assert "error" not in value
    else:
        assert response.status_code == 422 and reply.is_error and code == 1
        for value in values:
            assert value["error_code"] == "validation_error"
            assert value["retryable"] is False
            assert value["trace_id"] == "unspecified-clock"
            assert "result_delivery" not in value
            if row["case"].get("status") == "selected_unspecified_type":
                assert value["issues"] == [
                    {"path": "analysis_timezone", "code": "unresolved_timezone_offset"}
                ]

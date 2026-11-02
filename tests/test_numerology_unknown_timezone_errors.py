"""Typed timezone rejection survives the domain guard without echoing input."""

import json
from datetime import datetime

import pytest
from pydantic_core import PydanticCustomError

from fatebridge.utils.errors import (
    UNRESOLVED_OFFSET_MESSAGE,
    handle_calculation_error,
)
from fatebridge.utils.timezones import (
    parse_timezone_name,
    validate_local_clock,
)


def test_real_tzif_rejection_keeps_its_type_across_domain_guard():
    at = datetime(1900, 1, 1, 12, tzinfo=parse_timezone_name("Antarctica/Casey"))
    with pytest.raises(PydanticCustomError) as caught:
        validate_local_clock(at)
    result = handle_calculation_error(caught.value, "河洛测试")
    assert result == {
        "error": UNRESOLVED_OFFSET_MESSAGE,
        "error_code": "validation_error",
        "status_code": 422,
        "retryable": False,
        "issues": [{"path": "request", "code": "unresolved_timezone_offset"}],
    }


def test_typed_hint_uses_the_canonical_message_without_private_error_text():
    error = PydanticCustomError(
        "unresolved_timezone_offset", "private birthrecord /private/path"
    )
    result = handle_calculation_error(error, "测试")
    assert result["error"] == UNRESOLVED_OFFSET_MESSAGE
    assert result["issues"] == [
        {"path": "request", "code": "unresolved_timezone_offset"}
    ]
    assert "private" not in json.dumps(result)


def test_plain_text_cannot_impersonate_a_typed_timezone_rejection():
    error = ValueError("unresolved_timezone_offset " + UNRESOLVED_OFFSET_MESSAGE)
    result = handle_calculation_error(error, "测试")
    assert result["status_code"] == 400 and result["error_code"] == "validation_error"
    assert "issues" not in result


def test_other_custom_errors_keep_the_existing_domain_input_contract():
    result = handle_calculation_error(
        PydanticCustomError("another_type", "other failure"), "测试"
    )
    assert result == {
        "error": "other failure",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }

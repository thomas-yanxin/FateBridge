"""Source-consistency failures retain safe, actionable transport semantics."""

import pytest

from fatebridge.utils.errors import (
    EphemerisSourceError,
    calculation_guard,
    handle_calculation_error,
)


@pytest.mark.parametrize("reason", sorted(EphemerisSourceError.MESSAGES))
def test_typed_source_failure_is_not_rewritten_as_missing_dependency(reason):
    @calculation_guard("source check")
    def reject():
        raise EphemerisSourceError(reason)

    result = reject()
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503
    assert result["retryable"] is False
    assert result["issues"] == [{"path": "runtime.ephemeris_data", "code": reason}]
    assert result["error"] == EphemerisSourceError.MESSAGES[reason]


def test_arbitrary_raw_details_cannot_be_used_as_safe_source_messages():
    private = "/private/server/ephemeris/data"
    with pytest.raises(ValueError) as caught:
        EphemerisSourceError(private)
    assert private not in str(caught.value)


@pytest.mark.parametrize(
    "error,code,status",
    [
        (ImportError("swisseph unavailable"), "dependency_missing", 503),
        (ValueError("missing ephemeris dependency"), "dependency_missing", 503),
        (ValueError("Invalid calendar date"), "validation_error", 400),
    ],
)
def test_other_error_classifications_are_preserved(error, code, status):
    result = handle_calculation_error(error, "legacy check")
    assert result["error_code"] == code
    assert result["status_code"] == status

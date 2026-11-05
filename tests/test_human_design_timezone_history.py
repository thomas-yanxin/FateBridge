"""Unspecified historical offsets must never become asserted UTC births."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ValidationError, model_validator

from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.utils.errors import validation_error_result
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "tests/data/human_design/timezone"
VECTORS = json.loads((E / "unspecified-offset-control-vectors.json").read_text())[
    "vectors"
]


def test_typed_unknown_offset_has_an_actionable_private_input_free_error():
    with pytest.raises(ValidationError) as caught:
        HumanDesignRequest(
            birth_year=1900,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="Antarctica/Casey",
        )
    result = validation_error_result(caught.value)
    assert result["issues"] == [
        {"path": "request", "code": "unresolved_timezone_offset"}
    ]
    assert "已核实的出生钟时偏移" in result["error"]
    assert "Antarctica/Casey" not in json.dumps(result)


def test_plain_value_error_text_cannot_impersonate_the_public_typed_hint():
    class Fake(BaseModel):
        @model_validator(mode="after")
        def fail(self):
            raise ValueError(
                "unresolved local time /private/source-path private birth record"
            )

    with pytest.raises(ValidationError) as caught:
        Fake()
    result = validation_error_result(caught.value)
    assert result["error"] == "请求参数无效"
    assert result["issues"] == [{"path": "request", "code": "value_error"}]
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("row", VECTORS, ids=lambda r: r["name"])
def test_all16_frozen_named_unknown_offset_controls_reject_without_native(row):
    wall = datetime.fromisoformat(row["local_label"])
    moment = wall.replace(tzinfo=parse_timezone_name(row["name"]))
    assert moment.utcoffset() == timedelta(0)
    assert moment.tzname() == row["abbreviation"] == "-00"
    arguments = dict(
        birth_year=wall.year,
        birth_month=wall.month,
        birth_day=wall.day,
        birth_hour=wall.hour,
        birth_minute=wall.minute,
        birth_second=wall.second,
        birth_timezone=row["name"],
    )
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("unresolved clock must not call native"),
    ):
        with pytest.raises(ValueError, match="unresolved local time"):
            validate_local_clock(moment)
        with pytest.raises(ValueError, match="unresolved local time"):
            resolve_birth_clock(**arguments)
        with pytest.raises(ValueError, match="unresolved local time"):
            HumanDesignRequest(**arguments)


@pytest.mark.parametrize(
    "zone", ["UTC", "GMT", "+00:00", "-00:00", "0", "Etc/GMT", "Europe/London"]
)
def test_known_zero_offsets_are_still_valid(zone):
    value = resolve_birth_clock(
        birth_year=1900,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=zone,
    )
    assert value.utc_label == "1900-01-01T12:00:00+00:00"


@pytest.mark.parametrize(
    "zone,year,known",
    [
        ("Antarctica/Casey", 2000, True),
        ("Antarctica/Troll", 2000, False),
        ("Antarctica/Troll", 2010, True),
        ("America/Cambridge_Bay", 2000, True),
    ],
)
def test_named_zone_resolution_follows_its_actual_period(zone, year, known):
    arguments = dict(
        birth_year=year,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=zone,
    )
    if not known:
        with pytest.raises(ValueError, match="unresolved local time"):
            resolve_birth_clock(**arguments)
        return
    value = resolve_birth_clock(**arguments)
    assert value.local_anchor.tzname() != "-00"
    assert value.utc_anchor == value.local_anchor.astimezone(timezone.utc)

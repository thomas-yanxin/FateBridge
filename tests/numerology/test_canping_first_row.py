"""Keep the actual first row available without inventing a dated legacy period."""

import ast
import gzip
import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta
from dateutil.tz import resolve_imaginary
from pydantic import ValidationError

from fatebridge.application.examples import evidence_views
from fatebridge.application.projection import project_fields
from fatebridge.core import almanac
from fatebridge.core.astro.time_scales import datetime_from_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.canping_schedule_validation import require_schedule_binding
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.output_chinese import CanpingTiming
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.timezones import parse_timezone_name

REFERENCES = json.loads(
    (Path(__file__).parents[1] / "data/canping/first_row_inputs.json").read_bytes()
)
SPEC = next(s for s in CATALOG if s.key == "canping")
# HKO table1, transcribed independently of the production name/angle arrays:
# https://www.hko.gov.hk/sc/gts/time/24solarterms.htm
from tests.support.solar_source_facts import HKO_TERM_LONGITUDES


def test_literal_term_targets_match_the_published_hko_table():
    assert len(HKO_TERM_LONGITUDES) == 24
    assert dict(zip(almanac.SOLAR_TERM_NAMES, almanac.SOLAR_TERM_LONGITUDES)) == (
        HKO_TERM_LONGITUDES
    )


@pytest.fixture(autouse=True)
def native_model(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", "/tmp/fatebridge-heluo-fiftysecond/empty-ephe")


@pytest.mark.parametrize(
    "profile", ["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]
)
def test_published_policy_view_keeps_first_row_without_entire_timeline(profile):
    r = next(r for r in REFERENCES if r["arguments"]["dayun_method"] == profile)
    out = build_canping_result(**r["arguments"])
    fields = evidence_views(SPEC)["timing_policy"]["fields"]
    assert "canping_timing.first_row" in fields
    projected = project_fields(out, fields, strict_fields=True)
    assert projected["canping_timing"]["first_row"] == out["dayun"][0]
    assert "dayun" not in projected and "liunian_series" not in projected
    SPEC.output_model.model_validate(projected)


FAULTS = [
    ("uncomputed_claim", "invented"),
    ("numShun", 1111),
    ("branch", "子"),
    ("index", 9),
    ("end_at", "2100-01-01T00:00:00+00:00"),
    ("start_age", 999),
    ("verses.textShun", "无据测试改文"),
    ("verses.selectionShun.column", "middle_female"),
]


@pytest.mark.parametrize("summary", ["first_row", "first_period"])
@pytest.mark.parametrize("path,value", FAULTS)
def test_wrong_summary_facts_cannot_survive_complete_output_validation(
    summary, path, value
):
    out = deepcopy(
        next(
            build_canping_result(**r["arguments"])
            for r in REFERENCES
            if r["arguments"]["dayun_method"] == "bazi_appendix_v1"
        )
    )
    out["canping_timing"]["first_row"] = deepcopy(out["dayun"][0])
    p = out["canping_timing"][summary]
    keys = path.split(".")
    for key in keys[:-1]:
        p = p[key]
    p[keys[-1]] = value
    with pytest.raises(NumerologySourceError):
        require_schedule_binding(out)


def test_coherent_but_wrong_two_summaries_do_not_override_the_actual_row():
    out = deepcopy(
        next(
            build_canping_result(**r["arguments"])
            for r in REFERENCES
            if r["arguments"]["dayun_method"] == "bazi_appendix_v1"
        )
    )
    wrong = deepcopy(out["dayun"][1])
    wrong["start_at"] = out["dayun"][0]["start_at"]
    out["canping_timing"]["first_period"] = deepcopy(wrong)
    out["canping_timing"]["first_row"] = deepcopy(wrong)
    with pytest.raises(NumerologySourceError):
        require_schedule_binding(out)


def test_nonempty_summaries_cannot_survive_an_empty_actual_sequence():
    out = build_canping_result(**REFERENCES[0]["arguments"])
    out["canping_timing"]["first_row"] = deepcopy(out["dayun"][0])
    out["dayun"] = []
    with pytest.raises(NumerologySourceError):
        require_schedule_binding(out)


def test_empty_actual_sequence_does_not_invent_a_missing_summary():
    CanpingTiming.model_validate({"first_row": None, "first_period": None})
    require_schedule_binding({"dayun": [], "canping_timing": {}})


@pytest.mark.parametrize(
    "key",
    [
        "start_at",
        "end_at",
        "start_age",
        "end_age",
        "at",
        "dayun_index",
        "year_start_boundary",
    ],
)
def test_legacy_partial_row_does_not_gain_actual_dates_or_query_identity(key):
    value = {
        "year_start_boundary": {},
        "start_age": 1,
        "end_age": 11,
        "dayun_index": 0,
    }.get(key, "2032-01-01T00:00:00+00:00")
    with pytest.raises(ValidationError):
        CanpingTiming.model_validate(
            {"profile_id": "legacy_minggong_v1", "first_row": {key: value}}
        )


def test_partial_schema_preserves_omission_and_known_legacy_null():
    for value in [
        {},
        {"first_row": None},
        {"first_row": {"numShun": 2440}},
        {
            "profile_id": "legacy_minggong_v1",
            "first_period": None,
            "first_row": {"ageStart": 1, "ageEnd": 10},
        },
    ]:
        parsed = CanpingTiming.model_validate(value)
        assert parsed.model_dump(exclude_unset=True) == value
    assert "first_row" in CanpingTiming.model_fields

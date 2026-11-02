"""Keep the actual first row available without inventing a dated legacy period."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import evidence_views
from fatebridge.application.projection import project_fields
from fatebridge.core.canping_schedule_validation import require_schedule_binding
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.output_chinese import CanpingTiming
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import NumerologySourceError
from tests.canping_witness_fixture_compat import upgrade_frozen_witnesses
from tests.test_numerology_solar_providers import (
    preserve_original_canping_snapshot_with_source_changes_checked,
)

FIX = Path(__file__).parent / "fixtures/canping_first_row_v1"
REFERENCES = json.loads(gzip.decompress((FIX / "reference.json.gz").read_bytes()))
SPEC = next(s for s in CATALOG if s.key == "canping")


@pytest.fixture(autouse=True)
def native_model(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", "/tmp/fatebridge-heluo-fiftysecond/empty-ephe")


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda r: r["id"])
def test_same_result_first_row_keeps_all_prior_business_facts(reference):
    frozen_reference = reference
    assert reference["expected_first_row"] == reference["output"]["dayun"][0]
    upgraded = upgrade_frozen_witnesses(reference["output"])
    reference = {
        **reference,
        "output": upgraded,
        "expected_first_row": upgraded["dayun"][0],
    }
    out = build_canping_result(**reference["arguments"])
    timing = out["canping_timing"]
    assert timing["first_row"] == reference["expected_first_row"] == out["dayun"][0]
    assert timing["first_row"] is not out["dayun"][0]
    assert timing["first_row"]["verses"] is not out["dayun"][0]["verses"]
    original = deepcopy(out)
    del original["canping_timing"]["first_row"]
    original = preserve_original_canping_snapshot_with_source_changes_checked(
        original, frozen_reference["output"]
    )
    assert original == reference["output"]
    if timing["profile_id"] == "legacy_minggong_v1":
        assert timing["first_period"] is None
        assert (
            not {"start_at", "end_at", "start_age", "end_age"}
            & timing["first_row"].keys()
        )
    else:
        assert timing["first_row"] == timing["first_period"]
        assert timing["first_row"] is not timing["first_period"]
    if reference["id"].startswith("queried-"):
        assert timing["selected"]["dayun_index"] > 0
        assert timing["first_row"]["index"] == 0
        # Use the same result after validating the three added clock labels above.
        assert (
            original["canping_timing"]["selected"]
            == reference["output"]["canping_timing"]["selected"]
        )
    SPEC.output_model.model_validate(out)
    require_schedule_binding(out)


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
            r["output"]
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
            r["output"]
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
    out = deepcopy(REFERENCES[0]["output"])
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

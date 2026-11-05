"""Cross-run source mutation and mixed-generation traces must be impossible."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, rulesets
from fatebridge.core.sukuyo_activities import source_bundle as activity_source
from fatebridge.core.sukuyo_profiles import (
    SOURCE,
    fullmoon_calculation,
    select_profile,
    source_bundle,
)
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.services.tool_catalog import CATALOG

PRIMARY = json.loads(
    (Path(__file__).parent / "data/sukuyo-fullmoon-primary.json").read_text()
)
HINOO_PRIMARY = json.loads(
    (Path(__file__).parent / "data/sukuyo-hinoo-primary-cache.json").read_text()
)


def test_mutating_returned_anchor_does_not_poison_both_agreeing_algorithms():
    assert fullmoon_calculation(1, 15, SU27_ORDER)["direct_mansion"] == "翼"
    exposed = source_bundle()
    exposed["fullmoon_anchors"][0]["fullmoon_mansion"] = "角"
    exposed["hinoo_addendum"]["half_interpretation"] = "fabricated noon rule"
    for month, anchor in enumerate(PRIMARY["anchors"], 1):
        # The frozen primary text, rather than agreement between the two
        # formulas, supplies the expected full-moon anchor.
        result = fullmoon_calculation(month, 15, SU27_ORDER)
        expected = anchor.translate(str.maketrans("虛婁畢參張軫", "虚娄毕参张轸"))
        assert result["direct_mansion"] == result["shortcut_mansion"] == expected
    assert (
        source_bundle()["hinoo_addendum"]["half_interpretation"]
        != "fabricated noon rule"
    )


def test_loaded_data_cannot_change_future_runs_or_its_fingerprint(tmp_path):
    path = tmp_path / "source.json"
    raw = b'{"nested": {"rows": [1, 2]}, "value": "original"}'
    path.write_bytes(raw)
    loaded = load_source(path)
    first = loaded.data
    first["nested"]["rows"].append(99)
    first["value"] = "changed"
    assert loaded.data == {"nested": {"rows": [1, 2]}, "value": "original"}
    assert loaded.sha256 == hashlib.sha256(raw).hexdigest()
    # A disk replacement does not pair an old cached parse with a new hash.
    path.write_text('{"value":"replacement"}')
    assert load_source(path).data == {"nested": {"rows": [1, 2]}, "value": "original"}
    assert load_source(path).sha256 == hashlib.sha256(raw).hexdigest()
    # Private cache implementation is not a claimed security boundary.


def test_other_source_helpers_also_return_detached_payloads():
    first = activity_source()
    original = deepcopy(first)
    first["rules"][0]["selectors"].clear()
    first["rules"].clear()
    assert activity_source() == original


def test_entire_hinoo_selection_uses_one_loaded_record(monkeypatch):
    from fatebridge.core import sukuyo_profiles as profiles

    record = load_source(SOURCE)
    calls = []

    def once(path):
        calls.append(path)
        if len(calls) > 1:
            pytest.fail("mixed source generations inside one profile calculation")
        return record

    previous = {
        "lunar_year": 1903,
        "lunar_month": 5,
        "lunar_day": 29,
        "is_leap_month": False,
        "before_regular_month": {
            "lunar_year": 1903,
            "lunar_month": 4,
            "lunar_day": 29,
            "is_leap_month": False,
        },
    }
    monkeypatch.setattr(profiles, "load_source", once)
    result = select_profile(
        5,
        1,
        True,
        SU27_ORDER,
        profile="hinoo_t1299_host27",
        leap_policy="unresolved",
        day_part="first_half",
        previous_lunar=previous,
    )
    assert len(calls) == 1
    assert (
        result["source_bundle_sha256"]
        == result["host_calculation"]["source_bundle_sha256"]
        == record.sha256
    )
    assert result["candidate_su27s"] == ["鬼", "参"]
    assert result["resolution_reason"] == "hinoo_leap_short_month_precedence_unresolved"
    previous["before_regular_month"]["lunar_day"] = 30
    assert (
        result["short_month_assignment"]["previous_lunar"]["before_regular_month"][
            "lunar_day"
        ]
        == 29
    )


def test_omitted_day_and_regular_day_expose_the_same_captured_table_hash():
    result = calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27")
    profile = result["profile_calculation"]
    assert (
        profile["source_bundle_sha256"]
        == profile["host_calculation"]["source_bundle_sha256"]
        == profile["short_month_assignment"]["omitted_day_calculation"][
            "source_bundle_sha256"
        ]
        == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    )
    assert result["candidate_su27s"] == ["星", "张"]
    # Editing a delivered source note cannot alter a later ruleset response.
    result["profile_calculation"]["hinoo_source"]["cached_primary_excerpt"]["windows"][
        0
    ]["text"] = "modified"
    assert (
        rulesets("hinoo_t1299_host27")["calendar"]["hinoo_addendum"][
            "cached_primary_excerpt"
        ]["windows"][0]["text"]
        == HINOO_PRIMARY["windows"][0]["text"]
    )


def test_cached_primary_passage_hash_is_explicitly_not_a_full_source_hash():
    cached = source_bundle()["hinoo_addendum"]["cached_primary_excerpt"]
    assert cached == HINOO_PRIMARY
    assert cached["complete_original_source_bytes_sha256"] is None
    assert cached["facsimile_collation_complete"] is False
    for window in cached["windows"]:
        assert (
            hashlib.sha256(window["text"].encode()).hexdigest()
            == window["normalized_excerpt_utf8_sha256"]
        )
    assert "三十日直宿是星宿" in cached["windows"][0]["text"]
    assert (
        "半已上" in cached["windows"][1]["text"]
        and "半已下" in cached["windows"][1]["text"]
    )
    assert "12:00" in " ".join(cached["reading_notes"])


def test_public_schema_declares_captured_profile_and_host_fingerprints():
    for key in ["suzhan", "sukuyo_compatibility"]:
        spec = next(s for s in CATALOG if s.key == key)
        defs = spec.output_model.model_json_schema()["$defs"]
        assert "source_bundle_sha256" in defs["SukuyoCalendarProfile"]["properties"]
        assert "source_bundle_sha256" in defs["SukuyoFullmoonCalculation"]["properties"]

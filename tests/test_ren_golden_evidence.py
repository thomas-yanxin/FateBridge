"""Golden clock entry points freeze real instants and unwind failed entries."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import fatebridge.core.almanac as almanac
import fatebridge.core.execution_context as clock
import fatebridge.core.predictive._common as predictive
from scripts.audit_ren_golden_evidence import (
    KEYS,
    ORIGINALS,
    SLUGS,
    plan,
    reference,
    semantic_check,
)
from scripts.jinkou_archive_proofs import ARCHIVE_SNAPSHOTS
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.golden import runner
from tests.golden.canonical import canonical_json
from tests.ren_archive_contract import (
    NOMINAL_SEASONAL_GAP,
    assert_historical_contract_gap,
)
from tests.test_agentic_nested_outputs import AS_OF, SPECS, call_cli, native, rest


def test_additive_trace_migration_keeps_already_collated_source_fields():
    from scripts.audit_ren_golden_evidence import verify_change

    ref = reference()
    current = ref["natal_course_additions"]["jinkou.rule_trace"]
    old = [t for t in current if t["rule_id"] != "jinkou.natal_branch_course"]
    verify_change(
        dict(path="jinkou.rule_trace", kind="changed", old=old, new=current), ref
    )


ROOT = Path(__file__).resolve().parents[1]


def state():
    return (
        almanac.current_datetime,
        predictive.current_datetime,
        clock.datetime,
        almanac.datetime,
    )


def test_golden_clock_uses_current_entry_points_and_preserves_parsing_classes():
    before = state()
    real_date = datetime(2026, 1, 1)
    with runner.freeze_clock():
        assert almanac.datetime is before[-1]
        assert isinstance(real_date, almanac.datetime)
        assert (
            clock.current_datetime(ZoneInfo("America/New_York")).isoformat()
            == "2025-12-31T23:00:00-05:00"
        )
        with clock.call_clock() as actual:
            assert actual.instant.isoformat() == "2026-01-01T04:00:00+00:00"
            assert (
                clock.current_datetime(ZoneInfo("America/New_York")).isoformat()
                == "2025-12-31T23:00:00-05:00"
            )
            assert (
                clock.current_datetime(ZoneInfo("Asia/Tokyo")).isoformat()
                == "2026-01-01T13:00:00+09:00"
            )
        # Existing historical fixture convention is retained separately.
        assert (
            almanac.current_datetime(ZoneInfo("America/New_York")).isoformat()
            == "2026-01-01T12:00:00-05:00"
        )
    assert state() == before


def test_golden_clock_rolls_back_earlier_patches_when_a_later_entry_is_missing(
    monkeypatch,
):
    first, _, utc, parsing = state()
    monkeypatch.delattr(predictive, "current_datetime")
    with pytest.raises(AttributeError, match="current_datetime"):
        with runner.freeze_clock():
            pytest.fail("Missing real entry points must not be silently skipped")
    assert almanac.current_datetime is first
    assert clock.datetime is utc and almanac.datetime is parsing
    assert clock.clock_snapshot() is None


def test_golden_clock_restores_after_body_failure():
    before = state()
    with pytest.raises(RuntimeError, match="body failure"):
        with runner.freeze_clock(), clock.call_clock():
            raise RuntimeError("body failure")
    assert state() == before and clock.clock_snapshot() is None


def test_nested_golden_clocks_restore_outer_epoch_and_existing_call_context():
    before = state()
    with clock.call_clock("2030-01-01T00:00:00Z"):
        with runner.freeze_clock():
            with clock.call_clock() as outer:
                with runner.freeze_clock(runner.FROZEN_NOW + timedelta(days=400)):
                    with clock.call_clock() as inner:
                        assert inner.instant - outer.instant == timedelta(days=400)
                assert clock.clock_snapshot() == outer.instant.isoformat()
        assert clock.clock_snapshot() == "2030-01-01T00:00:00+00:00"
    assert state() == before and clock.clock_snapshot() is None


@pytest.mark.parametrize(
    "wall,expected,fold",
    [
        (datetime(2021, 11, 7, 13, 30), "2021-11-07T01:30:00-04:00", 0),
        (datetime(2021, 11, 7, 14, 30), "2021-11-07T01:30:00-05:00", 1),
    ],
)
def test_utc_golden_provider_preserves_both_historical_repeated_clock_instants(
    wall, expected, fold
):
    zone = ZoneInfo("America/New_York")
    with runner.freeze_clock(wall):
        direct = clock.current_datetime(zone)
        assert direct.isoformat() == expected and direct.fold == fold
        with clock.call_clock():
            bound = clock.current_datetime(zone)
            assert bound.isoformat() == expected and bound.fold == fold


@pytest.mark.parametrize("slug", SLUGS)
def test_historical_envelopes_keep_hand_annotated_inputs_and_current_contract_gap(slug):
    from fatebridge.application.execution import validate_output
    from fatebridge.services.tool_catalog import CATALOG

    value = json.loads((ARCHIVE_SNAPSHOTS / (slug + ".json")).read_text())
    from scripts.jinkou_archive_proofs import historical_pattern_proofs

    # Historical files stay byte-identical. Current complete-contract validation
    # uses an explicit new, reversible proof annotation, not fabricated old data.
    value, supplement = historical_pattern_proofs(value)
    from scripts.liuren_ordered_archive import historical_ordered_patterns

    value, ordered_supplement = historical_ordered_patterns(value)
    from scripts.liuren_course_archive import historical_course_conditions

    value, course_supplement = historical_course_conditions(value)
    from scripts.liuren_day_placement_archive import historical_day_placements

    value, placement_supplement = historical_day_placements(value)
    from scripts.liuren_cross_harmony_archive import historical_cross_harmony

    value, cross_supplement = historical_cross_harmony(value)
    assert cross_supplement["original_restored_exactly"]
    assert cross_supplement["golden_files_written"] is False
    assert placement_supplement["existing_fields_unchanged"]
    assert course_supplement["existing_fields_unchanged"]
    assert ordered_supplement["existing_fields_unchanged"]
    assert (
        supplement["existing_fields_unchanged"]
        and supplement["golden_files_written"] is False
    )
    ref = reference()
    semantic_check(slug, value, ref)
    spec = next(s for s in CATALOG if s.key == KEYS[slug])
    assert_historical_contract_gap(
        spec, {k: v for k, v in value.items() if k != "run_metadata"}
    )
    # Deliberate receipt canonicalization is not a fabricated live receipt.
    assert "run_id" not in value["run_metadata"]
    assert value["run_metadata"]["engine_is_approximate"] is True
    boards = [value["liureng"]]
    if slug == SLUGS[-1]:
        boards.append(value["subresults"]["liureng_gods"]["liureng"])
    for board in boards:
        assert board["ruleset"]["classical_acceptance_passed"] is False
        assert (
            set(
                [
                    "branch_relations",
                    "emptiness_evidence",
                    "transmission_progression",
                    "seasonal_evidence",
                ]
            )
            <= board.keys()
        )
        assert all(
            r["published_date_reference"]["dates_equal"]
            for r in board["calendar_policy"]["solar_term_dependencies"]
        )
    if slug in ("api_cn_liureng_gods", "api_cn_liureng_runyear"):
        assert "上神与下神相合，以和合成局为先。" not in value["snapshot_text"]
        assert "不据合独断成局" in value["snapshot_text"]


@pytest.mark.parametrize("slug", SLUGS)
def test_scoped_migration_keeps_original_bytes_available_and_can_restore_old_object(
    slug,
):
    before = json.loads((ORIGINALS / (slug + ".json")).read_text())
    candidate = json.loads((ARCHIVE_SNAPSHOTS / (slug + ".json")).read_text())
    migrated, report = plan(slug, candidate, reference())
    assert report["original_object_restored_exactly"]
    assert not report["complete_business_output_contract_passed"]
    assert report["current_contract_error"] == NOMINAL_SEASONAL_GAP
    assert (
        migrated["four_pillars"] == before["four_pillars"]
        if "four_pillars" in before
        else migrated["subresults"]["liureng_gods"]["four_pillars"]
        == before["subresults"]["liureng_gods"]["four_pillars"]
    )


@pytest.mark.parametrize(
    "fault", ["transmission", "old_board_fact", "false_full_acceptance"]
)
def test_migration_cannot_hide_calculation_changes_or_certify_full_original_text(fault):
    candidate = json.loads((ARCHIVE_SNAPSHOTS / "api_cn_liureng_gods.json").read_text())
    if fault == "transmission":
        candidate["liureng"]["three_transmissions"]["initial"]["branch"] = "子"
    elif fault == "old_board_fact":
        candidate["liureng"]["board_order"] = "invented_order"
    else:
        candidate["liureng"]["ruleset"]["classical_acceptance_passed"] = True
    with pytest.raises((ValueError, AssertionError)):
        plan(SLUGS[0], candidate, reference())


@pytest.mark.parametrize("slug", SLUGS)
def test_golden_ren_facts_replay_on_actual_rest_native_mcp_and_cli(
    slug, rest, tmp_path, capsys
):
    spec = SPECS[KEYS[slug]]
    payload = REST_POST_CASES[spec.rest_path]()
    expected = json.loads(
        (ROOT / "tests/golden/snapshots" / (slug + ".json")).read_text()
    )

    def facts(body):
        obj = body["subresults"]["liureng_gods"] if slug == SLUGS[-1] else body
        result = {"four_pillars": obj["four_pillars"], "liureng": obj["liureng"]}
        for k in ("jinkou", "runyear"):
            if k in body:
                result[k] = body[k]
        return result

    with runner.golden_ephemeris(), runner.freeze_clock():
        http = rest.post(
            spec.rest_path,
            json=payload,
            params={"as_of": AS_OF, "response_char_limit": 0},
        )
        protocol = asyncio.run(native(spec, payload))
        code, cli = call_cli(
            spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
        )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    for body in [http.json(), protocol.structured_content, cli]:
        # Actual receipts are validated here; no fields are fabricated.
        spec.output_model.model_validate(body)
        assert canonical_json(facts(body)) == canonical_json(facts(expected))

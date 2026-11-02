"""Independent published-minute controls across explicit solar backends."""

import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year, is_calculated_solar_term
from fatebridge.core.metaphysics.taiyi_periods import period_frame
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.validation.taiyi_solar_sources import (
    FREEZE_SHA256,
    PROVIDERS,
    audit,
    load_references,
    seed_at,
    solar_source,
)

CORPUS = Path(__file__).parent / "fixtures/taiyi_jinjing_v30"
REFERENCES = load_references(CORPUS)
NAOJ = REFERENCES["cases"][:72]
SOLSTICES = [c for c in NAOJ if c["term"] in {"冬至", "夏至"}]


def test_source_manifest_and_all_three_complete_official_years():
    assert (
        FREEZE_SHA256
        == "f2ca0a76be813ae4c0e38c788dc2fb8231507acb9b1b07c878f837555c0f2724"
    )
    assert len(REFERENCES["cases"]) == 84
    assert len({(c["year"], c["term"]) for c in REFERENCES["cases"]}) == 72
    assert {
        y: len([c for c in NAOJ if c["year"] == y]) for y in (2025, 2026, 2027)
    } == {2025: 24, 2026: 24, 2027: 24}
    assert REFERENCES["expected_generated_from_production"] is False
    assert REFERENCES["tolerance_seconds"] == 60
    assert PROVIDERS == {"native": "swisseph", "de440": "jpl_de440"}


def test_hko_and_naoj_overlap_is_same_utc_including_october_date_change():
    naoj = {(c["year"], c["term"]): c for c in NAOJ}
    for case in REFERENCES["cases"][72:]:
        assert case["at_utc"] == naoj[(case["year"], case["term"])]["at_utc"]
    a = naoj[(2027, "霜降")]
    b = next(c for c in REFERENCES["cases"][72:] if c["term"] == "霜降")
    assert a["at_source"].startswith("2027-10-24")
    assert b["at_source"].startswith("2027-10-23")


@pytest.mark.parametrize("change", ["source", "case_and_manifest", "drop_case"])
def test_original_reference_pins_cannot_be_updated_around_failures(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    if change == "source":
        (target / "naoj-2027.html").write_bytes(b"changed")
    else:
        p = target / "cases.json"
        data = json.loads(p.read_text())
        if change == "drop_case":
            data["cases"].pop()
        else:
            data["cases"][0]["at_utc"] = "2025-01-01T00:00:00+00:00"
        p.write_text(json.dumps(data))
        p = target / "freeze.json"
        manifest = json.loads(p.read_text())
        manifest["files"]["cases.json"] = hashlib.sha256(
            (target / "cases.json").read_bytes()
        ).hexdigest()
        p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="指纹"):
        load_references(target)


def test_audit_source_policy_is_restored_after_failure(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    with pytest.raises(RuntimeError):
        with solar_source("native"):
            assert os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] == "native"
            raise RuntimeError("synthetic audit failure")
    assert os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] == "auto"


@pytest.mark.parametrize("source,provider", list(PROVIDERS.items()))
def test_all_official_records_keep_numeric_tolerance_and_strict_identity(
    source, provider
):
    with solar_source(source):
        terms = {
            y: {t.name: t for t in get_solar_terms_for_year(y, "UTC")}
            for y in (2025, 2026, 2027)
        }
        for case in REFERENCES["cases"]:
            term = terms[case["year"]][case["term"]]
            assert term.resolution_provider == provider
            assert is_calculated_solar_term(term)
            assert (
                abs(
                    (
                        term.moment - datetime.fromisoformat(case["at_utc"])
                    ).total_seconds()
                )
                <= 60
            ), case["id"]
            if source == "de440":
                assert term.ephemeris_model == "fatebridge_de440_solar_v1"
                for key in ("coefficient_sha256", "source_kernel_sha256"):
                    digest = term.solar_model_details[key]
                    assert len(digest) == 64 and all(
                        c in "0123456789abcdef" for c in digest
                    )


@pytest.mark.parametrize("source", list(PROVIDERS))
@pytest.mark.parametrize("profile", [None, "key_month_tianzheng_jie_v1"])
def test_jie_changes_month_and_zhongqi_does_not_for_all_three_years(source, profile):
    with solar_source(source):
        for case in NAOJ:
            at = datetime.fromisoformat(case["at_utc"])
            before = period_frame(
                seed_at(at - timedelta(minutes=2)), "month", month_profile=profile
            )
            after = period_frame(
                seed_at(at + timedelta(minutes=2)), "month", month_profile=profile
            )
            assert after["accumulation"] - before["accumulation"] == int(
                case["kind"] == "jie"
            ), case["id"]
            if case["kind"] == "jie":
                assert after["anchor"].name == case["term"]
                assert before["anchor"].name != case["term"]
            else:
                assert before["anchor"] == after["anchor"]


@pytest.mark.parametrize("source", list(PROVIDERS))
@pytest.mark.parametrize("profile", [None, "key_hour_winter_jiazi_v1"])
@pytest.mark.parametrize("solar", [False, True])
def test_all_six_solstices_switch_actual_instant_on_both_clock_adapters(
    source, profile, solar
):
    with solar_source(source):
        for case in SOLSTICES:
            at = datetime.fromisoformat(case["at_utc"])
            before = period_frame(
                seed_at(at - timedelta(minutes=2), solar=solar),
                "hour",
                hour_profile=profile,
            )
            after = period_frame(
                seed_at(at + timedelta(minutes=2), solar=solar),
                "hour",
                hour_profile=profile,
            )
            yin = case["term"] == "夏至"
            assert before["yin"] is not yin
            assert after["yin"] is yin
            assert after["anchor"].name == case["term"]
            assert after["anchor"].resolution_provider == PROVIDERS[source]
            if profile is None:
                assert after["accumulation"] == 1


@pytest.mark.parametrize("source", list(PROVIDERS))
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize(
    "mode,options,term",
    [
        ("month", {}, "立春"),
        ("month", {"month_profile": "key_month_tianzheng_jie_v1"}, "立春"),
        ("hour", {}, "夏至"),
        ("hour", {"hour_profile": "key_hour_winter_jiazi_v1"}, "夏至"),
    ],
)
def test_public_taiyi_and_sanshi_share_actual_source_and_boundary(
    source, solar, mode, options, term
):
    case = next(c for c in NAOJ if c["year"] == 2027 and c["term"] == term)
    with solar_source(source):
        for shift in [-120, 120]:
            t = datetime.fromisoformat(case["at_utc"]) + timedelta(seconds=shift)
            dedicated = calculate_taiyi_analysis(
                analysis_year=t.year,
                analysis_month=t.month,
                analysis_day=t.day,
                analysis_hour=t.hour,
                analysis_minute=t.minute,
                analysis_second=t.second,
                analysis_timezone="UTC",
                analysis_longitude=0.0,
                use_true_solar_time=solar,
                calculation_mode=mode,
                **options,
            )
            aggregate = calculate_sanshiunited_analysis(
                date=t.date().isoformat(),
                time=t.time().isoformat() + "+00:00",
                zone="UTC",
                gps_lon=0.0,
                use_true_solar_time=solar,
                taiyi_options={"calculation_mode": mode, **options},
            )
            assert "taiyi" in dedicated and "taiyi" in aggregate
            assert dedicated["taiyi"] == aggregate["taiyi"]
            assert (
                dedicated["taiyi"]["calendar_rules"]["anchor_provider"]
                == PROVIDERS[source]
            )
            assert PROVIDERS[source] in dedicated["snapshot_text"]


def test_audit_keeps_all_source_rows_and_open_acceptance():
    report = audit(CORPUS)
    assert len(report["timing_comparisons"]) == 252
    assert len(report["month_brackets"]) == 288
    assert len(report["solstice_brackets"]) == 48
    assert report["source_rows"] == 84 and report["unique_events"] == 72
    assert report["scoped_controls_passed"] is True
    assert report["whole_calendar_acceptance_passed"] is False
    assert report["classical_acceptance_passed"] is False
    assert report["new_complete_dated_classical_cases"] == 0

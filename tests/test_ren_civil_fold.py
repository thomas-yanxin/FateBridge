"""Independent fold probes, cache order, and all three Ren transports."""

import asyncio
import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.calendar import BaZiCalendar
from fatebridge.services.metaphysics import _build_analysis_seed, calculate_liureng_gods
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ren_fold_audit", ROOT / "scripts/audit_ren_civil_fold.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
HAVANA = REFERENCE["havana_cache_case"]


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_same_wall_fold_cache_keeps_both_independent_month_expectations(order):
    BaZiCalendar._get_four_pillars_cached.cache_clear()
    for index in order:
        probe = HAVANA["probes"][index]
        seed = _build_analysis_seed(**AUDIT.payload(HAVANA, probe))
        assert list(seed.pillars["year"]) == HAVANA["year_pillar"]
        assert list(seed.pillars["month"]) == probe["month_pillar"]
        assert list(seed.pillars["day"]) == HAVANA["day_pillar_civil"]
        assert list(seed.pillars["hour"]) == HAVANA["hour_pillar_civil"]
        assert seed.calendar_context["current_solar_term"]["name"] == probe["term"]
    # Repeating either call after the other must still hit its own correct key.
    for index in order:
        seed = _build_analysis_seed(**AUDIT.payload(HAVANA, HAVANA["probes"][index]))
        assert list(seed.pillars["month"]) == HAVANA["probes"][index]["month_pillar"]


def test_all_declared_fold_projections_keep_source_precision_and_denominators():
    report = AUDIT.audit()
    assert report["comparison_count"] == report["matched_count"] == 54
    assert report["unique_astronomical_minute_count"] == 5
    assert report["middle_term_zone_projection_count"] == 7
    assert report["source_minute_edge_uncertainty"] == ["F04"]
    assert report["selected_clock_checks_passed"]
    assert report["full_supported_calendar_domain_certified"] is False
    assert report["classical_acceptance_passed"] is False
    assert report["goal_complete"] is False


@pytest.mark.parametrize("probe", HAVANA["probes"])
def test_named_zone_and_verified_offset_match_the_same_fixed_offset_solar_label(probe):
    payload = {
        **AUDIT.payload(HAVANA, probe),
        "use_true_solar_time": True,
        "analysis_longitude": HAVANA["longitude"],
    }
    named = _build_analysis_seed(**payload)
    fixed = _build_analysis_seed(
        **{**payload, "analysis_timezone": probe["offset"], "analysis_utc_offset": None}
    )
    assert named.corrected_datetime.replace(
        tzinfo=None
    ) == fixed.corrected_datetime.replace(tzinfo=None)
    assert named.pillars == fixed.pillars
    # Different standard-meridian/DST decompositions may associate floating
    # additions differently; this is 6 ns, below the datetime microsecond.
    assert named.total_correction_minutes == pytest.approx(
        fixed.total_correction_minutes, rel=0, abs=1e-10
    )
    # Physical year/month boundaries use the input instant, not the solar label.
    assert list(named.pillars["month"]) == probe["month_pillar"]


def request(key, probe, solar):
    payload = {
        **AUDIT.payload(HAVANA, probe),
        "use_true_solar_time": solar,
        "analysis_longitude": HAVANA["longitude"],
    }
    if key == "jinkou":
        payload["di_fen"] = "子"
    if key == "liureng_runyear":
        payload.update(
            birth_year=1910,
            birth_month=1,
            birth_day=15,
            birth_hour=10,
            birth_timezone="Asia/Shanghai",
            birth_longitude=116.4,
            gender="女",
        )
    return payload


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("probe", HAVANA["probes"])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("project", [False, True])
def test_actual_offset_fold_and_pillars_agree_across_rest_native_mcp_cli(
    key, probe, solar, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = request(key, probe, solar)
    branch = "jinkou" if key == "jinkou" else "liureng"
    fields = ["four_pillars", branch + ".calendar_policy"]
    params = [("response_char_limit", "0"), ("as_of", "2026-10-12T02:00:00Z")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", field) for field in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for result in bodies:
        spec.output_model.model_validate(result)
        resolution = result[branch]["calendar_policy"]["civil_clock_resolution"]
        assert resolution["input_utc_offset"] == probe["offset"]
        assert resolution["resolved_utc_offset"] == probe["offset"]
        assert resolution["instant_utc"] == probe["instant_utc"]
        assert resolution["fold"] == probe["fold"]
        assert resolution["was_ambiguous"] is True
        month = result["four_pillars"]["month"]
        assert [month["stem"], month["branch"]] == probe["month_pillar"]
        if not project:
            assert probe["instant_utc"] in result["snapshot_text"]
            assert "民用钟消歧" in result["snapshot_text"]
            general = (
                result[branch]["overview"]["month_general"]
                if key == "jinkou"
                else result[branch]["month_general"]
            )
            assert general["branch"] == "卯"  # 立冬换月建；月将仍待小雪中气。
        if solar:
            corrected = datetime.fromisoformat(
                result[branch]["calendar_policy"]["corrected_clock"]
            )
            assert (
                corrected.tzinfo is None
            )  # A solar label is not a second civil instant.


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("kind", ["missing", "wrong_offset", "gap"])
def test_ambiguous_missing_invalid_offset_and_gap_reject_on_every_transport(
    key, kind, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = request(key, HAVANA["probes"][0], False)
    if kind == "missing":
        payload.pop("analysis_utc_offset")
    elif kind == "wrong_offset":
        payload["analysis_utc_offset"] = "-03:00"
    else:
        payload.update(analysis_month=3, analysis_day=14)  # Havana 00:30 was skipped.
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 400 and code != 0 and protocol.is_error
    for body in (http.json(), cli, protocol.structured_content):
        assert body["error_code"] == "validation_error"
        assert "liureng" not in body and "jinkou" not in body


def test_explicit_offset_on_a_unique_clock_is_not_claimed_to_be_a_repeated_hour():
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        analysis_utc_offset="+08:00",
        use_true_solar_time=False,
    )
    resolution = result["liureng"]["calendar_policy"]["civil_clock_resolution"]
    assert resolution["was_ambiguous"] is False and resolution["fold"] == 0
    assert "明确偏移已核对" in result["snapshot_text"]
    assert "重复钟时第" not in result["snapshot_text"]


def test_independent_clock_reference_rejects_changed_expected_month(tmp_path):
    dest = tmp_path / "reference"
    shutil.copytree(AUDIT.CORPUS, dest)
    path = dest / "reference.json"
    data = json.loads(path.read_text())
    data["havana_cache_case"]["probes"][1]["month_pillar"] = ["戊", "戌"]
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="reference changed"):
        AUDIT.reference(dest)

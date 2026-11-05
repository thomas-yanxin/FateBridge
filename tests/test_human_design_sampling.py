"""All15 original report contradictions plus complete finite native replay."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import runtime
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_sampling import verify_sampled_interval

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
PLAN = json.loads((ROOT / "tests/fixtures/human-design-sampling-plan.json").read_text())


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(SPEC, SPEC.request_model(**PLAN["birth_input"]))


def rehash(value):
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    return value


def set_path(value, path, replacement):
    target = value
    parts = path.split(".")
    for key in parts[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    key = int(parts[-1]) if isinstance(target, list) else parts[-1]
    assert target[key] != replacement
    target[key] = deepcopy(replacement)


@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_every_original_rehashed_contradiction_is_rejected(complete, case):
    changed = deepcopy(complete)
    set_path(changed, case["path"], case["replacement"])
    rehash(changed)
    assert verify_sampled_interval(changed)["errors"]
    checked = verify_human_design_reading(changed)
    assert checked["status"] == "rejected", checked


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "duplicate",
        "reverse",
        "extra",
        "native_nan",
        "native_bool",
        "native_flag",
        "native_longitude",
        "native_speed",
        "birth_label",
        "design_label",
        "future_flag",
        "clock_status",
        "clock_tt",
        "clock_ut1",
        "radius",
        "summary",
        "meaning",
        "continuous",
        "unassessed",
    ],
)
def test_native_replay_and_derived_reading_reject_tampering(complete, kind):
    p = deepcopy(complete)
    report = p["time_sensitivity"]
    w = report["evaluation_witnesses"]
    sample = w["samples"][0]
    if kind == "missing":
        w["samples"].pop(0)
    elif kind == "duplicate":
        w["samples"].insert(0, deepcopy(sample))
    elif kind == "reverse":
        w["samples"].reverse()
    elif kind == "extra":
        w["certified"] = True
    elif kind.startswith("native_"):
        row = sample["native_positions"]["personality"][0]
        if kind == "native_nan":
            row[0] = float("nan")
        elif kind == "native_bool":
            row[1] = True
        elif kind == "native_flag":
            row[2] = 2
        elif kind == "native_longitude":
            row[0] += 0.1
        else:
            # Selected nominal native scalars have a separate chart anchor.
            w["samples"][12]["native_positions"]["personality"][0][1] += 1
    elif kind == "birth_label":
        sample["birth_utc"] = "2000-01-01T00:00:00+00:00"
    elif kind == "design_label":
        sample["design_utc"] = "2000-01-01T00:00:00+00:00"
    elif kind == "future_flag":
        sample["time_scales"]["design"]["future_leap_seconds_assumed_unchanged"] = True
    elif kind == "clock_status":
        sample["time_scales"]["personality"]["utc_label_status"] = "certified"
    elif kind == "clock_tt":
        sample["time_scales"]["personality"]["jd_tt"] += 1 / 86400
    elif kind == "clock_ut1":
        w["samples"][12]["time_scales"]["personality"]["jd_ut1"] += 1 / 86400
    elif kind == "radius":
        p["calculation_policy"]["birth_time_uncertainty_minutes"] = 1
    elif kind == "summary":
        report["summary"]["evaluated_full_charts"] -= 1
    elif kind == "meaning":
        p["interpretation"]["birth_interval_meaning"] = "区间已获连续稳定性认证。"
    elif kind == "continuous":
        report["summary"]["continuous_interval_certified"] = True
    else:
        report["status"] = "not_assessed"
    if kind == "native_nan":
        # NaN cannot have a canonical JSON receipt, even before replay.
        with pytest.raises(ValueError):
            rehash(p)
        assert verify_sampled_interval(p)["errors"]
        checked = verify_human_design_reading(p)
    else:
        checked = verify_human_design_reading(rehash(p))
    assert checked["status"] == "rejected", checked


def test_complete_25_sample_replay_never_calls_native(complete, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("Replay must not call an ephemeris")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_interval_evaluation_count"] == 25
    assert check["checked_statement_count"] == 10
    assert (
        complete["time_sensitivity"]["summary"]["continuous_interval_certified"]
        is False
    )


@pytest.mark.parametrize(
    "clock",
    [
        (2016, 12, 31, 23, 59, 60),
        (1964, 4, 1, 0, 0, 0),
        (1972, 1, 1, 0, 0, 0),
        (2030, 1, 1, 0, 0, 0),
    ],
)
@pytest.mark.parametrize("mode", ["true", "mean"])
def test_special_clock_and_future_interval_replay(clock, mode, monkeypatch):
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    y, m, d, h, n, s = clock
    p = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=y,
            birth_month=m,
            birth_day=d,
            birth_hour=h,
            birth_minute=n,
            birth_second=s,
            birth_timezone="UTC",
            node_mode=mode,
            birth_time_uncertainty_minutes=1,
        ),
    )
    check = verify_human_design_reading(p)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_interval_evaluation_count"] >= 13
    assert len(p["interpretation"]["statements"]) == (11 if s == 60 else 10)


@pytest.mark.parametrize("mode", ["true", "mean"])
def test_empty_files_moshier_and_not_assessed_remain_explicit(
    tmp_path, monkeypatch, mode
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    for radius in (0, 1):
        p = execute_tool(
            SPEC,
            SPEC.request_model(
                **{
                    **PLAN["birth_input"],
                    "node_mode": mode,
                    "birth_time_uncertainty_minutes": radius,
                }
            ),
        )
        check = verify_human_design_reading(p)
        assert check["status"] == "verified_fixed_template_reading", check
        if radius:
            assert p["time_sensitivity"]["summary"]["physical_models"] == ["moshier"]
        else:
            assert p["time_sensitivity"]["evaluation_witnesses"] is None
            assert "未请求" in p["interpretation"]["birth_interval_meaning"]
            p["time_sensitivity"]["evaluation_witnesses"] = {}
            assert verify_sampled_interval(p)["errors"]

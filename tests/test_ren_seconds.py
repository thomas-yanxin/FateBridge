"""Frozen complete second cohort, actual three protocols, and faithful snapshots."""

import asyncio
import gzip
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest
import swisseph as swe

from scripts import audit_ren_seconds as audit
from scripts.ren_second_reference import ReferenceClock
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
IDS = [
    f"{term}-{side}"
    for term in [
        "1800-小寒",
        "1936-雨水",
        "1952-立秋",
        "1972-大雪",
        "2026-立春",
        "2200-冬至",
    ]
    for side in ["floor", "next_second"]
]


@pytest.fixture(scope="module")
def frozen():
    return audit.reference()


def test_whole_reference_is_frozen_before_candidate_and_not_a_physical_holdout(frozen):
    rows = frozen["data"]["rows"]
    p = frozen["protocol"]
    assert len(rows) == 19248 and p["root_count"] == 9624 and p["guard_roots"] == 48
    assert {r["year"] for r in rows} == set(range(1800, 2201))
    assert set(p["profiles"]) == {"auto_empty", "auto_swiss", "native_swiss_control"}
    assert frozen["data"]["production_imports"] is False
    assert frozen["data"]["inside_root_bracket_ids"] == []
    assert all(r["expected"][k] is not None for r in rows for k in r["expected"])
    assert any(datetime.fromisoformat(r["civil_utc"]).second != 0 for r in rows)
    assert frozen["data"]["new_independent_physical_events"] == 0
    assert p["criteria"]["tt_seconds"] == 1.0
    assert p["criteria"]["input_clock_seconds"] == 0.0002
    for name, key in [
        ("scripts/ren_second_reference.py", "reference_helper_sha256"),
        ("scripts/collect_ren_second_probes.py", "collector_sha256"),
    ]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == p[key]


@pytest.mark.parametrize("fault", ["reference_bytes", "manifest_bytes", "extra_file"])
def test_corrupt_reference_is_rejected_without_rescoring(tmp_path, fault):
    folder = tmp_path / "corpus"
    shutil.copytree(audit.CORPUS, folder)
    if fault == "reference_bytes":
        with (folder / "probes.json.gz").open("ab") as f:
            f.write(b"wrong")
    elif fault == "manifest_bytes":
        (folder / "freeze.json").write_text("{}")
    else:
        (folder / "hidden.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen"):
        audit.reference(folder)


def test_reference_clock_matches_all233_original_sofa_cases_without_production(frozen):
    cases = frozen["data"]["reference_clock_sofa_checks"]
    assert len(cases) == 233
    assert max(abs(r["delta_seconds"]) for r in cases) <= 0.0002
    sofa = json.loads((ROOT / "tests/fixtures/historical-utc-sofa.json").read_text())
    clock = ReferenceClock(sofa["historical_coefficients"], swe)
    for case in sofa["cases"]:
        got, _ = clock.forward(datetime.fromisoformat(case["utc"]))
        assert abs(got - sum(case["tt_jd_parts"])) * 86400 <= 0.0002


@pytest.fixture
def default_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.setenv("FATEBRIDGE_REN_SECOND_AUDIT_PROFILE", "auto_empty")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
def test_whole_seconds_reach_three_protocols_and_the_snapshot(
    identifier, key, frozen, default_empty, rest, tmp_path, capsys
):
    row = next(r for r in frozen["data"]["rows"] if r["id"] == identifier)
    moment = datetime.fromisoformat(row["civil_utc"])
    expected = row["expected"]
    payload = dict(
        analysis_year=moment.year,
        analysis_month=moment.month,
        analysis_day=moment.day,
        analysis_hour=moment.hour,
        analysis_minute=moment.minute,
        analysis_second=moment.second,
        analysis_timezone="UTC",
        use_true_solar_time=False,
        is_diurnal=True,
    )
    if key == "jinkou":
        payload["di_fen"] = "酉"
    fields = [
        "four_pillars",
        "liureng.month_general",
        "liureng.calendar_policy",
        "snapshot_text",
    ]
    if key == "jinkou":
        fields += ["jinkou.rows", "jinkou.overview"]
    spec = SPECS[key]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=True,
        response_char_limit=0,
    )
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "true"),
            ("response_char_limit", "0"),
            ("as_of", AS_OF),
        ],
    )
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error, mcp.structured_content
    assert code == 0, cli
    outputs = [http.json(), mcp.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        assert {k: v["stem"] + v["branch"] for k, v in out["four_pillars"].items()} == {
            k: expected[k] for k in ["year", "month", "day", "hour"]
        }
        board = out["liureng"]
        deps = board["calendar_policy"]["solar_term_dependencies"]
        assert (
            deps[0]["name"] == expected["current_term"]
            and deps[1]["name"] == expected["next_term"]
        )
        assert {d["provider"] for d in deps} == {"jpl_de440"}
        assert board["month_general"]["branch"] == expected["month_general"]
        snap = out["snapshot_text"]
        assert (
            f"{'月将本位' if key == 'jinkou' else '月将'}：{expected['month_general']}("
            in snap
        )
        if key == "jinkou":
            j = out["jinkou"]
            assert j["overview"]["month_general"]["branch"] == expected["month_general"]
            assert j["overview"]["yuejiang"]["branch"] == expected["positions"][2]
            assert f"将神落地分：{expected['positions'][2]}(" in snap
            assert [r["content"] for r in j["rows"]] == expected["positions"]
            assert [r["seasonal_power"] for r in j["rows"]] == expected[
                "seasonal_powers"
            ]
            assert j["overview"]["use_position"] == expected["polarity_use"]
            for pos, r, power in zip(
                expected["positions"], j["rows"], expected["seasonal_powers"]
            ):
                lines = [
                    line
                    for line in snap.splitlines()
                    if line.startswith(f"{r['label']}：{pos}；")
                ]
                assert len(lines) == 1
                assert f"四季旺衰：{power}" in lines[0]
            assert f"用爻：{expected['polarity_use']}" in snap


def test_audit_carries_the_actual_second_instead_of_silently_using_zero(
    frozen, default_empty, monkeypatch
):
    import fatebridge.services.metaphysics as service

    original = service._build_analysis_seed
    seen = []

    def observe(**kwargs):
        seen.append(kwargs["analysis_second"])
        return original(**kwargs)

    monkeypatch.setattr(service, "_build_analysis_seed", observe)
    p = next(r for r in frozen["data"]["rows"] if r["id"] == "1800-小寒-floor")
    got = audit.evaluate_probe(p, frozen["protocol"])
    assert seen == [datetime.fromisoformat(p["civil_utc"]).second] and seen[0] != 0
    assert all(got["matches"].values())

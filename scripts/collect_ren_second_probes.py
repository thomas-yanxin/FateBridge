"""Freeze every whole-second pair around existing independent solar TT roots."""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import swisseph as swe

from scripts.ren_second_reference import NAMES, ReferenceClock, source_expectation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests/data/ren/second_boundary_inputs"
PINS = {
    "tests/data/solar/liuyao_de440_tt1800_2200.json": "7b64d68a9f91d9e0342ecadf39a423c736224b492128556187707e3ca3fb4e65",
    "tests/fixtures/ren_calendar_guard_v1/freeze.json": "7f93b89d2761b854672530e7d60bf99e201cfa962c80a63b3947d776c48f47d9",
    "tests/fixtures/ren_boundary_decisions_v1/protocol.json": "c980b9875b9201a6a6264173391aa13e7c16732eb9fc5460770c41653174f316",
    "tests/fixtures/ren_calendar_v1/reference.json": "7becec29a4e3416f73743ba49b55c2468922cfc9cfb14ddf82d52f9079e02600",
    "tests/fixtures/ren_classical_v1/rules.json": "c7640f353db970e83333a2171c01b1f5877dbb55f72f7c70a1d7741ecb391bb9",
    "tests/fixtures/historical-utc-sofa.json": "65a450c5777cfa8920694fffc382a14c691dd3e8092822d17e89a76f55f35642",
    "tests/fixtures/historical-utc-iers.txt": "54e702abdc388ae3bf8cfc5f126900a5277829ad90e80f6773df6e714a133642",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    assert not OUT.exists(), "Never overwrite a frozen reference"
    assert all(sha(ROOT / n) == h for n, h in PINS.items())
    guard = ROOT / "tests/fixtures/ren_calendar_guard_v1"
    for n, h in json.loads((guard / "freeze.json").read_text())["files"].items():
        assert sha(guard / n) == h
    full = json.loads(
        (ROOT / "tests/data/solar/liuyao_de440_tt1800_2200.json").read_text()
    )["rows"]
    extra = [
        r
        for r in json.loads((guard / "reference.json").read_text())["rows"]
        if r["year"] in (1799, 2201)
    ]
    roots = sorted(full + extra, key=lambda r: r["jd_tt"])
    assert len(full) == 9624 and len(roots) == 9672
    assert len({(r["year"], r["index"]) for r in roots}) == 9672
    old = json.loads(
        (ROOT / "tests/fixtures/ren_boundary_decisions_v1/protocol.json").read_text()
    )
    protocol = dict(
        id="ren_seconds_v1",
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        disclosure="Existing TT roots, old minute outcomes and endpoint development cases were already exposed. All19248 second labels and table-derived decisions are frozen before this audit; no blind/physical-observation credit.",
        years=[1800, 2200],
        root_count=9624,
        guard_roots=48,
        probe_count=19248,
        profiles={
            "auto_empty": dict(
                mode="auto",
                directory="empty",
                provider="jpl_de440",
                model="fatebridge_de440_solar_v1",
            ),
            "auto_swiss": dict(
                mode="auto",
                directory="swiss",
                provider="jpl_de440",
                model="fatebridge_de440_solar_v1",
            ),
            "native_swiss_control": dict(
                mode="native", directory="swiss", provider="swisseph", model="swieph"
            ),
        },
        di_fen="酉",
        is_diurnal=True,
        true_solar=False,
        timezone="UTC",
        day_boundary="23:00 declared software convention",
        criteria=dict(
            tt_seconds=1.0,
            input_clock_seconds=0.0002,
            decisions="exact frozen values; every row, error, unknown and uncertainty retained; no fitted clock/coordinate offsets or result-selected exclusions",
        ),
        reference_pins=PINS,
        reference_maps=old["reference_maps"],
        collector_sha256=sha(Path(__file__)),
        reference_helper_sha256=sha(ROOT / "scripts/ren_second_reference.py"),
        clock_method="No FateBridge imports. Direct Swiss historicalUT1 before1960 (shared declared clock model, not observedUTC); independently transcribed SOFA/IERS affineUTC1960..1971 and IERS modern offsets, future last37s explicit assumption. RawTT roots reused, no production solar roots or coefficients.",
        clock_swiss_version=swe.version,
        clock_files={n: sha(ROOT / "ephe" / n) for n in ["sepl_18.se1", "semo_18.se1"]},
        source_urls=[
            "https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history",
            "https://www.iausofa.org/2023-10-11c",
            "https://www.astro.com/swisseph/swephprg.htm",
        ],
        uncertainty_policy="Record whether input lies inside the frozen TT root bracket. Midpoint-based comparisons are still reported; uncertainty is never a passing physical-accuracy claim.",
        full_goal_complete=False,
    )
    OUT.mkdir()
    (OUT / "protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n"
    )
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    swe.set_ephe_path(str(ROOT / "ephe"))
    swe.set_tid_acc(swe.TIDAL_AUTOMATIC)
    sofa = json.loads((ROOT / "tests/fixtures/historical-utc-sofa.json").read_text())
    clock = ReferenceClock(sofa["historical_coefficients"], swe)
    calendar = json.loads(
        (ROOT / "tests/fixtures/ren_calendar_v1/reference.json").read_text()
    )
    rules = json.loads(
        (ROOT / "tests/fixtures/ren_classical_v1/rules.json").read_text()
    )
    times = [r["jd_tt"] for r in roots]
    rows = []
    sofa_checks = []
    for case in sofa["cases"]:
        moment = datetime.fromisoformat(case["utc"])
        expected = sum(case["tt_jd_parts"])
        tt, _ = clock.forward(moment)
        sofa_checks.append(
            dict(
                utc=case["utc"],
                delta_seconds=(tt - expected) * 86400,
                monthly=moment.day == 15,
            )
        )
    for root in full:
        civil = clock.inverse(root["jd_tt"])
        floor = civil.replace(microsecond=0)
        for side, moment in [
            ("floor", floor),
            ("next_second", floor + timedelta(seconds=1)),
        ]:
            tt, method = clock.forward(moment)
            rows.append(
                dict(
                    id=f"{root['year']}-{NAMES[root['index']]}-{side}",
                    year=root["year"],
                    index=root["index"],
                    side=side,
                    civil_utc=moment.isoformat(),
                    reference_jd_tt=root["jd_tt"],
                    reference_civil=civil.isoformat(),
                    input_jd_tt=tt,
                    reference_clock_method=method,
                    tt_margin_seconds=(tt - root["jd_tt"]) * 86400,
                    inside_root_bracket=abs(tt - root["jd_tt"]) * 86400
                    <= root["bracket_seconds"] / 2,
                    expected=source_expectation(
                        roots, times, moment, tt, protocol, calendar, rules
                    ),
                )
            )
    assert len(rows) == 19248 and len({r["id"] for r in rows}) == 19248
    assert all(sum(r["year"] == y for r in rows) == 48 for y in range(1800, 2201))
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    result = dict(
        protocol_sha256=sha(OUT / "protocol.json"),
        production_imports=False,
        root_count=9624,
        rows=rows,
        reference_clock_sofa_checks=sofa_checks,
        inside_root_bracket_ids=[r["id"] for r in rows if r["inside_root_bracket"]],
        minimum_abs_tt_margin_seconds=min(abs(r["tt_margin_seconds"]) for r in rows),
        new_independent_physical_events=0,
    )
    raw = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    (OUT / "probes.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (OUT / "freeze.json").write_text(
        json.dumps(
            dict(files={n: sha(OUT / n) for n in ["protocol.json", "probes.json.gz"]}),
            indent=2,
        )
        + "\n"
    )
    print(
        dict(
            probes=len(rows),
            freeze_sha256=sha(OUT / "freeze.json"),
            uncertain=result["inside_root_bracket_ids"],
            min_margin_seconds=result["minimum_abs_tt_margin_seconds"],
            sofa_monthly_max=max(
                abs(r["delta_seconds"]) for r in sofa_checks if r["monthly"]
            ),
        )
    )


if __name__ == "__main__":
    main()

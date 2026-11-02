"""Compare sixyao's consumed seasonal clock with already-frozen references.

The minute publisher and TT implementation comparisons answer different
questions. Neither supplies a physical error bound or real-world efficacy.
"""

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.local_techniques.sixyao import build_sixyao_result

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tests/fixtures/liuyao_solar_v16"
TT_BASE = ROOT / "tests/fixtures/bazi_all_terms_v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict[str, Any]:
    frozen = json.loads((BASE / "freeze.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        if sha(BASE / name) != digest:
            raise ValueError(f"Changed frozen publisher source: {name}")
    reference = json.loads((BASE / "reference.json").read_text())
    errata = json.loads((BASE / "input-errata.json").read_text())
    row = reference["records"][errata["record_index"]]
    if row[errata["field"]] != errata["old_value"]:
        raise ValueError("Unexpected source annotation under errata")
    row[errata["field"]] = errata["new_value"]
    tt_sha = sha(TT_BASE / "reference.json")
    if tt_sha != (TT_BASE / "reference.sha256").read_text().strip():
        raise ValueError("Changed independent TT reference")
    tt_reference = {
        r["name"]: r
        for r in json.loads((TT_BASE / "reference.json").read_text())["rows"]
        if r["year"] == 2026
    }
    terms = {t.name: t for t in get_solar_terms_for_year(2026)}
    if len(terms) != 24 or len(tt_reference) != 24:
        raise ValueError("Expected all 24 terms without exclusion")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for record in reference["records"]:
        term = terms[record["name"]]
        published = datetime.fromisoformat(record["published_at"])
        clock = ephemeris_time(term.moment)
        if clock.jd_tt is None:
            raise ValueError("TT unavailable")
        delta = (clock.jd_tt - tt_reference[term.name]["jd_tt"]) * 86400
        minute_delta = (term.moment - published).total_seconds()
        rows.append(
            {
                "name": term.name,
                "actual": term.as_dict(),
                "published_at": record["published_at"],
                "actual_minus_published_seconds": minute_delta,
                "actual_minus_reference_tt_seconds": delta,
                "tt_tolerance_seconds": 1,
                "civil_time_policy": clock.method,
                "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
            }
        )
        for layer, difference, tolerance in [
            ("printed_minute", minute_delta, 60),
            ("existing_independent_TT", delta, 1),
        ]:
            if abs(difference) > tolerance:
                failures.append(
                    dict(
                        name=term.name,
                        layer=layer,
                        difference_seconds=difference,
                        tolerance_seconds=tolerance,
                    )
                )
        for zone in ["Asia/Shanghai", "Asia/Tokyo", "America/New_York"]:
            for sign, key in [(-1, "before_month_branch"), (1, "after_month_branch")]:
                moment = (published + timedelta(seconds=sign * 61)).astimezone(
                    ZoneInfo(zone)
                )
                result = build_sixyao_result(
                    date=str(moment.date()),
                    time=moment.time().isoformat(),
                    zone=zone,
                    gua_code="111111",
                )
                expected = record[key]
                actual = result["nongli"]["monthGanZi"][1]
                evidence = result["liuyao_evidence"]["calendar_conventions"][
                    "month_branch"
                ]
                checks.append(
                    dict(
                        name=term.name,
                        zone=zone,
                        input=moment.isoformat(),
                        expected=expected,
                        actual=actual,
                        evidence=evidence,
                    )
                )
                if actual != expected or evidence != expected:
                    failures.append(
                        dict(
                            name=term.name,
                            layer="public_month_bracket",
                            input=moment.isoformat(),
                            zone=zone,
                            expected=expected,
                            actual=actual,
                            evidence=evidence,
                        )
                    )
    ephe = configured_ephemeris_path()
    return {
        "id": "liuyao_solar_boundaries_v16",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "24 published 2026 minute events; reuse of 24 existing DE440 TT events; 144 engineering month probes across three timezones. Not additional independent samples, blind holdout, absolute physical accuracy, all-year UTC certification, classical divination endorsement or predictive validity.",
        "publisher_rounding_mode_verified": False,
        "bracket_policy": "published minute +/-61 seconds; engineering probes outside the conservative 60-second comparison band, not a publisher uncertainty interval",
        "existing_moshier_all_year_failures_superseded": False,
        "source_sha256": {
            name: sha(ROOT / name)
            for name in [
                "src/fatebridge/core/almanac.py",
                "src/fatebridge/core/astro/time_scales.py",
                "src/fatebridge/core/local_techniques/sixyao.py",
                "uv.lock",
            ]
        },
        "reference_sha256": {
            "publisher": sha(BASE / "reference.json"),
            "publisher_raw": sha(BASE / "naoj-2026.html"),
            "name_errata": sha(BASE / "input-errata.json"),
            "existing_tt": tt_sha,
        },
        "selected_ephemeris_path": ephe,
        "selected_directory_se1_sha256": (
            {p.name: sha(p) for p in sorted(Path(ephe).glob("*.se1"))} if ephe else {}
        ),
        "term_count": len(rows),
        "public_probe_count": len(checks),
        "max_absolute_printed_minute_difference_seconds": max(
            abs(r["actual_minus_published_seconds"]) for r in rows
        ),
        "max_absolute_tt_difference_seconds": max(
            abs(r["actual_minus_reference_tt_seconds"]) for r in rows
        ),
        "failure_count": len(failures),
        "failures": failures,
        "rows": rows,
        "public_probes": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an earlier comparison")
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "term_count",
                    "public_probe_count",
                    "failure_count",
                    "max_absolute_tt_difference_seconds",
                ]
            }
        )
    )
    raise SystemExit(1 if result["failure_count"] else 0)


if __name__ == "__main__":
    main()

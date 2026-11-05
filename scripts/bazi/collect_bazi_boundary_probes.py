"""Freeze minute probes around every existing independent TT reference root."""

from __future__ import annotations

import bisect
import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_boundary_decisions_v1"
JIE_BRANCHES = {
    "立春": "寅",
    "惊蛰": "卯",
    "清明": "辰",
    "立夏": "巳",
    "芒种": "午",
    "小暑": "未",
    "立秋": "申",
    "白露": "酉",
    "寒露": "戌",
    "立冬": "亥",
    "大雪": "子",
    "小寒": "丑",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_state(roots: list[dict], jd_tt: float) -> dict:
    """Classify only from frozen reference events, not runtime solar roots."""
    index = bisect.bisect_right([r["jd_tt"] for r in roots], jd_tt) - 1
    jie = [r for r in roots if r["name"] in JIE_BRANCHES and r["jd_tt"] <= jd_tt]
    springs = [r for r in roots if r["name"] == "立春" and r["jd_tt"] <= jd_tt]
    return {
        "last_term": roots[index]["name"] if index >= 0 else None,
        "next_term": roots[index + 1]["name"] if index + 1 < len(roots) else None,
        "bazi_year": springs[-1]["year"] if springs else None,
        "month_branch": JIE_BRANCHES[jie[-1]["name"]] if jie else None,
    }


def main() -> None:
    target = FIXTURE / "probes.json"
    if target.exists():
        raise FileExistsError("Refusing to replace frozen probes")
    protocol_path = FIXTURE / "protocol.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen protocol changed")
    protocol = json.loads(protocol_path.read_text())
    reference = ROOT / protocol["reference_path"]
    if digest(reference) != protocol["reference_sha256"]:
        raise ValueError("Independent reference changed")
    for name, expected in protocol["source_fingerprints"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Source changed before probe collection: " + name)
    os.environ["SE_EPHE_PATH"] = str(ROOT / "ephe")
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "native"
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    runtime.configure_ephemeris_path(str(ROOT / "ephe"))
    roots = json.loads(reference.read_text())["rows"]
    rows = []
    for root in roots:
        civil = datetime_from_tt(root["jd_tt"])
        floor = civil.replace(second=0, microsecond=0)
        for side, moment in [
            ("floor", floor),
            ("next_minute", floor + timedelta(minutes=1)),
        ]:
            epoch = ephemeris_time(moment)
            rows.append(
                {
                    "id": f"{root['year']}-{root['name']}-{side}",
                    "year": root["year"],
                    "name": root["name"],
                    "side": side,
                    "civil_utc": moment.isoformat(),
                    "reference_root_tt": root["jd_tt"],
                    "reference_civil_under_frozen_policy": civil.isoformat(),
                    "input_jd_tt_under_frozen_policy": epoch.jd_tt,
                    "input_time_method": epoch.method,
                    "future_leap_seconds_assumed_unchanged": epoch.future_leap_seconds_assumed_unchanged,
                    "reference_state_under_frozen_policy": reference_state(
                        roots, epoch.jd_tt
                    ),
                }
            )
    if len(roots) != 4872 or len(rows) != 9744:
        raise ValueError("Full reference cohort not preserved")
    result = {
        "protocol_sha256": digest(protocol_path),
        "reference_sha256": digest(reference),
        "collector_sha256": digest(Path(__file__)),
        "root_count": len(roots),
        "probe_count": len(rows),
        "rows": rows,
        "native_clock_files": {
            n: digest(ROOT / "ephe" / n) for n in ["sepl_18.se1", "semo_18.se1"]
        },
        "scope": "All existing TT roots, fixed civil-minute labels. Native Swiss civil conversion is shared policy, not an independent physical UTC reference. No solar roots or candidate decisions were calculated here.",
    }
    with target.open("x") as handle:
        handle.write(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    target.with_suffix(".sha256").write_text(digest(target) + "\n")
    print({"roots": len(roots), "probes": len(rows), "sha256": digest(target)})


if __name__ == "__main__":
    main()

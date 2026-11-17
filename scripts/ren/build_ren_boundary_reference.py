"""Reproduce Ren boundary inputs using independent TT roots and source tables.

Run in a separate reference environment with no FateBridge package installed.
Inputs retain their original text; frozen source snapshots are metadata and are
never executed by the reader. Existing original source promises are unchanged.
"""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import inspect
import sys
from datetime import datetime, timedelta
from importlib import metadata
from pathlib import Path
from typing import Literal

import swisseph as swe

from scripts.astronomy.solar_term_reference import (
    REFERENCE_SHA256 as SOLAR_REFERENCE_SHA256,
)
from scripts.astronomy.solar_term_reference import load_solar_term_reference
from scripts.ren.ren_boundary_reference import (
    BoundarySourcePacket,
    ExpectedDecision,
    MinuteData,
    SecondData,
    SecondProbe,
    SourceBoundaryProtocol,
    SourceCalendar,
    SourceInput,
    SourceProfile,
    SourceRules,
    SourceSecondProtocol,
    SourceSOFA,
)
from scripts.ren.ren_second_reference import NAMES, ReferenceClock, source_expectation

INPUT_SHA256 = {
    "calendar": "7becec29a4e3416f73743ba49b55c2468922cfc9cfb14ddf82d52f9079e02600",
    "rules": "c7640f353db970e83333a2171c01b1f5877dbb55f72f7c70a1d7741ecb391bb9",
    "sofa": "65a450c5777cfa8920694fffc382a14c691dd3e8092822d17e89a76f55f35642",
    "iers": "54e702abdc388ae3bf8cfc5f126900a5277829ad90e80f6773df6e714a133642",
    "boundary_protocol": "c980b9875b9201a6a6264173391aa13e7c16732eb9fc5460770c41653174f316",
    "minute_data": "4912b449f484413b7dea61af35a4f93446d0710189f018f1a6c544842f0751fa",
    "minute_protocol": "ff0a5ef11175c4e19b6253412d3d000c8a6770e973ff8125de07f131661301f0",
    "second_protocol": "9a36958d42234befcd061f36fae30d961d2477602b3630ba0e3d9276f3106d8c",
    "guard_freeze": "7f93b89d2761b854672530e7d60bf99e201cfa962c80a63b3947d776c48f47d9",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Frozen references are never overwritten; choose a new output")
    if metadata.version("pyswisseph") != "2.10.3.2":
        raise ValueError("Use the declared independent Swiss reference version")
    inputs: dict[str, SourceInput] = {}
    for name, expected_digest in INPUT_SHA256.items():
        raw = (args.input_directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_digest:
            raise ValueError(f"Independent source bytes changed: {name}")
        inputs[name] = SourceInput(sha256=expected_digest, text=raw.decode("utf-8"))
    solar = load_solar_term_reference(args.input_directory / "solar_reference")
    calendar = SourceCalendar.model_validate_json(inputs["calendar"].text, strict=True)
    rules = SourceRules.model_validate_json(inputs["rules"].text, strict=True)
    sofa = SourceSOFA.model_validate_json(inputs["sofa"].text, strict=True)
    minute_data = MinuteData.model_validate_json(
        inputs["minute_data"].text, strict=True
    )
    protocol = SourceSecondProtocol.model_validate_json(
        inputs["second_protocol"].text, strict=True
    )
    boundary = SourceBoundaryProtocol.model_validate_json(
        inputs["boundary_protocol"].text, strict=True
    )
    general = calendar.general_starts["冬至"]
    general_by_term = {}
    for name in NAMES:
        general = calendar.general_starts.get(name, general)
        general_by_term[name] = general
    if protocol.reference_maps[
        "general_by_last_term"
    ] != general_by_term or protocol.reference_maps["gui_sequence"] != tuple(
        rules.inherent
    ):
        raise ValueError("Reference maps disagree with their independent source tables")
    # The current auto policy uses DE440. The old auto/analytic promise remains
    # verbatim in source_inputs; it is not relabeled as a passed old comparison.
    arms = {
        key: value
        for key, value in boundary.arms.items()
        if key != "empty_auto_analytic"
    }
    arms["empty_auto_de440"] = SourceProfile(
        mode="auto",
        directory="explicit_empty",
        provider="jpl_de440",
        model="fatebridge_de440_solar_v1",
    )
    boundary = boundary.model_copy(update={"arms": arms})
    for name, expected_digest in protocol.clock_files.items():
        if (
            hashlib.sha256((args.input_directory / name).read_bytes()).hexdigest()
            != expected_digest
        ):
            raise ValueError(f"Independent historical clock source changed: {name}")
    swe.set_ephe_path(str(args.input_directory))
    swe.set_tid_acc(swe.TIDAL_AUTOMATIC)
    clock = ReferenceClock([dict(row) for row in sofa.historical_coefficients], swe)
    roots = [r.model_dump() for r in solar.rows if 1799 <= r.year <= 2201]
    times = [r.jd_tt for r in solar.rows if 1799 <= r.year <= 2201]
    checks: list[dict[str, float | str | bool]] = []
    for case in sofa.cases:
        moment = datetime.fromisoformat(case.utc)
        tt, _ = clock.forward(moment)
        delta = (tt - sum(case.tt_jd_parts)) * 86400
        if abs(delta) > 0.0002:
            raise ValueError(
                f"Independent clock left its original SOFA criterion: {case.utc}"
            )
        checks.append(
            {"utc": case.utc, "delta_seconds": delta, "monthly": moment.day == 15}
        )
    rows: list[SecondProbe] = []
    for root in solar.rows:
        if not 1800 <= root.year <= 2200:
            continue
        civil = clock.inverse(root.jd_tt)
        floor = civil.replace(microsecond=0)
        sides: tuple[tuple[Literal["floor", "next_second"], datetime], ...] = (
            ("floor", floor),
            ("next_second", floor + timedelta(seconds=1)),
        )
        for side, moment in sides:
            tt, method = clock.forward(moment)
            expected = ExpectedDecision.model_validate(
                source_expectation(
                    roots,
                    times,
                    moment,
                    tt,
                    protocol.model_dump(),
                    calendar.model_dump(),
                    rules.model_dump(),
                )
            )
            rows.append(
                SecondProbe(
                    id=f"{root.year}-{root.name}-{side}",
                    year=root.year,
                    index=root.index,
                    side=side,
                    civil_utc=moment.isoformat(),
                    reference_jd_tt=root.jd_tt,
                    reference_civil=civil.isoformat(),
                    input_jd_tt=tt,
                    reference_clock_method=method,
                    tt_margin_seconds=(tt - root.jd_tt) * 86400,
                    inside_root_bracket=root.bracket_tt[0] <= tt <= root.bracket_tt[1],
                    expected=expected,
                )
            )
    # Preserve the original minute labels and shared-clock inputs. Independently
    # reclassify every conditional state; do not generate a new candidate clock.
    minute_roots = [r for r in solar.rows if 1899 <= r.year <= 2101]
    minute_times = [r.jd_tt for r in minute_roots]
    for row in minute_data.rows:
        index = (
            bisect.bisect_right(minute_times, row.input_jd_tt_under_frozen_policy) - 1
        )
        before = minute_roots[: index + 1] if index >= 0 else []
        spring = next((r for r in reversed(before) if r.index == 2), None)
        jie = next(
            (r for r in reversed(before) if r.name in calendar.month_starts), None
        )
        minute_state = {
            "last_term": minute_roots[index].name if index >= 0 else None,
            "next_term": (
                minute_roots[index + 1].name if index + 1 < len(minute_roots) else None
            ),
            "bazi_year": spring.year if spring else None,
            "month_branch": calendar.month_starts[jie.name] if jie else None,
        }
        if minute_state != row.reference_state_under_frozen_policy.model_dump():
            raise ValueError(
                f"Independent minute state differs from original: {row.id}"
            )
        root = minute_roots[(row.year - 1899) * 24 + NAMES.index(row.name)]
        if root.jd_tt != row.reference_root_tt:
            raise ValueError(f"Independent minute root differs from original: {row.id}")
    if len(rows) != 19248 or len(minute_data.rows) != 9744 or len(checks) != 233:
        raise ValueError(
            "All original second/minute inputs and SOFA controls are required"
        )
    if any(
        name == "fatebridge" or name.startswith("fatebridge.") for name in sys.modules
    ):
        raise ValueError("Independent reference collection imported the candidate")
    producer = Path(__file__).read_text(encoding="utf-8")
    helper = Path(inspect.getfile(ReferenceClock)).read_text(encoding="utf-8")
    observations: list[dict[str, str | bool]] = []
    for name, original in [
        (
            "guard_freeze",
            "9ccd4ba277cfa91c184fe59bcf33f5d0f392c509f2197b9167460653353e2f76",
        ),
        (
            "boundary_protocol",
            "aac95c48ce34c11c5001630e155ebfd1bc3bf6622f1950349cbef67bde88a8ea",
        ),
        ("minute_protocol", minute_data.protocol_sha256),
    ]:
        observations.append(
            {
                "source": name,
                "original_expected_sha256": original,
                "observed_sha256": inputs[name].sha256,
                "matches_original": original == inputs[name].sha256,
            }
        )
    packet = BoundarySourcePacket(
        schema_id="ren_boundary_sources_v1",
        solar_reference_sha256=SOLAR_REFERENCE_SHA256,
        producer_source=producer,
        producer_sha256=hashlib.sha256(producer.encode()).hexdigest(),
        helper_source=helper,
        helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),
        software_versions={
            "pyswisseph": metadata.version("pyswisseph"),
            "swiss_library": swe.version,
            "pydantic": metadata.version("pydantic"),
        },
        source_inputs=inputs,
        second_protocol=protocol,
        boundary_protocol=boundary,
        seconds=SecondData(
            production_imports=False,
            root_count=9624,
            rows=tuple(rows),
            reference_clock_sofa_checks=tuple(checks),
            inside_root_bracket_ids=tuple(r.id for r in rows if r.inside_root_bracket),
            minimum_abs_tt_margin_seconds=min(abs(r.tt_margin_seconds) for r in rows),
            new_independent_physical_events=0,
        ),
        legacy_identity_observations=tuple(observations),
        scope="Full19248 independently reproduced second inputs and table decisions,9744 unchanged conditional minute inputs,233 original SOFA controls. Same exposed events, not a blind physical holdout. Pre1960 Swiss model is shared; future UTC uses last offset. Original missing/different source promises remain unverified. Every uncertainty retained; no physical boundary, whole-library, predictive, model or SOTA certification.",
    )
    packed = gzip.compress(packet.model_dump_json().encode(), mtime=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(packed)
    print(
        {
            "seconds": len(rows),
            "minutes": len(minute_data.rows),
            "sha256": hashlib.sha256(packed).hexdigest(),
            "bytes": len(packed),
            "inside_root_bracket_ids": packet.seconds.inside_root_bracket_ids,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

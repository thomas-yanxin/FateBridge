"""Compare both fixed routes, retaining every unavailable or failed row."""

import argparse
import hashlib
import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


p = argparse.ArgumentParser()
p.add_argument("--ephe-dir", dest="dataset", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
a = p.parse_args()
FIX = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/western-ephemeris-coverage-v1"
)
seal = json.loads((FIX / "seal.json").read_text())
PROTOCOL_SHA256 = "74371d1cbcdaa6e400ac7ddbd2d51685e219ac9aa63cc02a3fcba6c478c63f36"
REFERENCE_SHA256 = "bc87a9633d327927f5bbefa0f395db740bd171fc884aa26d3f8cc90c24d95c91"
RAW_ARCHIVE_SHA256 = "a23d940040d8d9b9d71c53d42208e3d99478d787e51824d10aa2139d872cb95b"
require(seal["protocol_sha256"] == PROTOCOL_SHA256, "Protocol seal changed")
require(seal["reference_sha256"] == REFERENCE_SHA256, "Reference seal changed")
require(seal["raw_archive_sha256"] == RAW_ARCHIVE_SHA256, "Raw archive seal changed")
require(
    hashlib.sha256((FIX / "reference-raw.zip").read_bytes()).hexdigest()
    == RAW_ARCHIVE_SHA256,
    "Raw reference archive changed",
)
require(
    hashlib.sha256((FIX / "reference.json").read_bytes()).hexdigest()
    == REFERENCE_SHA256,
    "Reference changed",
)
require(
    hashlib.sha256((FIX / "protocol.json").read_bytes()).hexdigest() == PROTOCOL_SHA256,
    "Protocol changed",
)
os.environ["SE_EPHE_PATH"] = str(a.dataset)
sys.path.insert(0, str(a.source_root / "src"))
from fatebridge.core.astro import runtime
from fatebridge.core.astro.lunar_source_window import coherent_lunar_native_state
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

plan = json.loads((FIX / "protocol.json").read_text())
reference = json.loads((FIX / "reference.json").read_text())
require(len(reference["rows"]) == plan["expected_body_epochs"], "Incomplete reference")
with zipfile.ZipFile(FIX / "reference-raw.zip") as archive:
    for receipt in reference["receipts"]:
        require(
            hashlib.sha256(archive.read(receipt["raw_file"])).hexdigest()
            == receipt["response_sha256"],
            "Raw response identity changed",
        )
swe = runtime.swe
flags = swe.FLG_SWIEPH | swe.FLG_EQUATORIAL | swe.FLG_J2000 | swe.FLG_ICRS
mask = sum(getattr(swe, k) for k in COORDINATE_FLAGS)
expected = (flags | swe.FLG_NONUT) & mask


def direction(ra: float, dec: float) -> tuple[float, float, float]:
    ra, dec = map(math.radians, (ra, dec))
    return math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)


def angle(x: Sequence[float], y: Sequence[float]) -> float:
    u, v = direction(*x), direction(*y)
    cross = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(q * r for q, r in zip(u, v)))
        )
        * 3600
    )


rows = []
for request in reference["rows"]:
    for route in ["direct_native_ICRF", "existing_chart_coherent_lunar_ICRF"]:
        row = {**request, "route": route}
        try:
            with runtime.preserve_ephemeris_path():
                swe.set_ephe_path(str(a.dataset))
                values, returned = runtime.ephemeris_call(
                    "calc",
                    request["jd_tt"],
                    swe.SUN if request["body"] == "Sun" else swe.MOON,
                    flags,
                )
                model = runtime.ephemeris_model_from_retflag(returned)
                trace = PhysicalEphemerisTrace()
                policy = None
                if (
                    route == "existing_chart_coherent_lunar_ICRF"
                    and request["body"] == "Moon"
                ):
                    values, returned, policy = coherent_lunar_native_state(
                        "calc",
                        request["jd_tt"],
                        flags,
                        request["jd_tt"],
                        model,
                        trace,
                        initial=values,
                        initial_flags=returned,
                    )
                require(
                    returned >= 0 and returned & mask == expected,
                    "Coordinate contract changed",
                )
                require(
                    len(values) == 6 and all(math.isfinite(x) for x in values),
                    "Invalid coordinates",
                )
                require(-90 <= values[1] <= 90, "Invalid declination")
                trace.observe(request["body"], model)
                source = trace.finish()
                row.update(
                    status="computed",
                    returned_flags=returned,
                    model=model,
                    actual_ra_dec=list(values[:2]),
                    error_arcseconds=angle(values[:2], request["reference_ra_dec"]),
                    source=source,
                    lunar_policy=policy,
                )
        except Exception as error:
            row.update(
                status="unavailable_or_error",
                error_type=type(error).__name__,
                error=str(error),
            )
        rows.append(row)
summary = {}
for route in ["direct_native_ICRF", "existing_chart_coherent_lunar_ICRF"]:
    selected = [r for r in rows if r["route"] == route]
    done = [r for r in selected if r["status"] == "computed"]
    summary[route] = dict(
        total=len(selected),
        computed=len(done),
        unavailable_or_error=len(selected) - len(done),
        within_line=sum(
            r["error_arcseconds"] <= plan["position_line_arcseconds"] for r in done
        ),
        outside_line=sum(
            r["error_arcseconds"] > plan["position_line_arcseconds"] for r in done
        ),
        maximum_error_arcseconds=max(
            (r["error_arcseconds"] for r in done), default=None
        ),
        models={
            m: sum(r["model"] == m for r in done)
            for m in sorted({r["model"] for r in done})
        },
    )
passed = all(
    x["unavailable_or_error"] == 0
    and x["outside_line"] == 0
    and x["models"] == {"swieph": len(reference["rows"])}
    for x in summary.values()
)
result = dict(
    recorded_at=datetime.now(timezone.utc).isoformat(),
    dataset=str(a.dataset),
    python=sys.version,
    swiss_version=swe.version,
    source_root=str(a.source_root),
    source_files={
        n: hashlib.sha256((a.source_root / n).read_bytes()).hexdigest()
        for n in [
            "src/fatebridge/core/astro/lunar_source_window.py",
            "src/fatebridge/core/astro_models.py",
            "src/fatebridge/core/ephemeris_runtime.py",
            "src/fatebridge/core/compressed_ephemeris.py",
            "src/fatebridge/data/astro/ephemeris-manifest-v1.json",
        ]
    },
    reference_sha256=seal["reference_sha256"],
    comparison_protocol_sha256=seal["comparison_protocol_sha256"],
    position_line_arcseconds=plan["position_line_arcseconds"],
    explicit_tt_positions_not_future_utc_certification=True,
    shared_dynamics_not_independent_ephemeris=True,
    both_routes_full_pinned_swiss_and_within_line=passed,
    summary=summary,
    rows=rows,
)
with a.output.open("x") as f:
    f.write(json.dumps(result, indent=2) + "\n")
print(json.dumps(summary, indent=2))
raise SystemExit(0 if passed else 1)

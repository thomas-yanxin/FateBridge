"""Freeze an independent ERFA numerical oracle for the IERS expression kernel.

TT/UT1 pairs are synthetic common inputs, not observed Earth orientation or
UTC conversion evidence. This generator never imports FateBridge. Dense expression controls use
Swiss only for the supplied nutation inputs; coherent controls consume
separately generated original-author NPB matrices.
"""

import argparse
import importlib.metadata
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import erfa


def generate():
    if importlib.metadata.version("pyerfa") != "2.0.1.5":
        raise RuntimeError("Pinned pyerfa 2.0.1.5 required")
    rows = []
    for centuries in [-2, -1.75, -1.5, -1, -0.5, 0, 0.25, 0.5, 1, 1.5, 1.75, 2]:
        tt = 2451545.0 + centuries * 36525
        ut = tt - 78.9 / 86400
        dp, de = erfa.nut06a(2451545.0, tt - 2451545.0)
        rows.append(
            {
                "jd_tt": tt,
                "jd_ut1": ut,
                "nutation_longitude_degrees": math.degrees(dp),
                "mean_obliquity_degrees": math.degrees(
                    erfa.obl06(2451545.0, tt - 2451545.0)
                ),
                "gast_degrees": math.degrees(
                    erfa.gst06a(2451545.0, ut - 2451545.0, 2451545.0, tt - 2451545.0)
                )
                % 360,
                "arguments_radians": [
                    float(f(centuries))
                    for f in [
                        erfa.fal03,
                        erfa.falp03,
                        erfa.faf03,
                        erfa.fad03,
                        erfa.faom03,
                        erfa.fave03,
                        erfa.fae03,
                        erfa.fapa03,
                    ]
                ],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "independent_standard_expression_kernel_not_observational_astronomy",
        "pyerfa_version": importlib.metadata.version("pyerfa"),
        "erfa_version": erfa.version.erfa_version,
        "sofa_version": erfa.version.sofa_version,
        "gast_tolerance_arcseconds": 0.001,
        "scope": "Common TT/UT1 and nutation/mean-obliquity inputs; polynomial/ERA/complementary-series implementation check only",
        "cases": rows,
    }


def generate_dense(source_directory: Path, output_directory: Path) -> None:
    """Freeze daily ERFA controls and independent published-decimal evaluation.

    Additional reference-only dependencies: numpy2.5.4,mpmath1.3.0 and
    pyswisseph2.10.3.2. Supply the original IERS table and ERFA2.0.1
    fundamental-argument C sources; production FateBridge is never imported.
    """
    import gzip
    import hashlib
    import re
    import sys

    import mpmath as mp
    import numpy as np
    import swisseph as swe

    work = output_directory
    work.mkdir(parents=True, exist_ok=False)
    source = source_directory
    assert importlib.metadata.version("pyerfa") == "2.0.1.5"
    assert importlib.metadata.version("numpy") == "2.5.4"
    assert importlib.metadata.version("pyswisseph") == "2.10.3.2"
    assert mp.__version__ == "1.3.0"
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    raw = (source / "tab5.2e.txt").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "a5c690b277108e35d88df9cc20fea4120dfbc10a81444bb41b15cf9c6edcd6cb"
    )
    terms = []
    power = None
    for line in raw.decode().splitlines():
        group = re.match(r"j = (\d+)", line.strip())
        if group:
            power = int(group[1])
        parts = line.split()
        if len(parts) != 17 or not parts[0].isdigit():
            continue
        all_args = list(map(int, parts[3:]))
        assert all(all_args[i] == 0 for i in (5, 8, 9, 10, 11, 12))
        arguments = [all_args[i] for i in (0, 1, 2, 3, 4, 6, 7, 13)]
        terms.append([power, parts[1], parts[2], arguments])
    assert len(terms) == 34 and sum(r[0] == 0 for r in terms) == 33
    names = ["fal03", "falp03", "faf03", "fad03", "faom03", "fave03", "fae03", "fapa03"]
    coefficients = []
    for name in names:
        text = (source / (name + ".c")).read_text()
        expression = re.search(r"\ba\s*=\s*(.*?);", text, re.S)[1]
        values = [
            sign + value
            for sign, value in re.findall(r"([-+]?)\s*(\d+\.\d+)", expression)
        ]
        assert len(values) == (5 if len(coefficients) < 5 else 2), (name, values)
        coefficients.append(values)

    count = 146101
    indices = np.arange(count, dtype=np.int64)
    fraction = ((indices * 104729) % 1048576) / 1048576
    fraction[0] = fraction[-1] = 0
    tt = 2451545.0 + indices - 73050 + fraction
    offset = 32.184 + ((indices * 7919) % 1000) / 2
    ut1 = tt - offset / 86400
    assert tt[0] == 2378495 and tt[-1] == 2524595 and np.all(np.diff(tt) > 0)
    controls = np.linspace(0, count - 1, 257, dtype=np.int64)
    plan = dict(
        rows=count,
        TT_bounds=[float(tt[0]), float(tt[-1])],
        sampling="Every adopted TT day, deterministic binary phase (i*104729 mod2^20)/2^20; exact endpoints included",
        synthetic_TT_minus_UT1_seconds="32.184+(i*7919 mod1000)/2, not observations or a DeltaT model",
        original_gast_gate_arcseconds=0.001,
        high_precision_control_indices=controls.tolist(),
        high_precision_diagnostic_gate_arcseconds=1e-7,
        precision_decimal_digits=90,
        comparison_scope="Common-input ERFA expression gate and separately reported fullIAU2000A_R06 diagnostics; per-point dominance/high-precision errors are reported without fitting or changing gates",
    )
    (work / "dense-reference-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    delta = tt - 2451545.0
    dp, _ = erfa.nut06a(2451545.0, delta)
    eps = erfa.obl06(2451545.0, delta)
    dp_deg = np.rad2deg(dp)
    eps_deg = np.rad2deg(eps)
    gmst = erfa.gmst06(2451545.0, ut1 - 2451545.0, 2451545.0, delta)
    common = (
        np.rad2deg(
            gmst + erfa.ee00(2451545.0, delta, np.deg2rad(eps_deg), np.deg2rad(dp_deg))
        )
        % 360
    )
    full = np.rad2deg(erfa.gst06a(2451545.0, ut1 - 2451545.0, 2451545.0, delta)) % 360
    swe.set_ephe_path(str(work / "empty-reference-ephemeris"))
    native_rows = []
    for epoch in tt:
        coordinates, flags = swe.calc(float(epoch), swe.ECL_NUT, swe.FLG_SWIEPH)
        native_rows.append((*coordinates[:3], flags))
    native = np.asarray(native_rows, dtype=np.float64)
    assert np.all(np.isfinite(native)) and np.all(native[:, 3] >= 0)
    native_dp = native[:, 2]
    native_eps = native[:, 1]
    native_common = (
        np.rad2deg(
            gmst
            + erfa.ee00(2451545.0, delta, np.deg2rad(native_eps), np.deg2rad(native_dp))
        )
        % 360
    )
    args = np.array([getattr(erfa, name)((tt - 2451545.0) / 36525) for name in names]).T
    out = work / "dense-reference.npz"
    np.savez_compressed(
        out,
        jd_tt=tt,
        jd_ut1=ut1,
        dpsi_degrees=dp_deg,
        mean_obliquity_degrees=eps_deg,
        common_gast_degrees=common,
        full_IAU_gast_degrees=full,
        native_dpsi_degrees=native_dp,
        native_mean_obliquity_degrees=native_eps,
        native_common_gast_degrees=native_common,
        arguments_radians=args,
    )
    print("Dense ERFA data saved", count, flush=True)

    mp.mp.dps = 90
    polynomial = list(
        map(
            mp.mpf,
            [
                "0.014506",
                "4612.156534",
                "1.3915817",
                "-0.00000044",
                "-0.000029956",
                "-0.0000000368",
            ],
        )
    )

    def ideal(index, dpsi, obliquity):
        t = (mp.mpf(float(tt[index])) - 2451545) / 36525
        arguments = []
        for j, values in enumerate(coefficients):
            value = mp.polyval(list(reversed([mp.mpf(v) for v in values])), t)
            if j < 5:
                value *= mp.pi / 648000
            elif j == 7:
                value *= t
            arguments.append(value % (2 * mp.pi))
        series = mp.fsum(
            (
                mp.mpf(sine)
                * mp.sin(mp.fsum(m * a for m, a in zip(multipliers, arguments)))
                + mp.mpf(cosine)
                * mp.cos(mp.fsum(m * a for m, a in zip(multipliers, arguments)))
            )
            * t**power
            for power, sine, cosine, multipliers in terms
        )
        era = (
            mp.mpf("0.7790572732640")
            + mp.mpf("1.00273781191135448") * (mp.mpf(float(ut1[index])) - 2451545)
        ) % 1
        value = (
            era * 360
            + mp.polyval(list(reversed(polynomial)), t) / 3600
            + mp.mpf(float(dpsi)) * mp.cos(mp.mpf(float(obliquity)) * mp.pi / 180)
            + series / mp.mpf(3600000000)
        )
        return mp.nstr(value % 360, 88)

    high = []
    for index in controls:
        i = int(index)
        high.append(
            dict(
                index=i,
                jd_tt=float(tt[i]),
                jd_ut1=float(ut1[i]),
                ideal_standard_input_degrees=ideal(i, dp_deg[i], eps_deg[i]),
                ideal_native_input_degrees=ideal(i, native_dp[i], native_eps[i]),
            )
        )
    metadata = dict(
        **plan,
        versions={
            name: importlib.metadata.version(name)
            for name in ("pyerfa", "numpy", "pyswisseph", "mpmath")
        },
        erfa_version=erfa.version.erfa_version,
        sofa_version=erfa.version.sofa_version,
        native_version=swe.version,
        native_ECL_NUT_return_flags=sorted(set(map(int, native[:, 3]))),
        production_imported=False,
        primary_IERS_sha256=hashlib.sha256(raw).hexdigest(),
        parsed_published_terms=terms,
        parsed_ERFA_fundamental_coefficients=coefficients,
        reference_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        high_precision_controls=high,
        scope="Synthetic common epochs, independent software and original published formula; not measured Earth orientation, independent sky observations, civil UTC certification or all continuous epochs.",
    )
    (work / "dense-reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    print(
        json.dumps(
            dict(
                rows=count,
                high_precision_controls=len(high),
                reference_sha256=metadata["reference_sha256"],
                production_imported=False,
            )
        ),
        flush=True,
    )

    rows = []
    for control in high:
        i = control["index"]
        for family, psi, obliquity, reference, expected in [
            (
                "IAU_inputs",
                dp_deg[i],
                eps_deg[i],
                common[i],
                control["ideal_standard_input_degrees"],
            ),
            (
                "native_inputs",
                native_dp[i],
                native_eps[i],
                native_common[i],
                control["ideal_native_input_degrees"],
            ),
        ]:
            rows.append(
                dict(
                    index=i,
                    input_family=family,
                    jd_tt=float(tt[i]),
                    jd_ut1=float(ut1[i]),
                    nutation_longitude_degrees=float(psi),
                    mean_obliquity_degrees=float(obliquity),
                    ERFA_common_gast_degrees=float(reference),
                    published_expression_gast_degrees=expected,
                )
            )
    packet = dict(
        kind="independent_published_IERS_decimal_expression_and_ERFA_common_inputs",
        production_imported=False,
        rows=rows,
        versions=metadata["versions"],
        original_gast_gate_arcseconds=0.001,
        high_precision_diagnostic_gate_arcseconds=1e-7,
        precision_decimal_digits=90,
        generator_sha256=metadata["generator_sha256"],
        generator_source=Path(__file__).read_text(),
        IERS_source_sha256=metadata["primary_IERS_sha256"],
        reference_plan=plan,
        source_urls=[
            "https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.2e.txt",
            "https://github.com/liberfa/erfa/tree/v2.0.1/src",
        ],
        scope="257 a-priori uniform controls across the actual adopted TT window, each with2common input families. Exact supplied binary inputs and published decimal expression evaluated at90digits; ERFA unit conversions included. No FateBridge values, source fitting, observed Earth orientation or whole continuous/physical/UTC certification.",
    )
    (work / "high-precision-reference.json.gz").write_bytes(
        gzip.compress(
            (json.dumps(packet, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )


def generate_coherent(
    source_directory: Path, frame_reference: Path, clock_reference: Path, output: Path
) -> None:
    """Independent common-NPB oracle from original-author inputs and ERFA C.

    The input NPZ is produced by the separate original-author C process.
    It contains all146101 fixed dates and the two complete NPB families.
    The clock input contains the257 original-author default-clock controls.
    Neither input is allowed to contain FateBridge-produced values.
    """
    import gzip
    import hashlib
    import re
    import sys

    import mpmath as mp
    import numpy as np

    source = source_directory
    assert importlib.metadata.version("pyerfa") == "2.0.1.5"
    assert importlib.metadata.version("numpy") == "2.5.4"
    assert mp.__version__ == "1.3.0"
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    frame_metadata = json.loads(frame_reference.with_suffix(".json").read_text())
    assert frame_metadata["production_imported"] is False
    assert frame_metadata["rows"] == 146101
    assert (
        hashlib.sha256(frame_reference.read_bytes()).hexdigest()
        == frame_metadata["reference_sha256"]
    )
    clock = json.loads(clock_reference.read_text())
    assert clock["production_imported"] is False and len(clock["rows"]) == 257
    assert clock["source_library_sha256"] == frame_metadata["source_library_sha256"]
    s = (source / "s06.c").read_text()
    poly = re.search(r"static const double sp\[\]\s*=\s*\{(.*?)\};", s, re.S)[1]
    poly = re.findall(r"[-+]?\s*\d+\.\d+e-6", poly)
    assert len(poly) == 6
    terms = []
    for power, block in re.findall(
        r"static const TERM s(\d)\[\]\s*=\s*\{(.*?)\};", s, re.S
    ):
        for args, sine, cosine in re.findall(
            r"\{\{\s*([^}]+)\},\s*([-+0-9.e]+)\s*,\s*([-+0-9.e]+)\s*\}", block
        ):
            terms.append((int(power), list(map(int, args.split(","))), sine, cosine))
    assert len(terms) == 66
    coefficients = []
    for name in [
        "fal03",
        "falp03",
        "faf03",
        "fad03",
        "faom03",
        "fave03",
        "fae03",
        "fapa03",
    ]:
        text = (source / (name + ".c")).read_text()
        expression = re.search(r"\ba\s*=\s*(.*?);", text, re.S)[1]
        values = [
            sign + v for sign, v in re.findall(r"([-+]?)\s*(\d+\.\d+)", expression)
        ]
        assert len(values) == (5 if len(coefficients) < 5 else 2)
        coefficients.append(values)
    indices = np.linspace(0, 146100, 257, dtype=np.int64).tolist()
    with np.load(frame_reference) as z:
        data = {n: z[n] for n in z.files}
    mp.mp.dps = 90
    rows = []
    for index in indices:
        tt = float(data["jd_tt"][index])
        ut = float(data["jd_ut1"][index])
        t = (mp.mpf(tt) - 2451545) / 36525
        fa = []
        for j, c in enumerate(coefficients):
            v = [mp.mpf(x) for x in c]
            if j < 5:
                a = (
                    (mp.fsum(x * t**i for i, x in enumerate(v)) % 1296000)
                    * mp.pi
                    / 648000
                )
            elif j < 7:
                a = (v[0] + v[1] * t) % (2 * mp.pi)
            else:
                a = (v[0] + v[1] * t) * t
            fa.append(a)
        series = mp.fsum(mp.mpf(x.strip()) * t**i for i, x in enumerate(poly))
        series += mp.fsum(
            t**power
            * (
                mp.mpf(sin) * mp.sin(mp.fsum(n * a for n, a in zip(args, fa)))
                + mp.mpf(cos) * mp.cos(mp.fsum(n * a for n, a in zip(args, fa)))
            )
            for power, args, sin, cos in terms
        )
        era_turn = (
            mp.mpf("0.7790572732640")
            + mp.mpf("1.00273781191135448") * (mp.mpf(ut) - 2451545)
        ) % 1
        for label, array in [
            ("native", data["author_values"][index, :9].reshape(3, 3)),
            ("full_IAU", data["npb_full_IAU"][index]),
        ]:
            m = [[mp.mpf(float(x)) for x in row] for row in array]
            x = m[2][0]
            s_cio = series * mp.pi / 648000 - x * m[2][1] / 2
            ax = x / (1 + m[2][2])
            v = [1 - ax * x, -ax * m[2][1], -x]
            p = mp.fsum(a * b for a, b in zip(m[0], v))
            q = mp.fsum(a * b for a, b in zip(m[1], v))
            eo = s_cio - mp.atan2(q, p)
            ideal = (era_turn * 360 - eo * 180 / mp.pi) % 360
            authority = float(erfa.gst06(ut, 0, tt, 0, array)) * 180 / np.pi
            raw_radians = float(erfa.gst06(ut, 0, tt, 0, array))
            native_degrees = mp.mpf(raw_radians) * 180 / mp.pi
            degree_floor = abs(mp.mpf(float(ideal)) - ideal) * 3600
            native_error = abs(native_degrees - ideal) * 3600
            rows.append(
                dict(
                    index=index,
                    input_family=label,
                    jd_ut1=ut,
                    jd_tt=tt,
                    NPB=array.tolist(),
                    ideal_gast_degrees=mp.nstr(ideal, 85),
                    ERFA_common_gast_degrees=authority,
                    ERFA_native_gast_radians=raw_radians,
                    nearest_degree_gast=float(ideal),
                    nearest_degree_error_arcsec=mp.nstr(degree_floor, 85),
                    ERFA_native_radian_error_arcsec=mp.nstr(native_error, 85),
                    degree_format_limited_vs_native_radian=degree_floor > native_error,
                )
            )
    result = dict(
        production_imported=False,
        precision_decimal_digits=90,
        rows=rows,
        source_sha256={
            n: hashlib.sha256((source / n).read_bytes()).hexdigest()
            for n in ["s06.c", "eors.c", "gst06.c"]
        },
        parsed_S06_terms=terms,
        parsed_S06_polynomial_arcsec=poly,
        parsed_fundamental_coefficients=coefficients,
        original_gate_arcsec=0.001,
        extra_arithmetic_diagnostic_arcsec=1e-7,
        control_selection="All predeclared257uniform epochs, two fixed NPB input families,514controls, none selected by residual.",
        scope="Exact supplied IEEE NPB/TT/UT1 operands and published decimal expressions; no matrix construction or physical accuracy certification.",
        native_radian_comparison_scope="Retain ERFA native radians and exact-pi conversion; degree-float representability may prevent matching native-radian precision. Common-degree dominance does not establish unconditional superiority.",
    )
    result.update(
        native_clock_rows=clock["rows"],
        native_frame_boundary_rows=clock["frame_boundary_rows"],
        native_clock_source={
            k: v for k, v in clock.items() if k not in {"rows", "frame_boundary_rows"}
        },
        frame_input_metadata=frame_metadata,
        frame_input_sha256=hashlib.sha256(frame_reference.read_bytes()).hexdigest(),
        clock_input_sha256=hashlib.sha256(clock_reference.read_bytes()).hexdigest(),
        generator_source=Path(__file__).read_text(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    output.write_bytes(
        gzip.compress((json.dumps(result, indent=2) + "\n").encode(), mtime=0)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dense",
        action="store_true",
        help="Write the complete daily authority packet to a new output directory",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        help="Directory containing IERS Table5.2e and ERFA2.0.1 fundamental-argument sources",
    )
    parser.add_argument(
        "--coherent-reference",
        type=Path,
        help="Original-author complete NPB reference NPZ; writes a coherent scalar oracle",
    )
    parser.add_argument(
        "--clock-reference",
        type=Path,
        help="Original-author257 default-clock JSON for the coherent reference",
    )
    args = parser.parse_args()
    if args.coherent_reference is not None:
        if args.dense or args.sources is None or args.clock_reference is None:
            parser.error(
                "--coherent-reference requires --sources and --clock-reference, without --dense"
            )
        generate_coherent(
            args.sources, args.coherent_reference, args.clock_reference, args.output
        )
    elif args.clock_reference is not None:
        parser.error("--clock-reference requires --coherent-reference")
    elif args.dense:
        if args.sources is None:
            parser.error("--dense requires --sources")
        generate_dense(args.sources, args.output)
    else:
        if args.sources is not None:
            parser.error("--sources requires --dense or --coherent-reference")
        args.output.write_text(json.dumps(generate(), indent=2, allow_nan=False) + "\n")

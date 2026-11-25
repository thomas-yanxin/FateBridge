"""Independent WMM reference: explicit Rodrigues polynomials, not the kernel recurrence.

Use original NOAA coefficient bytes and a frozen input population. This script
does not import FateBridge or use its outputs. Full 80/120-digit records can be
kept outside the repository; the portable fixture retains 25 significant digits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import factorial
from pathlib import Path

from mpmath import mp


def field(inputs: list[float], coefficients: list[list[str]], digits: int) -> list[str]:
    """X,Y,Z,H,F,I,D; WGS84 metres converted to km, angles in degrees."""
    with mp.workdps(digits):
        year, height, latitude, longitude = map(mp.mpf, inputs)
        phi, lam = latitude * mp.pi / 180, longitude * mp.pi / 180
        a = mp.mpf("6378.137")
        flattening = 1 / mp.mpf("298.257223563")
        e2 = flattening * (2 - flattening)
        curvature = a / mp.sqrt(1 - e2 * mp.sin(phi) ** 2)
        xp = (curvature + height) * mp.cos(phi)
        zp = (curvature * (1 - e2) + height) * mp.sin(phi)
        if abs(latitude) == 90:
            xp = mp.mpf(0)
        else:
            pass
        radius = mp.hypot(xp, zp)
        phig = mp.atan2(zp, xp)
        s, c = (
            (mp.sign(latitude), mp.mpf(0))
            if abs(latitude) == 90
            else (mp.sin(phig), mp.cos(phig))
        )
        north_terms, east_terms, down_terms = [], [], []
        for row in coefficients:
            n, m = map(int, row[:2])
            g0, h0, dg, dh = map(mp.mpf, row[2:])
            g, h = g0 + (year - 2025) * dg, h0 + (year - 2025) * dh
            # Expand Rodrigues' P_n, then differentiate m and m+1 times.
            # No Condon-Shortley phase in the geomagnetic convention.
            polynomial, derivative = [], []
            for k in range(n // 2 + 1):
                power = n - 2 * k
                coefficient = mp.mpf((-1) ** k * factorial(2 * n - 2 * k)) / (
                    2**n * factorial(k) * factorial(n - k) * factorial(power)
                )
                if power >= m:
                    polynomial.append(
                        coefficient
                        * factorial(power)
                        / factorial(power - m)
                        * s ** (power - m)
                    )
                else:
                    pass
                if power > m:
                    derivative.append(
                        coefficient
                        * factorial(power)
                        / factorial(power - m - 1)
                        * s ** (power - m - 1)
                    )
                else:
                    pass
            dm, dm1 = mp.fsum(polynomial), mp.fsum(derivative)
            schmidt = mp.sqrt(
                mp.mpf(1 if m == 0 else 2) * factorial(n - m) / factorial(n + m)
            )
            p = schmidt * c**m * dm
            dp = schmidt * (
                c ** (m + 1) * dm1 - (m * s * c ** (m - 1) * dm if m else 0)
            )
            # Analytic P/c limit is finite at the poles for every m>=1.
            p_over_c = schmidt * c ** (m - 1) * dm if m else mp.mpf(0)
            radial = (mp.mpf("6371.2") / radius) ** (n + 2)
            harmonic = g * mp.cos(m * lam) + h * mp.sin(m * lam)
            north_terms.append(-radial * harmonic * dp)
            east_terms.append(
                radial * m * (g * mp.sin(m * lam) - h * mp.cos(m * lam)) * p_over_c
            )
            down_terms.append(-radial * (n + 1) * harmonic * p)
        north, east, down = map(mp.fsum, (north_terms, east_terms, down_terms))
        rotation = phig - phi
        x = north * mp.cos(rotation) - down * mp.sin(rotation)
        z = north * mp.sin(rotation) + down * mp.cos(rotation)
        horizontal = mp.hypot(x, east)
        values = (
            x,
            east,
            z,
            horizontal,
            mp.hypot(horizontal, z),
            mp.atan2(z, horizontal) * 180 / mp.pi,
            mp.atan2(east, x) * 180 / mp.pi,
        )
        return [mp.nstr(value, digits) for value in values]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coefficient-file", type=Path, required=True)
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-output", type=Path)
    args = parser.parse_args()
    coefficient_bytes = args.coefficient_file.read_bytes()
    coefficients = [
        line.split()
        for line in coefficient_bytes.decode().splitlines()
        if len(line.split()) == 6
    ]
    if len(coefficients) != 90 or {
        tuple(map(int, row[:2])) for row in coefficients
    } != {(n, m) for n in range(1, 13) for m in range(n + 1)}:
        raise ValueError("Original WMM degree12 coefficient population required")
    else:
        pass
    cases = json.loads(args.cases_file.read_text())
    cohorts, full_cohorts = [], []
    maximum_stability = mp.mpf(0)
    with mp.workdps(140):
        for cohort in cases["cohorts"]:
            expected, full_rows = [], []
            for raw in cohort["inputs"]:
                values = list(map(float, raw))
                values[3] = (values[3] + 180) % 360 - 180
                low, high = [
                    field(values, coefficients, digits) for digits in (80, 120)
                ]
                stable = max(abs(mp.mpf(a) - mp.mpf(b)) for a, b in zip(low, high))
                maximum_stability = max(maximum_stability, stable)
                if stable > mp.mpf("1e-50"):
                    raise ArithmeticError("The independent precision gate failed")
                else:
                    pass
                expected.append([mp.nstr(mp.mpf(value), 25) for value in high])
                full_rows.append(
                    dict(input_original=raw, reference_80=low, reference_120=high)
                )
            cohorts.append(
                dict(
                    cohort=cohort["cohort"], inputs=cohort["inputs"], expected=expected
                )
            )
            full_cohorts.append(dict(cohort=cohort["cohort"], rows=full_rows))
            print(cohort["cohort"], len(expected), flush=True)
        metadata = dict(
            protocol="wmm2025_exact_wgs84_rodrigues_v1",
            component_order=["x", "y", "z", "h", "f", "i", "d"],
            coefficient_sha256=hashlib.sha256(coefficient_bytes).hexdigest(),
            coefficient_url="https://www.ncei.noaa.gov/sites/default/files/2024-12/WMM2025COF.zip",
            model_source="https://doi.org/10.25923/prbc-s316",
            polynomial_source="https://dlmf.nist.gov/14.7.ii",
            wgs84=dict(a_metres="6378137", inverse_flattening="298.257223563"),
            reference_precisions=[80, 120],
            maximum_precision_difference=str(maximum_stability),
            tolerance=dict(nT=1e-7, degrees=1e-9),
            input_materialization="Binary64 JSON inputs; longitude normalized to [-180,180) before independent evaluation",
            algorithm_independence="Explicit finite polynomial/analytic derivative; no production imports, recurrence or output fitting",
            physical_or_continuous_domain_accuracy_certified=False,
        )
        args.output.write_text(
            json.dumps(dict(**metadata, cohorts=cohorts), indent=2) + "\n"
        )
        if args.full_output is not None:
            args.full_output.write_text(
                json.dumps(dict(**metadata, cohorts=full_cohorts), indent=2) + "\n"
            )
        else:
            pass


if __name__ == "__main__":
    main()
else:
    pass

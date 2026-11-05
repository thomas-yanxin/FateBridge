"""Supplemental independent rotation geometry; no FateBridge imports."""

import argparse
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import erfa
import swisseph as swe


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--controls", type=Path, required=True)
    p.add_argument("--ephe", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    controls = json.loads(gzip.decompress(a.controls.read_bytes()))
    swe.set_ephe_path(str(a.ephe))
    rows = []
    selected = [
        r
        for r in controls
        if r["utc"]
        in ["2000-01-01T12:00:00", "2016-12-31T23:59:60.5", "2024-06-01T12:00:00"]
    ]
    for r in selected:
        tt, u = r["jd_tt"], r["jd_ut1_continuous"]
        t2 = tt - 2451545
        u2 = u - 2451545
        gast = float(erfa.gst06a(2451545, u2, 2451545, t2))
        eps = float(erfa.obl06(2451545, t2) + erfa.nut06a(2451545, t2)[1])
        for lon, lat in [(0, 40), (-120, -30), (120, 60)]:
            theta = gast + math.radians(lon)
            phi = math.radians(lat)
            mc = (
                math.degrees(
                    math.atan2(math.sin(theta), math.cos(theta) * math.cos(eps))
                )
                % 360
            )
            x = -math.sin(eps) * math.sin(phi) - math.cos(eps) * math.cos(
                phi
            ) * math.sin(theta)
            y = math.cos(phi) * math.cos(theta)
            asc = math.degrees(math.atan2(y, x)) % 360
            rows.append(
                dict(
                    utc=r["utc"],
                    jd_tt=tt,
                    jd_ut1=u,
                    longitude=lon,
                    latitude=lat,
                    gast_degrees=math.degrees(gast),
                    ascendant=asc,
                    midheaven=mc,
                )
            )
    leap = next(r for r in controls if r["utc"] == "2016-12-31T23:59:60.5")
    tt, u = leap["jd_tt"], leap["jd_ut1_continuous"]
    t2 = tt - 2451545
    u2 = u - 2451545
    sun, flags = swe.calc(tt, swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL)
    assert flags & swe.FLG_SWIEPH
    ecl, _ = swe.calc(tt, swe.ECL_NUT, swe.FLG_SWIEPH)
    # Independent public IERS/SOFA expression, matching the declared Swiss
    # nutation convention rather than silently changing the clock's model.
    gast = math.degrees(
        float(erfa.gmst06(2451545, u2, 2451545, t2) + erfa.eect00(2451545, t2))
    ) + ecl[2] * math.cos(math.radians(ecl[1]))
    frac = (Fraction(u) + Fraction(1, 2)) % 1
    phase = (Fraction(gast) - Fraction(sun[0]) - 360 * frac - 180 + 180) % 360 - 180
    eot = phase * 240
    label = Fraction(2457754.5)
    inputs = []
    for basis, shift in [
        ("local_mean_solar", Fraction(0)),
        ("local_apparent_solar", eot / 86400),
    ]:
        inputs.append(
            dict(
                basis=basis,
                wall="2017-01-01T00:00:00",
                longitude=float((label - Fraction(u) - shift) * 360),
                jd_tt=tt,
                jd_ut1=u,
                utc="2016-12-31T23:59:60.5",
            )
        )
    result = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        created_after_candidate=True,
        development_reference_not_blind=True,
        production_imports=False,
        erfa_version=erfa.__version__,
        swiss_version=swe.version,
        controls_sha256=hashlib.sha256(a.controls.read_bytes()).hexdigest(),
        angle_line_arcseconds=0.02,
        clock_line_seconds=0.0002,
        geometry=rows,
        synthetic_solar_inputs=inputs,
        scope="SOFA IAU2006/2000A rotation/obliquity with polar motion/CIP offsets omitted on both sides. Solar-label inputs use independent IERS/SOFA expression with the same raw Swiss Sun/nutation and file data; not independent planetary dynamics, original clocks or new observations.",
    )
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(geometry_controls=len(rows), solar_inputs=len(inputs))))


if __name__ == "__main__":
    main()

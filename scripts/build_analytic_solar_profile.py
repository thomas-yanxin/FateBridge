"""Extract published ERFA coefficients; no measured ephemeris residual inputs."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/analytic_solar_v23"
DESTINATION = ROOT / "src/fatebridge/data/astronomy/analytic-solar-v1.json"
NUMBER = r"[-+]?(?:\d+\.?(?:\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def build() -> str:
    manifest = json.loads((SOURCE / "source-manifest.json").read_text())
    sources = {}
    for name, record in manifest["files"].items():
        raw = (SOURCE / "sources" / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Pinned primary source changed: " + name)
        sources[name] = re.sub(r"/\*.*?\*/", "", raw.decode(), flags=re.S)
    coefficients = {}
    for name, body in re.findall(
        r"static const double ([es][012][xyz])\[\] = \{(.*?)\};",
        sources["epv00.c"],
        flags=re.S,
    ):
        numbers = [float(n) for n in re.findall(NUMBER, body)]
        if len(numbers) % 3:
            raise ValueError("Incomplete harmonic term")
        coefficients[name] = [numbers[i : i + 3] for i in range(0, len(numbers), 3)]
    assert set(coefficients) == {
        f"{kind}{power}{axis}" for kind in "es" for power in range(3) for axis in "xyz"
    }
    nutation = re.search(r"x\[\] = \{(.*?)\};", sources["nut00b.c"], re.S)
    if nutation is None:
        raise ValueError("Missing nutation series")
    rows = [
        [float(v) for v in re.findall(NUMBER, row)]
        for row in re.findall(r"\{([^{}]+)\}", nutation[1])
    ]
    assert len(rows) == 77 and all(len(row) == 11 for row in rows)
    orientation = {}
    for name in ["am12", "am13", "am21", "am22", "am23", "am32", "am33"]:
        match = re.search(rf"\b{name}\s*=\s*({NUMBER})", sources["epv00.c"])
        if match is None:
            raise ValueError("Missing orientation constant: " + name)
        orientation[name] = float(match[1])
    return (
        json.dumps(
            {
                "model_id": "fatebridge_analytic_solar_v1",
                "version": "1.0.0",
                "source": manifest,
                "license": "erfa-license.txt",
                "author_validated_years": [1900, 2100],
                "coefficient_fit_to_fatebridge_reference": False,
                "epv00": coefficients,
                "orientation": orientation,
                "nut00b": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build()
    if args.check:
        if not DESTINATION.exists() or DESTINATION.read_text() != expected:
            raise SystemExit("Analytic solar profile is stale")
        if (
            not DESTINATION.with_name("erfa-license.txt").exists()
            or DESTINATION.with_name("erfa-license.txt").read_text()
            != (SOURCE / "sources/LICENSE").read_text()
        ):
            raise SystemExit("The distributed ERFA license is missing or changed")
        print("Analytic solar coefficients match pinned ERFA sources")
    else:
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_text(expected)
        license_text = (SOURCE / "sources/LICENSE").read_text()
        DESTINATION.with_name("erfa-license.txt").write_text(license_text)
        print(DESTINATION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

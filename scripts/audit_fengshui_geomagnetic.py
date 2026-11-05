#!/usr/bin/env python3
"""Retain coarse and six-decimal NOAA comparisons independently, including failures."""

import hashlib
import json
from pathlib import Path

from fatebridge.validation.geomagnetic import audit_noaa_c_vectors, audit_noaa_vectors


def main() -> int:
    folder = Path(__file__).parents[1] / "tests/data/fengshui_geomagnetic_v1"
    manifest = json.loads((folder / "provenance.json").read_text())
    integrity = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest["files"].items()
    }
    reports = [
        audit_noaa_vectors((folder / name).read_text(), layout=layout)
        for name, layout in (
            ("NOAA_12_test_values.txt", "published_12"),
            ("NOAA_100_test_values.txt", "coefficient_zip_100"),
        )
    ]
    passed = all(integrity.values()) and all(
        r["all_published_precision_checks_passed"] for r in reports
    )
    c_comparison = audit_noaa_c_vectors(
        json.loads((folder / "NOAA_C_100_main_field_values.json").read_text()),
        (folder / "NOAA_100_test_values.txt").read_text(),
    )
    passed = passed and c_comparison["official_c_implementation_agreement"]
    print(
        json.dumps(
            {
                "source_integrity": integrity,
                "audits": reports,
                "official_c_comparison": c_comparison,
                "all_scoped_numeric_checks_passed": passed,
                "reality_prediction": "not_tested",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

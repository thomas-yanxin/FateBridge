"""Bounded source inventory and four printed affinity controls, no full certificate."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from fatebridge.core.lilly import SIGNS
from fatebridge.core.lilly_radicality import (
    CLAUSES,
    MOON_LATE_SPECIAL,
    OWN_NATURES,
    SHORT_ASCENSION_PRINTED,
    VOC_SOME_PERFORMANCE,
    hour_affinity,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SHA256 = "5d86c81732c1ea00310ea704fd87727f74179a4b2bd96dc9e8a7f5e515d84728"
ARCHIVE_SHA256 = "1e984b9f50f1421672bcaa0b7d28b5da137353d15d2c52ff609056e830b2f90a"


def audit():
    p = ROOT / "tests/fixtures/western-lilly-radicality-1647.json"
    archive = p.with_name("western-lilly-radicality-sources.zip")
    assert hashlib.sha256(p.read_bytes()).hexdigest() == FIXTURE_SHA256
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA256
    ref = json.loads(p.read_text())
    assert ref["production_imports"] is False
    with zipfile.ZipFile(archive) as z:
        for row in ref["source_receipts"]:
            assert hashlib.sha256(z.read(row["file"])).hexdigest() == row["sha256"]
    assert [
        dict(code=c, condition=n, source_pages=pages) for c, n, pages in CLAUSES
    ] == ref["clause_inventory"]
    assert {
        p: dict(heat=h, moisture=m, source_page=page)
        for p, (h, m, page) in OWN_NATURES.items()
    } == ref["own_natures"]
    assert (
        list(SHORT_ASCENSION_PRINTED)
        == ref["source_sign_lists"]["short_ascension_printed_northern_context"]
    )
    assert (
        list(MOON_LATE_SPECIAL) == ref["source_sign_lists"]["moon_late_special_signs"]
    )
    assert (
        list(VOC_SOME_PERFORMANCE)
        == ref["source_sign_lists"]["void_moon_some_performance_signs"]
    )
    cases = []
    for expected in ref["printed_affinity_examples"]:
        # The examples do not give a clock/sect. Evaluate each stated source
        # example under both sects, retaining four examples as the denominator.
        values = [
            hour_affinity(
                expected["hour_ruler"], SIGNS.index(expected["ascendant_sign"]) * 30, s
            )
            for s in ["day", "night", None]
        ]
        cases.append(
            {
                "id": expected["id"],
                "required_route": expected["required_route"],
                "all_three_sect_controls_supported": all(
                    v["supported_under_declared_policy"] is expected["supported"]
                    and v[expected["required_route"]] is True
                    for v in values
                ),
                "observed": values,
            }
        )
    return {
        "fixture_sha256": FIXTURE_SHA256,
        "archive_sha256": ARCHIVE_SHA256,
        "source_assets_verified": len(ref["source_receipts"]),
        "manual_clause_inventory_checked": len(CLAUSES),
        "own_nature_records_checked": len(OWN_NATURES),
        "printed_affinity_examples_compared": len(cases),
        "printed_affinity_examples_reproduced": sum(
            c["all_three_sect_controls_supported"] for c in cases
        ),
        "examples": cases,
        "bounded_reference_gate_passed": all(
            c["all_three_sect_controls_supported"] for c in cases
        ),
        "full_original_text_acceptance": False,
        "complete_judgement_accepted": False,
        "all_three_full_marks_established": False,
        "all_four_full_marks_established": False,
        "authority_certified": False,
        "real_world_observations_added": 0,
        "scope": "Four printed affinity examples and manual clause/nature/sign-list transcription only. Sect repetitions are sensitivity controls, not extra original examples. No complete horoscope, unknown Moon-late cutoff, full source interpretation, measured outcomes or LLM fidelity certificate.",
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit()
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in value.items() if k != "examples"}, ensure_ascii=False
        )
    )
    return 0 if value["bounded_reference_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

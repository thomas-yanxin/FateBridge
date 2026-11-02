"""Bounded checks against the named-author 2024 IHDS educator explanation.

These are written examples and disclosed synthetic instantiations, not new
observed charts or an authenticated 384-line semantic reference. Audio ASR is
deliberately excluded from the acceptance oracle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.human_design_additional_polarities import facts_for
from fatebridge.core.human_design_depth import depth_reference, line_fixings

FIXTURE = "tests/fixtures/human-design-primary-fixing-2024.json"
FIXTURE_SHA256 = "29f9acf94c6cbd475039fff477e46492ea4520bb73c831f81b76e7d7c884b984"


def primary_fixing_checks(root: Path) -> dict[str, Any]:
    raw = (root / FIXTURE).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != FIXTURE_SHA256:
        raise ValueError("Frozen 2024 written fixing reference changed")
    plan = json.loads(raw)
    facts = []
    for fact in plan["source_facts"]:
        gate, line, role = fact["gate"], fact["line"], fact["role"]
        glyph = depth_reference()["gates"][gate - 1]["line_polarities"][line - 1]
        listed = {glyph[role + "_planet"]} - {None}
        listed.update(
            f["additional_planet"] for f in facts_for(gate, line) if f["role"] == role
        )
        facts.append(
            {
                **fact,
                "computed_planet_set": sorted(listed),
                # An illustrative planet is a positive fact, not an exhaustive
                # list or an erratum deleting other explicit 2001 prose facts.
                "matches": fact["planet"] in listed,
            }
        )
    cases = []
    for case in plan["cases"]:
        records = line_fixings(case["activations"])
        recipient = case["recipient"]
        selected = next(
            r
            for r in records
            if r["side"] == recipient["side"] and r["body"] == recipient["body"]
        )
        cases.append(
            {
                **case,
                "computed_recipient": selected,
                "matches": selected["fixing_state"] == case["expected_state"],
            }
        )
    passed = all(r["matches"] for r in [*facts, *cases])
    return {
        "method_id": plan["method_id"],
        "source": plan["source"],
        "plan_sha256": sha,
        "status": "bounded_written_examples_match" if passed else "failed",
        "source_fact_count": len(facts),
        "source_facts_matched": sum(r["matches"] for r in facts),
        "case_count": len(cases),
        "cases_matched": sum(r["matches"] for r in cases),
        "source_facts": facts,
        "cases": cases,
        "failures": [r for r in [*facts, *cases] if not r["matches"]],
        "selection": plan["selection"],
        "limitations": plan["limitations"],
        "audio_asr_used_as_acceptance_oracle": False,
        "complete_fixing_statuses_certified": False,
        "full_384_line_meaning_acceptance": False,
        "authority_certified": False,
    }

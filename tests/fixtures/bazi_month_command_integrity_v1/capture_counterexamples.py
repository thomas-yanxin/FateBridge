"""Preserve complete first accepted contradictions across original nineteen."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain

F = Path(__file__).parent
D = Path("docs/validation/bazi-month-command-integrity-files-v1")


def perturb(chain, fault):
    value = deepcopy(chain)
    month = value["month_command"]
    duty = month["intra_month_duty"]
    source = duty["source_reference"]
    layer = source["duration_source_layers"][0]
    if fault == "invented_duty":
        duty.update(status="adjudicated", selected_stem=month["candidates"][0]["stem"], rule_profile="invented")
    elif fault == "false_duration_sum":
        layer["computed_literal_duration_sum"] += 1
    elif fault == "false_annual_match":
        source["annual_duration_arithmetic"]["matches"] = True
    elif fault == "mixed_witness_month":
        source["scanned_witness"]["month_branch"] = "酉" if month["month_branch"] != "酉" else "卯"
    elif fault == "adopted_table_order":
        layer["chronological_order_adjudicated"] = True
    elif fault == "invented_source_duty":
        layer["selected_duty_stem"] = month["candidates"][0]["stem"]
    elif fault == "wrong_hidden_identity":
        claim = next(c for c in layer["claims"] if c["canonical_stem"] is not None and c["hidden_positions"])
        position = claim["hidden_positions"][0]
        position["branch"] = "子" if claim["canonical_stem"] != "癸" else "卯"
    elif fault == "wrong_conventional_roots":
        source["conventional_month_hidden_stems"] = ["甲"] if month["month_branch"] != "寅" else ["癸"]
    else:
        raise AssertionError(fault)
    return value


FAULTS = ("invented_duty", "false_duration_sum", "false_annual_match", "mixed_witness_month", "adopted_table_order", "invented_source_duty", "wrong_hidden_identity", "wrong_conventional_roots")

if __name__ == "__main__":
    rows = [json.loads(line) for line in gzip.open("docs/validation/bazi-same-target-bureau-files-v1/all408-source-first.jsonl.gz", "rt")]
    first = []
    for row in rows:
        if not row["case"]["is_original_nineteen"]:
            continue
        for fault in FAULTS:
            value = perturb(row["natal"], fault)
            try:
                BaziEvidenceChain.model_validate(value)
                accepted = True
            except ValidationError:
                accepted = False
            first.append({"id": row["case"]["id"], "fault": fault, "first_accepted": accepted, "value": value})
    assert len(first) == 152 and all(x["first_accepted"] for x in first)
    (D / "first152-accepted-contradictions.json.gz").open("xb").write(gzip.compress(json.dumps(first, ensure_ascii=False).encode(), mtime=0))
    (F / "first152-summary.json").open("x").write(json.dumps({"original_cases": 19, "faults_each": list(FAULTS), "first_accepted": len(first), "scope": "output fact contradictions, not newly observed wrong strength calculation", "new_models": 0}, ensure_ascii=False, indent=2) + "\n")
    print("152 first accepted contradictions retained")

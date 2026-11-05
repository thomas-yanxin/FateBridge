"""Preserve complete first accepted contradictions across original nineteen."""

from copy import deepcopy


def perturb(chain, fault):
    value = deepcopy(chain)
    month = value["month_command"]
    duty = month["intra_month_duty"]
    source = duty["source_reference"]
    layer = source["duration_source_layers"][0]
    if fault == "invented_duty":
        duty.update(
            status="adjudicated",
            selected_stem=month["candidates"][0]["stem"],
            rule_profile="invented",
        )
    elif fault == "false_duration_sum":
        layer["computed_literal_duration_sum"] += 1
    elif fault == "false_annual_match":
        source["annual_duration_arithmetic"]["matches"] = True
    elif fault == "mixed_witness_month":
        source["scanned_witness"]["month_branch"] = (
            "酉" if month["month_branch"] != "酉" else "卯"
        )
    elif fault == "adopted_table_order":
        layer["chronological_order_adjudicated"] = True
    elif fault == "invented_source_duty":
        layer["selected_duty_stem"] = month["candidates"][0]["stem"]
    elif fault == "wrong_hidden_identity":
        claim = next(
            c
            for c in layer["claims"]
            if c["canonical_stem"] is not None and c["hidden_positions"]
        )
        position = claim["hidden_positions"][0]
        position["branch"] = "子" if claim["canonical_stem"] != "癸" else "卯"
    elif fault == "wrong_conventional_roots":
        source["conventional_month_hidden_stems"] = (
            ["甲"] if month["month_branch"] != "寅" else ["癸"]
        )
    else:
        raise AssertionError(fault)
    return value

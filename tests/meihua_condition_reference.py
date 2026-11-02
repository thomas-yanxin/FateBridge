"""Narrow historical-output adapter for the frozen v41 null-first policy.

This is not a production oracle: new applicability is checked independently
against the pre-edit truth table and frozen literal geometries. Only the
predeclared null -> false correction may be restored for historical hashes.
"""

from copy import deepcopy


def restore_historical_undetermined_flags(result):
    result = deepcopy(result)
    interpretation = result["interpretation"]
    layers = [interpretation, *(interpretation.get("casting_readings") or [])]
    for layer in layers:
        stage = layer.get("stage_emphasis")
        if stage is None:
            continue
        for clause in [
            *stage["relative_generation_clauses"],
            stage["mixed_generation_control"],
            *stage["scenario_clauses"],
        ]:
            if (
                clause["structural_condition_met"] is False
                and clause["scenario_condition_met"] is None
            ):
                assert clause["full_clause_applies"] is False
                clause["full_clause_applies"] = None
        timing = stage["obstruction_timing"]
        if (
            timing["structural_condition_met"] is False
            and timing["scenario_condition_met"] is None
        ):
            assert timing["selected_clause_applies"] is False
            timing["selected_clause_applies"] = None
            for record in timing["attacker_records"]:
                assert record["selected_clause_applies"] is False
                record["selected_clause_applies"] = None
    return result

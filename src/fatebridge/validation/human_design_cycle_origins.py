"""Pure replay of conditional Design-origin cycles and their interpretation."""

from typing import Any, cast

from fatebridge.core.human_design_cycle_origins import (
    alternative_context,
    assemble_origin_comparison,
    origin_body_row,
)
from fatebridge.core.human_design_cycles import (
    BODIES,
    CycleUnavailable,
    derive_body_contacts,
)
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design_clocks import ClockReplay
from fatebridge.validation.human_design_cycle_sources import verify_cycle_sources


def verify_cycle_origin_comparison(
    payload: dict[str, Any], *, clock_replay: ClockReplay
) -> dict[str, Any]:
    evaluated = 0
    try:
        proof = payload["clock_evidence"]
        policy = payload["calculation_policy"]
        flag = proof.get("compare_cycle_origins", False)
        policy_flag = policy.get("compare_cycle_origins", False)
        if (
            type(flag) is not bool
            or type(policy_flag) is not bool
            or flag is not policy_flag
        ):
            raise ValueError(
                "Origin comparison request and calculation policy disagree"
            )
        supplied = payload.get("cycle_origin_comparison")
        if not flag:
            if supplied is not None:
                raise ValueError("Unrequested origin comparison")
            return {"errors": [], "checked_cycle_origin_evaluation_count": 0}
        if supplied is None or payload["cycle_context"]["status"] == "not_requested":
            raise ValueError("Missing requested origin comparison")
        origin = payload["time_scales"]["design"]["jd_tt"]
        if not origin < payload["time_scales"]["personality"]["jd_tt"]:
            raise ValueError("Design origin is not the actual pre-birth epoch")
        alternative = supplied["alternative"]
        if [r["body"] for r in alternative["bodies"]] != list(BODIES):
            raise ValueError("Incomplete or unordered alternative body set")
        verify_cycle_sources(alternative["source_evidence"], alternative["bodies"])
        rebuilt = []
        for row in alternative["bodies"]:
            witnesses = row["evaluation_witnesses"]
            times = [p[0] for p in witnesses]
            if times != sorted(set(times)):
                raise ValueError("Duplicate or unordered alternative witnesses")
            trace = {p[0]: p for p in witnesses}
            unavailable = {
                r["jd_tt"]: r["reason"] for r in row["unavailable_evaluations"]
            }
            if len(unavailable) != len(row["unavailable_evaluations"]) or set(
                unavailable
            ) & set(trace):
                raise ValueError("Conflicting alternative failures")
            used: set[float] = set()
            failed: set[float] = set()

            def read(t: float) -> list[float | int]:
                if t in unavailable:
                    if unavailable[t] != "native_ephemeris_unavailable":
                        raise ValueError("Unknown alternative failure")
                    failed.add(t)
                    raise CycleUnavailable(unavailable[t], t)
                used.add(t)
                return cast(list[float | int], trace[t])

            result = derive_body_contacts(
                row["body"],
                origin,
                read,
                require_swiss_files=policy["require_swiss_files"],
            )
            if used != set(trace) or failed != set(unavailable):
                raise ValueError("Unused or missing alternative witness")
            if row["body"] != "Chiron":
                activation = next(
                    a
                    for a in payload["activations"]["design"]
                    if a["body"] == row["body"]
                )
                if trace.get(origin) != [
                    origin,
                    activation["longitude"],
                    activation["longitude_speed"],
                    activation["return_flags"],
                ]:
                    raise ValueError(
                        "Alternative origin detached from served Design position"
                    )
            for event in result["contacts"]:
                event.update(clock_replay.label_context(event["jd_tt"]))
            result["evaluation_witnesses"] = witnesses
            result["evaluation_source_context_indices"] = row[
                "evaluation_source_context_indices"
            ]
            result["unavailable_evaluations"] = row["unavailable_evaluations"]
            rebuilt.append(origin_body_row(result))
            evaluated += len(used)
        expected_alternative = alternative_context(
            origin,
            rebuilt,
            alternative["source_evidence"],
            policy["require_swiss_files"],
        )
        expected = assemble_origin_comparison(
            payload, payload["cycle_context"], expected_alternative
        )
        if not _same_value(supplied, expected):
            raise ValueError(
                "Alternative derivation, comparison or interpretation mismatch"
            )
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, StopIteration):
        return {
            "errors": [{"code": "cycle_origin_comparison_mismatch"}],
            "checked_cycle_origin_evaluation_count": evaluated,
        }
    return {"errors": [], "checked_cycle_origin_evaluation_count": evaluated}

"""Check all local contact-search derivations, without authenticating the sky."""

from typing import Any, cast

from fatebridge.core.human_design_cycle_summary import FORMAT as SUMMARY_FORMAT
from fatebridge.core.human_design_cycles import (
    BODIES,
    HORIZON_DAYS,
    SCOPE,
    SOURCE_URLS,
    STEP_DAYS,
    CycleUnavailable,
    cycle_ruleset,
    cycle_summary,
    derive_body_contacts,
    origin_source_evidence,
    summary_conventions,
)
from fatebridge.core.human_design_reference_order import reference_ordering
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design_clocks import ClockReplay, verify_clock_records
from fatebridge.validation.human_design_cycle_sources import verify_cycle_sources


def verify_cycle_context(
    payload: dict[str, Any], *, clock_replay: ClockReplay | None = None
) -> dict[str, Any]:
    errors = []
    evaluated = 0
    try:
        context = payload["cycle_context"]
        expected: dict[str, Any]
        if context["status"] == "not_requested":
            expected = {"status": "not_requested"}
        else:
            summary_format = context.get("summary_format")
            if summary_format not in (None, SUMMARY_FORMAT):
                raise ValueError("Unknown cycle summary format")
            if context["ruleset"] != cycle_ruleset():
                raise ValueError("Unknown cycle numerical ruleset")
            birth = payload["time_scales"]["personality"]["jd_tt"]
            replay = (
                clock_replay
                if clock_replay is not None
                else verify_clock_records(payload)
            )
            label, reference_tt = replay.reference_epoch(context["reference_utc"])
            birth_label = payload["birth_utc"]
            if payload["time_scales"]["personality"]["method"].startswith(
                "continuous_TT"
            ):
                birth_label = None
            proof = context["reference_ordering"]
            ordering = reference_ordering(
                birth_label, birth, label, reference_tt, replay_proof=proof
            )
            for key in ("birth", "reference"):
                clock = ordering[key]
                native = clock["source"].get("native_observation")
                if (
                    native is not None
                    and (clock["utc_label"], native["jd_tt"], native["jd_ut1"])
                    not in replay.civil
                ):
                    raise ValueError(
                        "Ordering lacks its actual historical clock observation"
                    )
            if ordering["relation"] == "before":
                raise ValueError("reference precedes birth")
            policy = payload["calculation_policy"]["require_swiss_files"]
            if type(policy) is not bool:
                raise ValueError("invalid backend policy")
            if len(context["bodies"]) != 3 or [
                r["body"] for r in context["bodies"]
            ] != list(BODIES):
                raise ValueError("incomplete body set")
            verify_cycle_sources(context["source_evidence"], context["bodies"])
            rebuilt = []
            for row in context["bodies"]:
                witnesses = row["evaluation_witnesses"]
                times = [p[0] for p in witnesses]
                if times != sorted(set(times)):
                    raise ValueError("duplicate or unsorted witness")
                trace = {p[0]: p for p in witnesses}
                unavailable = {
                    r["jd_tt"]: r["reason"] for r in row["unavailable_evaluations"]
                }
                if len(unavailable) != len(row["unavailable_evaluations"]) or set(
                    unavailable
                ) & set(trace):
                    raise ValueError("conflicting failures")
                used: set[float] = set()
                failed: set[float] = set()

                def read(t: float) -> list[float | int]:
                    if t in unavailable:
                        if unavailable[t] != "native_ephemeris_unavailable":
                            raise ValueError("unknown failure")
                        failed.add(t)
                        raise CycleUnavailable(unavailable[t], t)
                    used.add(t)
                    return cast(list[float | int], trace[t])

                result = derive_body_contacts(
                    row["body"], birth, read, require_swiss_files=policy
                )
                result["origin_source_evidence"] = origin_source_evidence(row["body"])
                if used != set(trace) or failed != set(unavailable):
                    raise ValueError("unused or missing witness")
                if row["body"] != "Chiron" and result["natal_longitude"] is not None:
                    natal = next(
                        a
                        for a in payload["activations"]["personality"]
                        if a["body"] == row["body"]
                    )
                    if (
                        result["natal_longitude"],
                        result["native_return_flag_model"],
                    ) != (natal["longitude"], natal["ephemeris_model"]):
                        raise ValueError("natal source mismatch")
                for event in result["contacts"]:
                    event.update(replay.label_context(event["jd_tt"]))
                result["evaluation_witnesses"] = witnesses
                result["evaluation_source_context_indices"] = row[
                    "evaluation_source_context_indices"
                ]
                result["unavailable_evaluations"] = row["unavailable_evaluations"]
                rebuilt.append(result)
                evaluated += len(used)
            expected = {
                "method_id": "human_design_first_cycle_contacts_v1",
                "status": (
                    "computed_finite_search"
                    if all(r["status"] == "sampled_search_completed" for r in rebuilt)
                    else "partial"
                ),
                "reference_utc": label,
                "reference_jd_tt": reference_tt,
                "birth_jd_tt": birth,
                "reference_ordering": ordering,
                "origin": "personality_birth_longitude_explicit_computational_convention",
                "step_days_tt": STEP_DAYS,
                "horizon_days_tt": HORIZON_DAYS,
                "continuous_completeness_certified": False,
                "timing_accuracy_certified": False,
                "require_swiss_files": policy,
                "source_urls": SOURCE_URLS,
                "ruleset": dict(cycle_ruleset()),
                "scope": (SCOPE),
                "bodies": rebuilt,
                "source_evidence": context["source_evidence"],
            }
            if summary_format == SUMMARY_FORMAT:
                expected["summary_format"] = SUMMARY_FORMAT
                expected["summary_conventions"] = summary_conventions(
                    context["source_evidence"], ordering
                )
        expected_summary = cycle_summary(expected, payload["profile"])
        if not _same_value(context, expected):
            errors.append({"code": "cycle_contact_derivation_mismatch"})
        if not _same_value(payload["cycle_summary"], expected_summary):
            errors.append({"code": "cycle_summary_derivation_mismatch"})
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        StopIteration,
        OverflowError,
    ):
        errors.append({"code": "incomplete_or_malformed_cycle_witnesses"})
    return {
        "errors": errors,
        "checked_cycle_evaluation_count": evaluated,
        "scope": "Local deterministic replay of supplied TT positions and all consumed finite-search witnesses; does not independently authenticate coordinates, TT-to-sky correspondence, continuous completeness, original source priority, or reality.",
    }

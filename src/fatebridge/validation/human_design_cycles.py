"""Check all local contact-search derivations, without authenticating the sky."""

from fractions import Fraction
from typing import Any, cast

from fatebridge.core.human_design_cycle_history import (
    derive_pre_coordinate_body_contacts,
)
from fatebridge.core.human_design_cycle_summary import FORMAT as SUMMARY_FORMAT
from fatebridge.core.human_design_cycles import (
    BODIES,
    HORIZON_DAYS,
    LEGACY_SCOPE,
    PRE_COORDINATE_SCOPE,
    SCOPE,
    SOURCE_URLS,
    STEP_DAYS,
    CycleUnavailable,
    cycle_ruleset,
    cycle_summary,
    derive_body_contacts,
    origin_source_evidence,
    reference_contact_relation,
    summary_conventions,
)
from fatebridge.core.human_design_reference_order import reference_ordering
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design_clocks import ClockReplay, verify_clock_records
from fatebridge.validation.human_design_cycle_sources import verify_cycle_sources

# Exact complete schemas predating the reference/contact comparison fix.
# A current/unknown receipt cannot downgrade its arithmetic by changing only
# a version label and recomputing the business hash.
PRE_REFERENCE_CONTACT_CONTRACTS = frozenset(
    {
        "89c717f00c649ed5373e3a803fb1c6b3190c68b63c1c55dd8f4fdd54aa71927d",
        "5b8d14718cf5015eb9b4f89740da82ca63c9a0af12c5c2169df87ebb0563e04e",
        "fa56c62beed008e190217f69fc8eb89f7abe858c5a4c46fb0d0ac0e77c6c93d4",
        "f66b042abb0a9b04261477989e147609fc9b011cea0e4613fb4183e6c483ae7e",
        "30e391eb24c92dc5b61f9f27b296536cc5891c34367b73e7cc33daee91b8f765",
        "168d79463454686ee3e8afb731ea2ee8d29ae906f0d9ca88c5cf364ea7daba30",
        "570410131790378bf9a4e34e1f7031d5767e6dd9103c88426746099d870400b2",
        "56806b2004d57149ad0067f1e7cb090d4fd3325413a6f21b04b4dc91dd02d4aa",
    }
)


def verify_cycle_context(
    payload: dict[str, Any], *, clock_replay: ClockReplay | None = None
) -> dict[str, Any]:
    errors = []
    evaluated = 0
    legacy = False
    legacy_reference = False
    try:
        context = payload["cycle_context"]
        expected: dict[str, Any]
        if context["status"] == "not_requested":
            expected = {"status": "not_requested"}
        else:
            summary_format = context.get("summary_format")
            if summary_format not in (None, SUMMARY_FORMAT):
                raise ValueError("Unknown cycle summary format")
            legacy = context["ruleset"] == cycle_ruleset(legacy=True)
            legacy_reference = context["ruleset"] == cycle_ruleset(
                legacy_reference_relation=True
            )
            if (
                not (legacy or legacy_reference)
                and context["ruleset"] != cycle_ruleset()
            ):
                errors.append({"code": "cycle_contact_derivation_mismatch"})
                raise ValueError("Unknown cycle numerical ruleset")
            if (legacy or legacy_reference) and payload.get("run_metadata", {}).get(
                "contract_sha256"
            ) not in PRE_REFERENCE_CONTACT_CONTRACTS:
                raise ValueError("Unknown/current contract downgraded cycle arithmetic")
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
            if legacy or legacy_reference:
                # Keep the known clock contradiction visible even when an
                # older receipt also lacks the new coordinate probes.
                ratio = ordering["reference"]["exact_jd_tt"]
                exact_reference = Fraction(
                    int(ratio["numerator"]), int(ratio["denominator"])
                )
                for index, row in enumerate(context["bodies"]):
                    if payload["cycle_summary"]["bodies"][index][
                        "reference_relation"
                    ] != reference_contact_relation(row, exact_reference):
                        errors.append(
                            {
                                "code": "historical_reference_contact_ordering_loss",
                                "path": f"cycle_summary.bodies.{index}.reference_relation",
                            }
                        )
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

                derive = (
                    derive_pre_coordinate_body_contacts
                    if legacy or legacy_reference
                    else derive_body_contacts
                )
                result = derive(row["body"], birth, read, require_swiss_files=policy)
                if not legacy:
                    result["origin_source_evidence"] = origin_source_evidence(
                        row["body"]
                    )
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
                "ruleset": dict(
                    cycle_ruleset(
                        legacy=legacy, legacy_reference_relation=legacy_reference
                    )
                ),
                "scope": (
                    LEGACY_SCOPE
                    if legacy
                    else PRE_COORDINATE_SCOPE if legacy_reference else SCOPE
                ),
                "bodies": rebuilt,
                "source_evidence": context["source_evidence"],
            }
            if not (legacy or legacy_reference) and summary_format == SUMMARY_FORMAT:
                expected["summary_format"] = SUMMARY_FORMAT
                expected["summary_conventions"] = summary_conventions(
                    context["source_evidence"], ordering
                )
        expected_summary = cycle_summary(expected, payload["profile"])
        if legacy or legacy_reference:
            # Reproduce the historical declaration, but never certify a known
            # arithmetic contradiction merely because that version emitted it.
            # The original packet/proof stays unchanged in its archive.
            exact_summary = cycle_summary(
                {**expected, "ruleset": cycle_ruleset()}, payload["profile"]
            )
            for index, (old_body, exact_body) in enumerate(
                zip(expected_summary["bodies"], exact_summary["bodies"], strict=True)
            ):
                if old_body["reference_relation"] != exact_body["reference_relation"]:
                    errors.append(
                        {
                            "code": "historical_reference_contact_ordering_loss",
                            "path": f"cycle_summary.bodies.{index}.reference_relation",
                        }
                    )
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

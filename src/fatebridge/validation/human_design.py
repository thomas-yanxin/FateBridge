"""Verify the served fixed-template reading against a complete original run.

This checks exact text, typed field quotations and internal derivations. It does
not certify arbitrary model prose, historical birth records or a source's truth.
"""

from typing import Any

from fatebridge.core.human_design_apparent_positions import add_apparent_evidence
from fatebridge.core.human_design_birth_clock import verify_birth_clock
from fatebridge.core.human_design_depth import cross_identifier
from fatebridge.core.human_design_evidence import evidence
from fatebridge.core.human_design_gate_context import METHOD as GATE_CONTEXT_METHOD
from fatebridge.core.human_design_mechanics import (
    VALID_PROFILES,
    bodygraph,
    longitude_activation,
    opposite_activation,
)
from fatebridge.core.human_design_references import coherent_human_design_references
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.claims import (
    CalculationClaim,
    _same_value,
    verify_calculation_claims,
)
from fatebridge.validation.human_design_apparent_positions import (
    checked_context,
    declares_legacy_apparent_contract,
)
from fatebridge.validation.human_design_backend import verify_full_backend_report
from fatebridge.validation.human_design_clocks import verify_clock_records
from fatebridge.validation.human_design_comparisons import (
    verify_node_comparison_reports,
)
from fatebridge.validation.human_design_cycle_origins import (
    verify_cycle_origin_comparison,
)
from fatebridge.validation.human_design_cycles import verify_cycle_context
from fatebridge.validation.human_design_execution import verify_native_context
from fatebridge.validation.human_design_historical_polarity import (
    declares_legacy_historical_polarity_contract,
)
from fatebridge.validation.human_design_joint import verify_run_joint_snapshots
from fatebridge.validation.human_design_natal_sources import verify_natal_sources
from fatebridge.validation.human_design_profile_partition import (
    checked_profile_partition,
    declares_legacy_partition_contract,
)
from fatebridge.validation.human_design_provenance import verify_selected_provenance
from fatebridge.validation.human_design_sampling import verify_sampled_interval
from fatebridge.validation.human_design_solar_root import verify_solar_root_context

# These are complete pre-extension schema fingerprints, not selected case IDs.
# A current or unknown contract must include the extension even if all four of
# its regions have been deleted and the business payload has been rehashed.
_PRE_GATE_CONTEXT_CONTRACTS = frozenset(
    {
        "570410131790378bf9a4e34e1f7031d5767e6dd9103c88426746099d870400b2",
        "56806b2004d57149ad0067f1e7cb090d4fd3325413a6f21b04b4dc91dd02d4aa",
    }
)


def _declares_legacy_gate_contract(payload: dict[str, Any]) -> bool:
    if payload.get("run_metadata", {}).get("contract_sha256") not in (
        _PRE_GATE_CONTEXT_CONTRACTS
    ):
        return False
    if (
        "gate_activation_context" in payload
        or "gate_activation_context" in payload.get("interpretation", {})
    ):
        return False
    return not any(
        any(row.get(k) == GATE_CONTEXT_METHOD for k in ("id", "rule_id", "ruleset_id"))
        for key in ("rulesets", "rule_trace")
        for row in payload.get(key, [])
    )


def verify_human_design_reading(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        with coherent_human_design_references():
            result = _verify_human_design_reading(payload)
        return result
    except EphemerisSourceError as error:
        return {
            **result,
            "method_id": "human_design_source_bound_reading_verification_v1",
            "status": "rejected",
            "errors": [*result.get("errors", []), {"code": error.reason}],
            "scope": "本次参考目录来源不一致或不可用，未完成完整解释核验。",
        }


def _verify_human_design_reading(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    checked = 0
    checked_snapshots = 0
    checked_provenance = 0
    checked_cycles = 0
    checked_roots = 0
    checked_fixings = 0
    checked_topologies = 0
    checked_cross_observations = 0
    checked_node_reports = 0
    checked_interval_evaluations = 0
    checked_natal_sources = 0
    legacy_historical_polarity_contract = False
    legacy_gate_contract = False
    legacy_apparent_contract = False
    legacy_partition_contract = False
    profile_partition = None
    checked_position_batches = 0
    native_context = None
    try:
        legacy_gate_contract = _declares_legacy_gate_contract(payload)
        legacy_apparent_contract = declares_legacy_apparent_contract(payload)
        legacy_partition_contract = declares_legacy_partition_contract(payload)
        legacy_historical_polarity_contract = (
            declares_legacy_historical_polarity_contract(payload)
        )
        if not legacy_partition_contract:
            try:
                profile_partition = checked_profile_partition(payload)
            except (KeyError, TypeError, ValueError, IndexError, OverflowError):
                errors.append({"code": "profile_partition_context_mismatch"})
        apparent_context = None
        if not legacy_apparent_contract:
            try:
                apparent_context = checked_context(payload)
                checked_position_batches = apparent_context["unique_batch_count"]
            except (KeyError, TypeError, ValueError, IndexError, OverflowError):
                # A new evidence fault must not suppress pre-existing source
                # diagnostics. Retain the rejection and run the old checks too.
                errors.append({"code": "apparent_position_context_mismatch"})
        verify_birth_clock(payload)
        clock_replay = verify_clock_records(payload)
        native_context = verify_native_context(payload)
        errors.extend(native_context["errors"])
        native_sources = verify_natal_sources(payload)
        errors.extend(native_sources["errors"])
        checked_natal_sources = native_sources["checked_nominal_native_source_count"]
        nodes = verify_node_comparison_reports(payload)
        errors.extend(nodes["errors"])
        checked_node_reports = nodes["checked_node_report_count"]
        interval = verify_sampled_interval(payload)
        errors.extend(interval["errors"])
        checked_interval_evaluations = interval["checked_interval_evaluation_count"]
        root_check = verify_solar_root_context(payload)
        errors.extend(root_check["errors"])
        checked_roots = root_check["checked_root_count"]
        cycle_check = verify_cycle_context(payload, clock_replay=clock_replay)
        errors.extend(cycle_check["errors"])
        checked_cycles = cycle_check["checked_cycle_evaluation_count"]
        origin_check = verify_cycle_origin_comparison(
            payload, clock_replay=clock_replay
        )
        errors.extend(origin_check["errors"])
        checked_cycles += origin_check["checked_cycle_origin_evaluation_count"]
        provenance = verify_selected_provenance(payload)
        errors.extend(provenance["errors"])
        checked_provenance = provenance["checked_activation_count"]
        actual_interpretation = payload["interpretation"]
        statements = actual_interpretation["statements"]
        receipt = payload["run_metadata"]
        claims = [
            CalculationClaim(
                path=basis["path"],
                value=basis["value"],
                run_id=receipt["run_id"],
                business_output_sha256=receipt["business_output_sha256"],
            )
            for statement in statements
            for basis in statement["basis"]
        ]
        if not legacy_gate_contract:
            context_report = payload["gate_activation_context"]
            context_bindings = [
                b
                for c in [context_report["nominal"], *context_report["witnesses"]]
                for b in c["basis"]
            ] + actual_interpretation["gate_activation_context"]["basis"]
            claims.extend(
                CalculationClaim(
                    path=b["path"],
                    value=b["value"],
                    run_id=receipt["run_id"],
                    business_output_sha256=receipt["business_output_sha256"],
                )
                for b in context_bindings
            )
        if not legacy_apparent_contract:
            claims.extend(
                CalculationClaim(
                    path=b["path"],
                    value=b["value"],
                    run_id=receipt["run_id"],
                    business_output_sha256=receipt["business_output_sha256"],
                )
                for b in actual_interpretation["apparent_position_context"]["basis"]
            )
        if not legacy_partition_contract:
            claims.extend(
                CalculationClaim(
                    path=b["path"],
                    value=b["value"],
                    run_id=receipt["run_id"],
                    business_output_sha256=receipt["business_output_sha256"],
                )
                for b in (
                    payload["profile_partition_context"]["basis"]
                    + actual_interpretation["profile_partition_context"]["basis"]
                )
            )
        result = verify_calculation_claims(payload, claims)
        if result["status"] != "verified_structured_facts":
            errors.append({"code": "original_run_or_field_quotation_mismatch"})
        sides = payload["activations"]
        expected_bodies = {
            "Sun",
            "Earth",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
            "NorthNode",
            "SouthNode",
        }
        if set(sides) != {"personality", "design"} or any(
            len(items) != 13 or {a["body"] for a in items} != expected_bodies
            for items in sides.values()
        ):
            errors.append({"code": "incomplete_activation_set"})
        expected_graph = bodygraph(
            (a["gate"] for a in sides["personality"]),
            (a["gate"] for a in sides["design"]),
        )
        checked_topologies = len(
            expected_graph["circuitry"]["topology_completion"]["topologies"]
        )
        for key, value in expected_graph.items():
            if not _same_value(payload["bodygraph"].get(key), value):
                errors.append(
                    {
                        "code": "bodygraph_derivation_mismatch",
                        "path": "bodygraph." + key,
                    }
                )
        for side, items in sides.items():
            by_body = {item["body"]: item for item in items}
            for index, activation in enumerate(items):
                source_body = {"Earth": "Sun", "SouthNode": "NorthNode"}.get(
                    activation["body"]
                )
                if source_body is not None:
                    source_longitude = by_body[source_body]["longitude"]
                    expected = opposite_activation(source_longitude)
                    if activation.get("derived_from") != source_body or not _same_value(
                        activation.get("derivation_source_longitude"), source_longitude
                    ):
                        errors.append(
                            {
                                "code": "opposition_source_mismatch",
                                "path": f"activations.{side}.{index}",
                            }
                        )
                else:
                    expected = longitude_activation(activation["longitude"])
                    if (
                        "derived_from" in activation
                        or "derivation_source_longitude" in activation
                    ):
                        errors.append(
                            {
                                "code": "unexpected_opposition_source",
                                "path": f"activations.{side}.{index}",
                            }
                        )
                for key, value in expected.items():
                    if not _same_value(activation.get(key), value):
                        errors.append(
                            {
                                "code": "activation_derivation_mismatch",
                                "path": f"activations.{side}.{index}.{key}",
                            }
                        )
        if not _same_value(payload.get("variables"), variables_from_activations(sides)):
            errors.append({"code": "variable_derivation_mismatch", "path": "variables"})
        suns = {
            side: next(a for a in items if a["body"] == "Sun")
            for side, items in sides.items()
        }
        for side, items in sides.items():
            by_body = {item["body"]: item for item in items}
            for source, opposite in (("Sun", "Earth"), ("NorthNode", "SouthNode")):
                arc = (
                    by_body[opposite]["longitude"] - by_body[source]["longitude"]
                ) % 360
                if abs(arc - 180) > 1e-8:
                    errors.append(
                        {
                            "code": "opposition_derivation_mismatch",
                            "path": f"activations.{side}.{opposite}",
                        }
                    )
        if (
            abs(
                (suns["personality"]["longitude"] - suns["design"]["longitude"]) % 360
                - 88
            )
            > 1e-7
        ):
            errors.append({"code": "design_solar_arc_mismatch"})
        expected_profile = f"{suns['personality']['line']}/{suns['design']['line']}"
        if (
            payload["profile"] != expected_profile
            or expected_profile not in VALID_PROFILES
        ):
            errors.append({"code": "profile_derivation_mismatch", "path": "profile"})
        expected_angle = (
            "juxtaposition"
            if expected_profile == "4/1"
            else "right" if suns["personality"]["line"] <= 4 else "left"
        )
        expected_identifier = cross_identifier(
            suns["personality"]["gate"], expected_angle
        )
        expected_cross_gates = [
            next(a["gate"] for a in sides[side] if a["body"] == body)
            for side, body in (
                ("personality", "Sun"),
                ("personality", "Earth"),
                ("design", "Sun"),
                ("design", "Earth"),
            )
        ]
        if not _same_value(payload["incarnation_cross"]["gates"], expected_cross_gates):
            errors.append({"code": "cross_gates_derivation_mismatch"})
        if payload["incarnation_cross"]["angle"] != expected_angle or any(
            not _same_value(payload["incarnation_cross"].get(key), value)
            for key, value in expected_identifier.items()
        ):
            errors.append({"code": "cross_identifier_derivation_mismatch"})
        if payload["incarnation_cross"]["order"] != [
            "personality_sun",
            "personality_earth",
            "design_sun",
            "design_earth",
        ]:
            errors.append({"code": "cross_order_mismatch"})
        expected_evidence = evidence(
            payload,
            include_gate_context=not legacy_gate_contract,
            include_profile_partition=not legacy_partition_contract,
            include_historical_polarity=not legacy_historical_polarity_contract,
        )
        if apparent_context is not None:
            add_apparent_evidence(expected_evidence, apparent_context)
        checked_cross_observations = len(
            expected_evidence["source_consistency"]["expanded_cross_name_comparison"][
                "observations"
            ]
        )
        checked_fixings = len(expected_evidence["depth_evidence"]["line_fixings"])
        if not _same_value(actual_interpretation, expected_evidence["interpretation"]):
            errors.append({"code": "text_or_template_basis_mismatch"})
        if not _same_value(
            payload["depth_evidence"], expected_evidence["depth_evidence"]
        ):
            errors.append({"code": "source_or_fixing_derivation_mismatch"})
        # Hash consistency alone cannot establish source fidelity or acceptance.
        # Reject altered source records and invented certification, even when
        # the caller supplies a freshly recomputed hash of the forged payload.
        for key in (
            "rulesets",
            "rule_trace",
            "gate_evidence",
            "gate_activation_context",
            "profile_partition_context",
            "historical_polarity_context",
            "source_consistency",
            "source_summary",
            "validation",
            "definition_bridging",
            "profile_evidence",
        ):
            if key == "gate_activation_context" and legacy_gate_contract:
                continue
            if key == "profile_partition_context" and legacy_partition_contract:
                continue
            if (
                key == "historical_polarity_context"
                and legacy_historical_polarity_contract
            ):
                continue
            if not _same_value(payload.get(key), expected_evidence[key]):
                errors.append({"code": "source_or_acceptance_mismatch", "path": key})
        joint = verify_run_joint_snapshots(payload)
        checked_snapshots = joint["checked_snapshot_count"]
        errors.extend(joint["errors"])
        backend = verify_full_backend_report(payload)
        checked_roots += backend["checked_adjacent_solar_root_count"]
        checked_snapshots += backend["checked_snapshot_count"]
        errors.extend(backend["errors"])
        checked = len(statements)
        if checked != len(expected_evidence["interpretation"]["statements"]):
            errors.append({"code": "incomplete_statement_set"})
    except (
        KeyError,
        TypeError,
        ValueError,
        StopIteration,
        IndexError,
        AttributeError,
        OverflowError,
    ):
        errors.append({"code": "incomplete_or_malformed_original_result"})
    return {
        "native_execution_policy": native_context,
        "profile_partition_context_status": (
            "not_verified"
            if errors
            else (
                "not_in_declared_legacy_contract"
                if legacy_partition_contract
                else (
                    "verified_nominal_role_and_exact_solar_arc_partition"
                    if profile_partition is not None
                    else "not_verified"
                )
            )
        ),
        "checked_apparent_position_batch_count": checked_position_batches,
        "apparent_position_context_status": (
            "not_verified"
            if errors
            else (
                "not_in_declared_legacy_contract"
                if legacy_apparent_contract
                else "verified_supplied_native_batch_geometry"
            )
        ),
        "checked_nominal_native_source_count": checked_natal_sources,
        "checked_node_report_count": checked_node_reports,
        "checked_interval_evaluation_count": checked_interval_evaluations,
        "checked_expanded_cross_observation_count": checked_cross_observations,
        "checked_circuit_topology_count": checked_topologies,
        "checked_fixing_reading_count": checked_fixings,
        "method_id": "human_design_source_bound_reading_verification_v1",
        "status": "rejected" if errors else "verified_fixed_template_reading",
        "gate_activation_context_status": (
            "not_verified"
            if errors
            else (
                "not_in_declared_legacy_contract"
                if legacy_gate_contract
                else "verified_all_current_contexts"
            )
        ),
        "checked_statement_count": checked,
        "checked_joint_snapshot_count": checked_snapshots,
        "checked_nominal_provenance_activation_count": checked_provenance,
        "checked_cycle_evaluation_count": checked_cycles,
        "checked_solar_root_count": checked_roots,
        "errors": errors,
        "scope": "仅核验完整原始run的固定模板释义、字段引用与各联合快照的本地数学派生；不认证见证TT到星体坐标的独立真实性、连续区间穷尽性、任意自由文本、输入出生记录、完整原典或现实预测。须由调用方保管可信原始回执。",
    }

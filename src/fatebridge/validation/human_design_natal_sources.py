"""Check bounded file-context relationships without reopening original files."""

from typing import Any

from fatebridge.core.human_design_natal_sources import (
    BODIES,
    METHOD,
    ROLES,
    SCOPE,
    SOURCE,
    natal_source_summary,
)
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design_source_files import verify_source_files


def verify_natal_sources(payload: dict[str, Any]) -> dict[str, Any]:
    checked = 0
    errors = []
    try:
        source = payload["ephemeris_source_evidence"]
        files = source["files"]
        by_id = verify_source_files(files, allowed_slots=(0, 1))
        contexts = source["contexts"]
        seen = set()
        used_files = set()
        editions: dict[tuple[str, str, int], int] = {}
        for context in contexts:
            body, role, model, status, ids = (
                context[k]
                for k in (
                    "body",
                    "role",
                    "native_return_flag_model",
                    "status",
                    "file_ids",
                )
            )
            if (
                body not in BODIES
                or role not in ROLES
                or model not in {"swieph", "jpl", "moshier"}
                or (role == "solar_root" and body != "Sun")
                or (
                    role == "node_reference"
                    and (body != "NorthNode" or model != "moshier")
                )
            ):
                raise ValueError("Invalid native source body/role/model")
            if ids != sorted(set(ids)) or not set(ids) <= set(by_id):
                raise ValueError("Unbound or duplicate file identities")
            unresolved = context["unresolved_slots"]
            allowed_native = (
                {0, 1} if model == "swieph" else {0} if model == "jpl" else set()
            )
            if (
                not isinstance(unresolved, list)
                or any(type(x) is not int for x in unresolved)
                or unresolved != sorted(set(unresolved))
                or not set(unresolved) <= allowed_native
            ):
                raise ValueError("Invalid unresolved native source slots")
            if status in {
                "analytical_mean_node",
                "library_builtin",
                "identity_unavailable",
            }:
                if (
                    ids
                    or (
                        status == "analytical_mean_node"
                        and (
                            body != "NorthNode"
                            or role not in {"activation", "root_bracket_activation"}
                        )
                    )
                    or (
                        status in {"analytical_mean_node", "library_builtin"}
                        and unresolved
                    )
                    or (
                        status == "identity_unavailable"
                        and set(unresolved) != allowed_native
                    )
                    or (status == "library_builtin" and model != "moshier")
                    or (status == "identity_unavailable" and model == "moshier")
                ):
                    raise ValueError("Invented analytical or unobserved source file")
            elif status == "file_contexts_observed":
                slots = {by_id[i]["slot"] for i in ids}
                allowed = (
                    {0, 1} if model == "swieph" else {0} if model == "jpl" else set()
                )
                if (
                    not slots <= allowed
                    or len(slots) != len(ids)
                    or set(unresolved) & slots
                    or slots | set(unresolved) != allowed
                ):
                    raise ValueError("Missing or irrelevant native source slots")
                for identity in ids:
                    file = by_id[identity]
                    if not identity.startswith("jpl:" if model == "jpl" else "se1:"):
                        raise ValueError("Wrong file format for native model")
                    key = body, model, file["slot"]
                    if key in editions and editions[key] != file["de_number"]:
                        raise ValueError("Native file edition changed")
                    editions[key] = file["de_number"]
            else:
                raise ValueError("Invalid source status")
            count, lo, hi = (
                context[k]
                for k in ("observed_evaluation_count", "minimum_jd_tt", "maximum_jd_tt")
            )
            if (
                type(count) is not int
                or count <= 0
                or type(lo) is not float
                or type(hi) is not float
                or not -1e9 < lo <= hi < 1e9
            ):
                raise ValueError("Malformed native observation summary")
            expected = {
                "body": body,
                "role": role,
                "native_return_flag_model": model,
                "status": status,
                "file_ids": ids,
                "unresolved_slots": unresolved,
                "observed_evaluation_count": count,
                "minimum_jd_tt": lo,
                "maximum_jd_tt": hi,
            }
            context_key = body, role, model, status, tuple(ids), tuple(unresolved)
            if context_key in seen or not _same_value(context, expected):
                raise ValueError("Duplicate or malformed native source context")
            seen.add(context_key)
            used_files.update(ids)
        if payload["calculation_policy"]["require_swiss_files"] and any(
            c["unresolved_slots"] for c in contexts
        ):
            raise ValueError("Strict Swiss file policy has unresolved native contexts")
        if used_files != set(by_id):
            raise ValueError("Unused native source files")
        for side, rows in payload["activations"].items():
            tt = payload["time_scales"][side]["jd_tt"]
            for row in rows:
                body = row["body"]
                if body not in BODIES:
                    continue
                model = position_flag_model(row["return_flags"])
                analytical = (
                    body == "NorthNode"
                    and payload["calculation_policy"]["node_mode"] == "mean"
                )
                matches = [
                    c
                    for c in contexts
                    if c["body"] == body
                    and c["role"] == "activation"
                    and c["native_return_flag_model"] == model
                    and c["minimum_jd_tt"] <= tt <= c["maximum_jd_tt"]
                    and ((c["status"] == "analytical_mean_node") == analytical)
                ]
                if not matches:
                    raise ValueError(
                        "Selected native factor has no compatible observed context"
                    )
                checked += 1
        for tt in (
            payload["time_scales"][s]["jd_tt"] for s in ("personality", "design")
        ):
            if not any(
                c["body"] == "Sun"
                and c["role"] == "solar_root"
                and c["minimum_jd_tt"] <= tt <= c["maximum_jd_tt"]
                for c in contexts
            ):
                raise ValueError("Missing design-root source context")
        from fatebridge.core.human_design_native_positions import DIRECT_BODIES

        assessment = payload["design_solver"]["numerical_precision"][
            "design_body_endpoint_assessment"
        ]
        family = payload["design_solver"]["numerical_precision"]["local_root_family"]
        epochs = [*assessment["evaluations"], *(family["candidates"] if family else [])]
        for epoch in epochs:
            for body, values in zip(DIRECT_BODIES, epoch["native_positions"]):
                model = position_flag_model(values[2])
                analytical = body == "NorthNode" and assessment["node_mode"] == "mean"
                if not any(
                    c["body"] == body
                    and c["role"] == epoch["source_role"]
                    and c["native_return_flag_model"] == model
                    and c["minimum_jd_tt"] <= epoch["jd_tt"] <= c["maximum_jd_tt"]
                    and ((c["status"] == "analytical_mean_node") == analytical)
                    for c in contexts
                ):
                    raise ValueError(
                        "Design endpoint has no compatible observed source context"
                    )
        unidentified = any(
            c["status"] == "identity_unavailable" or c["unresolved_slots"]
            for c in contexts
        )
        expected = {
            "method_id": METHOD,
            "source_url": SOURCE,
            "status": (
                "identity_incomplete"
                if unidentified
                else "observed_contexts_endpoint_verified"
            ),
            "files": files,
            "contexts": contexts,
            "has_unidentified_sources": unidentified,
            "configuration_checked": True,
            "endpoint_file_hashes_checked": True,
            "atomic_file_read_proven": False,
            "accuracy_certified": False,
            "observed_native_position_evaluations": sum(
                c["observed_evaluation_count"] for c in contexts
            ),
            "native_execution_authenticated": False,
            "scope": SCOPE,
        }
        if not _same_value(source, expected) or not _same_value(
            payload["ephemeris_source_summary"], natal_source_summary(source)
        ):
            raise ValueError("Native file consistency policy or scope mismatch")
    except (
        KeyError,
        TypeError,
        ValueError,
        StopIteration,
        IndexError,
        AttributeError,
        OverflowError,
    ):
        errors.append(
            {
                "code": "natal_file_context_or_policy_mismatch",
                "path": "ephemeris_source_evidence",
            }
        )
    return {
        "errors": errors,
        "checked_nominal_native_source_count": checked,
        "native_execution_authenticated": False,
        "scope": "Supplied file metadata, factor/role/model links and stated TT envelope coherence only. Does not authenticate native calls, observation counts, source bytes, exact file-read sets or physical accuracy.",
    }

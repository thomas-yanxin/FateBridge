"""Check conditional mathematical relations against same-result operands.

These certificates prove the named relation and its arithmetic enclosure.
They do not attest the producer's instruction read-set, the upstream native
coordinates, classical force, or physical accuracy of any input operand.
"""

from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from fatebridge.utils.json_digest import digest

ELEMENTS = "木火土金水"
PALACES = "坎坤震巽中乾兑艮离"
STEMS = "甲乙丙丁戊己庚辛壬癸"
NumericUnit = Literal["dimensionless", "engineering_budget_points", "count", "radians"]


class OperandBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    value_sha256: str


class VerifiedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    method_id: str
    output_path: str
    output_sha256: str
    operands: tuple[OperandBinding, ...]
    unit: Literal[
        "dimensionless", "engineering_budget_points", "count", "radians", "categorical"
    ]
    reference_interval_exact: tuple[str, str] | None
    reference_minus_reported_interval_exact: tuple[str, str] | None
    discrete_value: str | None = None
    proof_scope: Literal["mathematical_relation_conditional_on_recorded_operands"] = (
        "mathematical_relation_conditional_on_recorded_operands"
    )
    upstream_dependency_proof: Literal["not_established"] = "not_established"
    physical_accuracy_certified: Literal[False] = False


def pointer(parent: str, key: str | int) -> str:
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def read_pointer(payload: JsonValue, path: str) -> JsonValue:
    value = payload
    for token in path[1:].split("/") if path else ():
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[key]
        elif isinstance(value, list):
            value = value[int(key)]
        else:
            raise ValueError("数学见证路径未指向已有字段")
    return value


def rational(value: JsonValue) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("数学见证需要数值或精确分数字符串")
    return Fraction(value)  # floats denote their exact stored binary64 values


def collect_verified_outputs(
    payload: dict[str, JsonValue],
) -> tuple[VerifiedOutput, ...]:
    """Close supported arithmetic relations without a new ephemeris call."""
    results: list[VerifiedOutput] = []

    def numeric(
        method: str,
        output: str,
        operands: tuple[str, ...],
        unit: NumericUnit,
        interval: tuple[Fraction, Fraction],
        *,
        exact_output: bool = False,
    ) -> None:
        reported = read_pointer(payload, output)
        value = rational(reported)
        if exact_output and interval != (value, value):
            raise RuntimeError("同次精确数学输出与其完整操作数矛盾：" + output)
        results.append(
            VerifiedOutput(
                method_id=method,
                output_path=output,
                output_sha256=digest(reported),
                operands=tuple(
                    OperandBinding(
                        path=p, value_sha256=digest(read_pointer(payload, p))
                    )
                    for p in dict.fromkeys(operands)
                ),
                unit=unit,
                reference_interval_exact=(str(interval[0]), str(interval[1])),
                reference_minus_reported_interval_exact=(
                    str(interval[0] - value),
                    str(interval[1] - value),
                ),
            )
        )

    pending: list[tuple[str, JsonValue, str, JsonValue]] = [
        (pointer("", k), v, "", payload) for k, v in payload.items()
    ]
    while pending:
        path, value, parent_path, parent = pending.pop()
        if isinstance(value, dict):
            if (
                value.get("method_id") == "exact_rational_strength_thresholds_v1"
                and isinstance(value.get("energies_exact"), dict)
                and isinstance(value.get("day_element"), str)
                and all(
                    k in value for k in ("support_exact", "weaken_exact", "share_exact")
                )
            ):
                energies = value["energies_exact"]
                assert isinstance(energies, dict)
                body = value["day_element"]
                assert isinstance(body, str)
                seal = ELEMENTS[(ELEMENTS.index(body) - 1) % 5]
                inputs = tuple(
                    pointer(pointer(path, "energies_exact"), e) for e in ELEMENTS
                )
                amounts = {e: rational(energies[e]) for e in ELEMENTS}
                support = amounts[body] + amounts[seal]
                weaken = sum(
                    (amounts[e] for e in ELEMENTS if e not in {body, seal}), Fraction()
                )
                share = (
                    support / (support + weaken) if support + weaken else Fraction(1, 2)
                )
                method = "exact_component_support_relation_v1"
                exact_targets: tuple[tuple[str, Fraction, NumericUnit], ...] = (
                    ("support_exact", support, "engineering_budget_points"),
                    ("weaken_exact", weaken, "engineering_budget_points"),
                    ("share_exact", share, "dimensionless"),
                )
                for key, exact, unit in exact_targets:
                    numeric(
                        method,
                        pointer(path, key),
                        (*inputs, pointer(path, "day_element")),
                        unit,
                        (exact, exact),
                        exact_output=True,
                    )
                if isinstance(parent, dict):
                    float_targets: tuple[tuple[str, Fraction, NumericUnit], ...] = (
                        ("support_strength", support, "engineering_budget_points"),
                        ("weaken_strength", weaken, "engineering_budget_points"),
                        ("support_share", share, "dimensionless"),
                    )
                    for key, exact, unit in float_targets:
                        if type(parent.get(key)) in (int, float):
                            numeric(
                                method,
                                pointer(parent_path, key),
                                (*inputs, pointer(path, "day_element")),
                                unit,
                                (exact, exact),
                            )

            if (
                "counting_rule" in value
                and "terminal_palace" in value
                and isinstance(value.get("path"), list)
                and type(value.get("count")) is int
            ):
                steps = value["path"]
                assert isinstance(steps, list)
                inputs = tuple(
                    pointer(pointer(pointer(path, "path"), i), "value")
                    for i in range(len(steps))
                )
                total = sum(
                    (rational(read_pointer(payload, p)) for p in inputs), Fraction()
                )
                numeric(
                    "integer_count_trace_sum_v1",
                    pointer(path, "count"),
                    inputs,
                    "count",
                    (total, total),
                    exact_output=True,
                )
                marker_path: str | None = None
                if "/count_trace/" in path:
                    core_path, camp = path.rsplit("/count_trace/", 1)
                    if camp in {"main", "guest"}:
                        candidate = pointer(
                            core_path, "wenchang_palace" if camp == "main" else "shiji"
                        )
                        core_value = read_pointer(payload, core_path)
                        if (
                            isinstance(core_value, dict)
                            and candidate.rsplit("/", 1)[1] in core_value
                        ):
                            marker_path = candidate
                elif (
                    path.endswith("/source_position_recount")
                    and isinstance(parent, dict)
                    and isinstance(parent.get("source_marker"), str)
                ):
                    marker_path = pointer(parent_path, "source_marker")
                if marker_path is not None:
                    # Check the entire declared ring traversal, not only a sum
                    # of terms already chosen by the producer. This is a
                    # relation under the named rule, not source adjudication.
                    from fatebridge.core.metaphysics.taiyi_geometry import (
                        PALACES as TAIYI_PALACES,
                    )
                    from fatebridge.core.metaphysics.taiyi_geometry import RING

                    marker = read_pointer(payload, marker_path)
                    terminal = value["terminal_palace"]
                    assert isinstance(marker, str) and isinstance(terminal, str)
                    weights = {p: n for n, p in TAIYI_PALACES.items() if n != 5}
                    distance = (RING.index(terminal) - RING.index(marker)) % 16
                    visited = [
                        RING[(RING.index(marker) + k) % 16] for k in range(distance)
                    ]
                    terms = [(p, weights[p]) for p in visited if p in weights]
                    if marker not in weights:
                        terms.insert(0, (marker, 1))
                    if not terms:
                        terms = [(marker, weights[marker])]
                    actual_terms = [
                        (step["palace"], step["value"])
                        for step in steps
                        if isinstance(step, dict)
                    ]
                    if actual_terms != terms:
                        raise RuntimeError("太乙计数项不符合所记起点至终宫的完整环路")
                    numeric(
                        "taiyi_recorded_ring_walk_v1",
                        pointer(path, "count"),
                        (marker_path, pointer(path, "terminal_palace")),
                        "count",
                        (Fraction(sum(v for _, v in terms)),) * 2,
                        exact_output=True,
                    )
                if (
                    isinstance(parent, dict)
                    and path.endswith("/main")
                    and "/count_trace" in path
                ):
                    core_path = parent_path.rsplit("/count_trace", 1)[0]
                    target = pointer(core_path, "main_count")
                    numeric(
                        "integer_count_trace_sum_v1",
                        target,
                        inputs,
                        "count",
                        (total, total),
                        exact_output=True,
                    )
                elif (
                    isinstance(parent, dict)
                    and path.endswith("/guest")
                    and "/count_trace" in path
                ):
                    core_path = parent_path.rsplit("/count_trace", 1)[0]
                    target = pointer(core_path, "guest_count")
                    numeric(
                        "integer_count_trace_sum_v1",
                        target,
                        inputs,
                        "count",
                        (total, total),
                        exact_output=True,
                    )

            if (
                value.get("rule_id") == "leaders"
                and isinstance(value.get("inputs"), dict)
                and isinstance(value.get("outputs"), dict)
            ):
                inputs_value, outputs = value["inputs"], value["outputs"]
                assert isinstance(inputs_value, dict) and isinstance(outputs, dict)
                if all(
                    k in outputs for k in ("source_gong", "raw_door_gong", "dun_type")
                ) and isinstance(inputs_value.get("time_ganzhi"), str):
                    hour = inputs_value["time_ganzhi"]
                    origin, direction = outputs["source_gong"], outputs["dun_type"]
                    assert isinstance(hour, str) and isinstance(origin, str)
                    if direction not in {"阴", "阳"}:
                        raise RuntimeError("值使数学见证阴阳方向未定")
                    derived = PALACES[
                        (
                            PALACES.index(origin)
                            + (-1 if direction == "阴" else 1) * STEMS.index(hour[0])
                        )
                        % 9
                    ]
                    target = pointer(pointer(path, "outputs"), "raw_door_gong")
                    if read_pointer(payload, target) != derived:
                        raise RuntimeError("值使逐时九宫运算与同次实际输出矛盾")
                    refs = (
                        pointer(pointer(path, "inputs"), "time_ganzhi"),
                        pointer(pointer(path, "outputs"), "source_gong"),
                        pointer(pointer(path, "outputs"), "dun_type"),
                    )
                    results.append(
                        VerifiedOutput(
                            method_id="nine_palace_elapsed_hour_walk_v1",
                            output_path=target,
                            output_sha256=digest(derived),
                            operands=tuple(
                                OperandBinding(
                                    path=p,
                                    value_sha256=digest(read_pointer(payload, p)),
                                )
                                for p in refs
                            ),
                            unit="categorical",
                            reference_interval_exact=None,
                            reference_minus_reported_interval_exact=None,
                            discrete_value=derived,
                        )
                    )

            if value.get(
                "method_id"
            ) == "human_design_apparent_position_context_v1" and isinstance(
                value.get("batches"), list
            ):
                from fatebridge.core.human_design_interval_geometry import (
                    portable_projection_scalars,
                )

                batches = value["batches"]
                assert isinstance(batches, list)
                for i, batch in enumerate(batches):
                    if (
                        not isinstance(batch, dict)
                        or not isinstance(batch.get("bodies"), list)
                        or not isinstance(batch.get("solar_projection"), list)
                    ):
                        continue
                    bodies, projections = batch["bodies"], batch["solar_projection"]
                    assert isinstance(bodies, list) and isinstance(projections, list)
                    batch_path = pointer(pointer(path, "batches"), i)
                    for j, projection in enumerate(projections):
                        if (
                            not isinstance(projection, dict)
                            or projection.get("arithmetic_method")
                            != "integer_interval_nominal_projection_v2"
                        ):
                            continue
                        body_index = next(
                            k
                            for k, b in enumerate(bodies)
                            if isinstance(b, dict)
                            and b.get("body") == projection["body"]
                        )
                        sun_path = pointer(
                            pointer(pointer(batch_path, "bodies"), 0),
                            "native_coordinates",
                        )
                        body_path = pointer(
                            pointer(pointer(batch_path, "bodies"), body_index),
                            "native_coordinates",
                        )
                        sun, target_values = read_pointer(
                            payload, sun_path
                        ), read_pointer(payload, body_path)
                        assert isinstance(sun, list) and isinstance(target_values, list)
                        radius_path, au_path = pointer(
                            path, "nominal_solar_radius_m"
                        ), pointer(path, "astronomical_unit_m")
                        projection_path = pointer(
                            pointer(batch_path, "solar_projection"), j
                        )
                        resolution_path = pointer(
                            projection_path, "arithmetic_comparison_resolution_radians"
                        )
                        radius, au, resolution = (
                            read_pointer(payload, radius_path),
                            read_pointer(payload, au_path),
                            read_pointer(payload, resolution_path),
                        )
                        assert (
                            type(radius) is int
                            and type(au) is int
                            and type(resolution) is float
                        )
                        calculated = portable_projection_scalars(
                            tuple(float(rational(x)) for x in sun[:3]),
                            tuple(float(rational(x)) for x in target_values[:3]),
                            radius,
                            au,
                            resolution,
                            include_enclosures=True,
                        )
                        enclosures = calculated["arithmetic_enclosures_exact"]
                        assert isinstance(enclosures, dict)
                        projection_refs = (
                            *tuple(pointer(sun_path, k) for k in range(3)),
                            *tuple(pointer(body_path, k) for k in range(3)),
                            radius_path,
                            au_path,
                            resolution_path,
                        )
                        for key in (
                            "separation_radians",
                            "nominal_solar_radius_radians",
                            "projection_margin_radians",
                        ):
                            if projection[key] != calculated[key]:
                                raise RuntimeError("名义几何与同次完整坐标操作数矛盾")
                            bounds = enclosures[key]
                            assert isinstance(bounds, list) and len(bounds) == 2
                            numeric(
                                "integer_interval_nominal_projection_v2",
                                pointer(projection_path, key),
                                projection_refs,
                                "radians",
                                (rational(bounds[0]), rational(bounds[1])),
                            )
            pending.extend(
                (pointer(path, k), v, path, value)
                for k, v in value.items()
                if isinstance(v, (dict, list))
            )
        elif isinstance(value, list):
            pending.extend(
                (pointer(path, i), v, path, value)
                for i, v in enumerate(value)
                if isinstance(v, (dict, list))
            )
    return tuple(sorted(results, key=lambda w: (w.output_path, w.method_id)))


def verify_output_binding(
    witness: VerifiedOutput, payload: dict[str, JsonValue]
) -> None:
    """Rebuild the mathematical relation, not only its serialized checksums."""
    for operand in witness.operands:
        if digest(read_pointer(payload, operand.path)) != operand.value_sha256:
            raise ValueError("数学见证操作数与当前结果不一致")
    if digest(read_pointer(payload, witness.output_path)) != witness.output_sha256:
        raise ValueError("数学见证输出与当前结果不一致")
    candidates = collect_verified_outputs(payload)
    if witness not in candidates:
        raise ValueError("数学见证未通过原操作数重建")


def collect_source_conflicts(
    payload: dict[str, JsonValue], witnesses: tuple[VerifiedOutput, ...]
) -> list[dict[str, JsonValue]]:
    """Record incompatible literals and named formulae; never select a winner."""
    by_path = {w.output_path: w for w in witnesses}
    result: list[dict[str, JsonValue]] = []
    pending: list[tuple[str, JsonValue]] = [
        (pointer("", k), v) for k, v in payload.items()
    ]
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict):
            formula_path: str | None = None
            literal_path: str | None = None
            alternatives: list[JsonValue] = []
            if (
                isinstance(value.get("source_position_recount"), dict)
                and type(value.get("source_table_count")) is int
            ):
                formula_path = pointer(
                    pointer(path, "source_position_recount"), "count"
                )
                literal_path = pointer(path, "source_table_count")
                if type(value.get("actual_count")) is int:
                    alternatives.append(value["actual_count"])
            elif (
                value.get("field") == "raw_door_gong"
                and isinstance(value.get("source_value"), str)
                and isinstance(value.get("evidence_paths"), list)
                and "/source_disagreements/" in path
            ):
                paths = value["evidence_paths"]
                assert isinstance(paths, list)
                board_path = path.rsplit("/source_disagreements/", 1)[0]
                for p in paths:
                    if (
                        isinstance(p, str)
                        and p.startswith("qimen.rule_trace.")
                        and p.endswith(".raw_door_gong")
                    ):
                        formula_path = board_path + "/" + "/".join(p.split(".")[1:])
                        literal_path = pointer(path, "source_value")
                        break
            if formula_path in by_path and literal_path is not None:
                assert formula_path is not None
                computed, literal = read_pointer(payload, formula_path), read_pointer(
                    payload, literal_path
                )
                if "source_recount_matches_table" in value and value[
                    "source_recount_matches_table"
                ] != (computed == literal):
                    raise RuntimeError("来源重算相符标记与同次算数及原表不符")
                if "computed_value" in value and value["computed_value"] != computed:
                    raise RuntimeError("来源分歧的当前值未绑定同次实际输出")
                if computed != literal:
                    alternatives.extend((computed, literal))
                    choices: list[JsonValue] = []
                    for v in alternatives:
                        if v not in choices:
                            choices.append(v)
                    numeric_choices = [v for v in choices if type(v) is int]
                    record: dict[str, JsonValue] = {
                        "status": "incompatible_under_recorded_rule_operands",
                        "formula_output_path": formula_path,
                        "formula_method_id": by_path[formula_path].method_id,
                        "source_literal_path": literal_path,
                        "source_literal_sha256": digest(literal),
                        "computed_value": computed,
                        "literal_value": literal,
                        "finite_recorded_alternatives": choices,
                        "alternatives_exhaustive": False,
                        "preferred_value": None,
                        "source_priority": "not_adjudicated",
                        "original_gate_reclassified_as_passed": False,
                    }
                    if len(numeric_choices) == len(choices):
                        exacts = [rational(v) for v in numeric_choices]
                        record["finite_alternative_enclosure_exact"] = [
                            str(min(exacts)),
                            str(max(exacts)),
                        ]
                        record["enclosure_scope"] = (
                            "finite_recorded_source_alternatives_not_a_physical_or_classical_error_bound"
                        )
                    result.append(record)
            pending.extend(
                (pointer(path, k), v)
                for k, v in value.items()
                if isinstance(v, (dict, list))
            )
        elif isinstance(value, list):
            pending.extend(
                (pointer(path, i), v)
                for i, v in enumerate(value)
                if isinstance(v, (dict, list))
            )
    return sorted(result, key=lambda r: str(r["source_literal_path"]))

"""Reverse only declared component-provenance AST edits, then compare all old code."""

import ast
from copy import deepcopy
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(node):
    return ast.dump(node, include_attributes=False)


def statement(source):
    values = ast.parse(source).body
    require(len(values) == 1, "Scope source must be exactly one statement")
    return values[0]


def expression(source):
    return ast.parse(source, mode="eval").body


class Replace(ast.NodeTransformer):
    def __init__(self, after, before):
        self.after, self.before, self.count = dump(after), before, 0

    def visit(self, node):
        if dump(node) == self.after:
            self.count += 1
            return deepcopy(self.before)
        return super().visit(node)


def change(tree, after, before):
    transform = Replace(after, before)
    tree = transform.visit(tree)
    require(
        transform.count == 1,
        "Declared AST edit missing or duplicated: " + dump(after)[:120],
    )
    return tree


def member(tree, name):
    return next(n for n in tree.body if getattr(n, "name", None) == name)


def remove_keyword(function, name, annotation, default):
    found = [i for i, a in enumerate(function.args.kwonlyargs) if a.arg == name]
    require(len(found) == 1, "Unknown optional clock argument: " + name)
    i = found[0]
    require(
        dump(function.args.kwonlyargs[i].annotation) == dump(expression(annotation))
        and dump(function.args.kw_defaults[i]) == dump(expression(default)),
        "Clock argument changed: " + name,
    )
    function.args.kwonlyargs.pop(i)
    function.args.kw_defaults.pop(i)


def restore_clock(tree, old):
    tree = change(
        tree,
        statement("from fatebridge.core.meihua_clock_input import clock_input_receipt"),
        None,
    )
    function, original = member(tree, "resolve_meihua_clock"), member(
        old, "resolve_meihua_clock"
    )
    remove_keyword(function, "minute_supplied", "bool", "True")
    remove_keyword(
        function, "component_provenance", "str", '"direct_datetime_components"'
    )
    evidence = next(
        n
        for n in function.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "evidence"
    )
    require(
        dump(evidence.annotation) == dump(expression("dict[str, Any]")),
        "Unknown evidence annotation",
    )
    require(isinstance(evidence.value, ast.Dict), "Unknown clock evidence")
    after = expression(
        '"supplied_civil_second; historical_offset_seconds_preserved" if seconds_supplied and minute_supplied else ("supplied_civil_minute; historical_offset_seconds_preserved" if minute_supplied else ("hour_and_second_supplied; minute_00_calculation_default; historical_offset_seconds_preserved" if seconds_supplied else "supplied_civil_hour; minute_and_second_00_calculation_defaults; historical_offset_seconds_preserved"))'
    )
    before = expression(
        '"supplied_civil_second; historical_offset_seconds_preserved" if seconds_supplied else "supplied_civil_minute; historical_offset_seconds_preserved"'
    )
    evidence.value = change(evidence.value, after, before)
    expected_tail = ast.parse("""
supplied = ["year", "month", "day", "hour"]
if minute_supplied:
    supplied.append("minute")
if seconds_supplied:
    supplied.append("second")
evidence["input_components"] = clock_input_receipt(resolved, evidence["instant_utc"], supplied, component_provenance)
return resolved, evidence
""").body
    i = function.body.index(evidence)
    require(
        [dump(n) for n in function.body[i + 1 :]] == [dump(n) for n in expected_tail],
        "Clock changed outside declared component receipt",
    )
    require(isinstance(original.body[-1], ast.Return), "Unknown original clock return")
    old_dict = original.body[-1].value.elts[1]
    require(dump(evidence.value) == dump(old_dict), "Old clock facts changed")
    function.body = [*function.body[:i], deepcopy(original.body[-1])]
    return tree


def restore_request(tree, old):
    function, original = member(tree, "MeihuaAnalysisRequest"), member(
        old, "MeihuaAnalysisRequest"
    )
    current = next(
        n
        for n in function.body
        if isinstance(n, ast.AnnAssign) and n.target.id == "analysis_minute"
    )
    expected = statement(
        'analysis_minute: Optional[StrictInt] = Field(default=None, ge=0, le=59, description="Confirmed civil minute (strict integer 0-59), when known. Omitted/null means unavailable; numerical00 is only the nominal calculation reference, not a claim that the event occurred on the hour. No rounding or measurement-error interval is inferred. Minute and second never add to the cast seed.")'
    )
    require(
        dump(current) == dump(expected),
        "Minute request differs from declared strict unknown/default contract",
    )
    before = next(
        n
        for n in original.body
        if isinstance(n, ast.AnnAssign) and n.target.id == "analysis_minute"
    )
    function.body[function.body.index(current)] = deepcopy(before)
    return tree


def restore_service(tree, old):
    function, original = member(tree, "calculate_meihua_analysis"), member(
        old, "calculate_meihua_analysis"
    )
    remove_keyword(
        function, "_clock_supplied_components", "Optional[list[str]]", "None"
    )
    i = next(
        i for i, a in enumerate(function.args.kwonlyargs) if a.arg == "analysis_minute"
    )
    require(
        dump(function.args.kwonlyargs[i].annotation)
        == dump(expression("Optional[int]"))
        and dump(function.args.kw_defaults[i]) == dump(expression("None")),
        "Unknown nominal minute argument",
    )
    function.args.kwonlyargs[i].annotation = expression("int")
    function.args.kw_defaults[i] = expression("0")
    for source in [
        """if analysis_minute is not None and (type(analysis_minute) is not int or not 0 <= analysis_minute <= 59):
    return ParameterError("analysis_minute须为已确认的0至59整数分钟；未知时省略。", [{"path": "analysis_minute", "code": "invalid_civil_minute"}]).as_result()""",
        "from fatebridge.core.meihua_clock_input import clock_components",
        "supplied_clock = clock_components(analysis_minute, analysis_second, _clock_supplied_components)",
        "from fatebridge.core.meihua_clock_input import apply_clock_input_notice",
        "apply_clock_input_notice(interpretation, clock_resolution)",
    ]:
        function = change(function, statement(source), None)
    call = next(
        n.value
        for n in function.body
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "analysis_datetime" for t in n.targets
        )
    )
    require(
        dump(call.args[4])
        == dump(expression("0 if analysis_minute is None else analysis_minute")),
        "Unexpected nominal minute calculation",
    )
    call.args[4] = expression("analysis_minute")
    current_call = expression(
        'resolve_meihua_clock(analysis_datetime, timezone_name, analysis_utc_offset, seconds_supplied="second" in supplied_clock, minute_supplied="minute" in supplied_clock, component_provenance="bound_request_model_fields_set" if _clock_supplied_components is not None else "direct_service_optional_components")'
    )
    old_call = expression(
        "resolve_meihua_clock(analysis_datetime, timezone_name, analysis_utc_offset, seconds_supplied=analysis_second is not None)"
    )
    change(function, current_call, old_call)
    require(
        dump(function) == dump(original),
        "Service AST changed outside declared input components",
    )
    return tree


def restore_catalog(tree, old):
    tree = change(
        tree,
        statement(
            "from fatebridge.application.meihua_clock_binding import meihua_time_invoke"
        ),
        None,
    )
    return change(
        tree,
        expression("meihua_time_invoke(calculate_meihua_analysis)"),
        expression("raw_invoke(calculate_meihua_analysis)"),
    )


def restore_mcp(tree, old):
    function = member(tree, "model_parameters")
    remove_keyword(function, "additional_presence_fields", "tuple[str, ...]", "()")
    tree = change(
        tree,
        expression(
            "(name in _MCP_PRESENCE_FIELDS or name in additional_presence_fields) and not field.is_required()"
        ),
        expression("name in _MCP_PRESENCE_FIELDS and not field.is_required()"),
    )
    tree = change(
        tree,
        statement(
            'presence_fields = _MCP_PRESENCE_FIELDS | ({"analysis_minute"} if spec.key == "meihua_analysis" else set())'
        ),
        None,
    )
    tree = change(
        tree,
        expression("presence_fields & spec.request_model.model_fields.keys()"),
        expression("_MCP_PRESENCE_FIELDS & spec.request_model.model_fields.keys()"),
    )
    return change(
        tree,
        expression(
            'model_parameters(model, additional_presence_fields=("analysis_minute",) if spec.key == "meihua_analysis" else ())'
        ),
        expression("model_parameters(model)"),
    )


def restore_replay(tree, old):
    return change(
        tree,
        expression(
            '(field.endswith(("use_true_solar_time", "birth_minute")) or (spec.key == "meihua_analysis" and not prefix and field == "analysis_minute" and value is not None)) and field in model.model_fields_set'
        ),
        expression(
            'field.endswith(("use_true_solar_time", "birth_minute")) and field in model.model_fields_set'
        ),
    )


def restore_execution(tree, old):
    return change(
        tree,
        statement(
            """if spec.key == "meihua_analysis" and request is not None:
    from fatebridge.application.meihua_clock_binding import require_meihua_clock_binding
    try:
        require_meihua_clock_binding(result, request)
    except (ValueError, TypeError, KeyError) as exc:
        raise OutputContractError("完整梅花时卦结果与本次钟时输入分量不符") from exc"""
        ),
        None,
    )


SCOPE = {
    "core/meihua_clock.py": ("before-clock.py", restore_clock),
    "core/requests/divination.py": ("before-request-divination.py", restore_request),
    "services/divination.py": ("before-service.py", restore_service),
    "services/catalog/divination.py": ("before-catalog.py", restore_catalog),
    "transports/mcp.py": ("before-mcp-adapter.py", restore_mcp),
    "services/replay_metadata.py": ("before-replay-metadata.py", restore_replay),
    "application/execution.py": ("before-execution.py", restore_execution),
}


def assert_clock_source_scope(root, references):
    for name, (before_name, normalize) in SCOPE.items():
        old = ast.parse((Path(references) / before_name).read_bytes())
        current = ast.parse((Path(root) / name).read_bytes())
        current = normalize(current, old)
        require(
            dump(current) == dump(old),
            "AST changed outside declared clock edits: " + name,
        )

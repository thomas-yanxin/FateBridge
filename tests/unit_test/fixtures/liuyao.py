"""Share mounted charts, frozen case readers and public transport assertions."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pytest import CaptureFixture

from fatebridge.core.liuyao.liuyao_casting import cast_lines_from_codes
from fatebridge.core.liuyao.liuyao_focus import kinship
from fatebridge.core.liuyao.liuyao_judgment import build_conditional_analysis
from fatebridge.core.liuyao.liuyao_najia import build_sixyao_enrichment
from fatebridge.core.liuyao.liuyao_relations import ELEMENTS
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.utils.timezones import parse_timezone_name
from tests.support.transports import SPECS, business, call_cli, native

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def liuyao_cases(directory: str) -> list[dict[str, Any]]:
    return json.loads(
        (FIXTURES / directory / "cases.json").read_text(encoding="utf-8")
    )["cases"]


def all_surfaces(
    payload: dict[str, Any],
    fields: list[str] | None,
    rest: TestClient,
    tmp_path: Path,
    capsys: CaptureFixture[str],
    budget: int = 0,
    *,
    audit: bool = False,
) -> list[dict[str, Any]]:
    spec = SPECS["sixyao"]
    options: dict[str, int | str | bool | list[str]] = {"response_char_limit": budget}
    flags = ["--response-char-limit", str(budget)]
    params = [("response_char_limit", str(budget))]
    if audit:
        options["detail"] = "audit"
        flags += ["--detail", "audit"]
        params.append(("detail", "audit"))
    else:
        pass
    if fields:
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
    else:
        pass
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, local = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    if not budget:
        assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    else:
        pass
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
    return outputs


def conditional_case(case: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    info, lines = mounted_lines(case["base_code"], case["changed_code"])
    # No civil date was provided by these excerpts. Timing is disabled in
    # source comparisons; this clock is test infrastructure, not a recovered date.
    args = dict(
        lines=lines,
        hidden=[],
        month=case["month_branch"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime(2026, 10, 22, 12, tzinfo=parse_timezone_name("Asia/Shanghai")),
        focus_line=case["focus_line"],
        focus_kinship=None,
        timing_days=0,
    )
    return build_conditional_analysis(**{**args, **overrides})


def mounted_lines(
    code: str, changed: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    info, enrichment = build_sixyao_enrichment(code, changed, "甲")
    lines = cast_lines_from_codes(code, changed)
    for line, extra in zip(lines, enrichment):
        line.update(extra)
        if line["change"]:
            line["changed_branch"] = extra["changed_branch"] or extra["branch"]
        else:
            pass
    return info, lines


def hidden_case(case: dict[str, Any]) -> dict[str, Any]:

    info, _ = mounted_lines(case["base_code"], case["changed_code"])
    hidden = dict(
        position=case["focus_line"],
        branch=case["hidden_branch"],
        element=ELEMENTS[case["hidden_branch"]],
        liuqin=kinship(info["current_palace_element"], ELEMENTS[case["hidden_branch"]]),
        flying_branch=case["flying_branch"],
    )
    return conditional_case(case, hidden=[hidden], focus_kind="hidden")


def cyclic_support_case(
    anchors: dict[int, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    # Adversarial DTO graph, not six legally mounted lines or extra chart cases.
    elements = ["土", "火", "木", "水", "金", "金"]
    branches = ["戌", "午", "寅", "子", "申", "酉"]
    lines = [
        dict(position=i + 1, element=e, branch=b, change=i < 5)
        for i, (e, b) in enumerate(zip(elements, branches))
    ]
    parent = {1: 2, 2: 3, 3: 4, 4: 5, 5: 1}
    rows = []
    for p in range(1, 7):
        supports = []
        if p in parent:
            q = parent[p]
            supports.append(
                dict(
                    location="visible",
                    position=q,
                    branch=branches[q - 1],
                    source_grounded=True,
                    held=False,
                    activity_pending=False,
                )
            )
        else:
            pass
        supports += deepcopy((anchors or {}).get(p, []))
        rows.append(dict(position=p, strength=dict(supports=supports)))
    generation = dict(
        sources=[
            dict(
                position=i + 1,
                branch=b,
                condition_match=True,
                activity_condition_match=i < 5,
                source_path=f"sources.{i}",
            )
            for i, b in enumerate(branches)
        ],
        generations=[
            dict(source_position=q, target_position=p, benefit_now=True)
            for p, q in parent.items()
        ],
    )
    return dict(
        element="金",
        subject_position=6,
        lines=lines,
        assessment=dict(lines=rows),
        generation=generation,
        day_ganzhi="乙巳",
        source_path="growth.moving_support",
    )


def read_condition_path(result: dict[str, Any], path: str) -> Any:
    value = {"liuyao_evidence": {"conditional_analysis": result}}
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def classical_case(case: dict[str, Any]) -> dict[str, Any]:
    info, lines = mounted_lines(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=[],
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        focus_kind=case.get("focus_kind"),
        timing_days=0,
    )


def routing_case(case: dict[str, Any]) -> dict[str, Any]:
    if case.get("focus_kind") == "hidden":
        r = build_sixyao_result(
            date=case["date"],
            time="12:00:00",
            gua_code=case["base_code"],
            changed_code=case["changed_code"],
            focus_kind="hidden",
            focus_line=case["focus_line"],
        )
        assert r["nongli"]["dayGanZi"] == case["day_ganzhi"]
        assert r["nongli"]["monthGanZi"][1] == case["month_branch"]
        return r["liuyao_evidence"]["conditional_analysis"]
    else:
        pass
    return conditional_case(case)


def strength_case(case: dict[str, Any]) -> dict[str, Any]:
    info, lines = mounted_lines(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=[],
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        timing_days=0,
    )


def void_case(case: dict[str, Any]) -> dict[str, Any]:
    info, lines = mounted_lines(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=case.get("hidden", []),
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        focus_kind=case.get("focus_kind"),
        timing_days=0,
    )

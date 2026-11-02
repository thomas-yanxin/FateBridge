"""Same-board, projection-aware contract for coexisting branch conditions."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import StrictBool, model_validator

from .output_base import PartialOutput
from .output_liuren_emptiness import Branch


class LiurenBranchFacts(PartialOutput):
    same_branch: Optional[StrictBool] = None
    liuhe: Optional[StrictBool] = None
    liupo: Optional[StrictBool] = None
    liuhai: Optional[StrictBool] = None
    liuchong: Optional[StrictBool] = None
    left_xing_right: Optional[StrictBool] = None
    right_xing_left: Optional[StrictBool] = None
    harmony_annotation: Optional[Literal["破合", "刑合"]] = None


class LiurenBranchPair(PartialOutput):
    id: Optional[str] = None
    left_role: Optional[str] = None
    right_role: Optional[str] = None
    left_branch: Optional[Branch] = None
    right_branch: Optional[Branch] = None
    facts: Optional[LiurenBranchFacts] = None

    @model_validator(mode="after")
    def actual_pair_facts(self) -> "LiurenBranchPair":
        if (
            self.left_branch is not None
            and self.right_branch is not None
            and self.facts is not None
        ):
            from .metaphysics.liureng_branch_relations import branch_pair_facts

            compare_present_branches(
                self.facts.model_dump(exclude_unset=True),
                branch_pair_facts(self.left_branch, self.right_branch),
            )
        return self


class LiurenLessonBranches(PartialOutput):
    index: Optional[int] = None
    lower_branch: Optional[Branch] = None
    upper_branch: Optional[Branch] = None


class LiurenBranchRelations(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_branch_relations_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    day_ganzhi: Optional[str] = None
    calendar_branches: Optional[
        Dict[Literal["year", "month", "day", "hour"], Branch]
    ] = None
    month_general_branch: Optional[Branch] = None
    sky_by_earth: Optional[Dict[Branch, Branch]] = None
    lesson_branches: Optional[List[LiurenLessonBranches]] = None
    transmission_branches: Optional[
        Dict[Literal["initial", "middle", "final"], Branch]
    ] = None
    rows: Optional[List[LiurenBranchPair]] = None
    comprehensive_judgement: None = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def ledger_matches_context(self) -> "LiurenBranchRelations":
        if self.rows is not None and len(self.rows) != 47:
            raise ValueError("六壬支位关系须保留47个比较对象")
        if self.calendar_branches is not None and self.day_ganzhi is not None:
            if (
                self.calendar_branches.get("day", self.day_ganzhi[-1:])
                != self.day_ganzhi[-1:]
            ):
                raise ValueError("六壬支位关系日支与日干支不一致")
        value = self.model_dump(exclude_unset=True)
        if context_available(value):
            compare_present_branches(value, rebuild(value))
        return self


def compare_present_branches(actual: Any, expected: Any) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for k, v in actual.items():
            if k in expected:
                compare_present_branches(v, expected[k])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("六壬支位关系队列缺项或重复")
        for a, b in zip(actual, expected):
            compare_present_branches(a, b)
    elif actual != expected:
        raise ValueError("六壬支位关系与同次支位或并存关系不一致")


def context_available(value: dict[str, Any]) -> bool:
    return (
        value.get("day_ganzhi") is not None
        and isinstance(value.get("calendar_branches"), dict)
        and set(value["calendar_branches"]) == {"year", "month", "day", "hour"}
        and value.get("month_general_branch") is not None
        and isinstance(value.get("sky_by_earth"), dict)
        and len(value["sky_by_earth"]) == 12
        and isinstance(value.get("lesson_branches"), list)
        and len(value["lesson_branches"]) == 4
        and all(
            all(l.get(k) is not None for k in ("index", "lower_branch", "upper_branch"))
            for l in value["lesson_branches"]
        )
        and isinstance(value.get("transmission_branches"), dict)
        and set(value["transmission_branches"]) == {"initial", "middle", "final"}
    )


def rebuild(value: dict[str, Any]) -> dict[str, Any]:
    from .metaphysics.liureng_branch_relations import branch_relations

    cal = value["calendar_branches"]
    return branch_relations(
        day_ganzhi=value["day_ganzhi"],
        year_branch=cal["year"],
        month_branch=cal["month"],
        hour_branch=cal["hour"],
        month_general_branch=value["month_general_branch"],
        sky_by_earth=value["sky_by_earth"],
        lessons=value["lesson_branches"],
        transmissions=[
            value["transmission_branches"][p] for p in ("initial", "middle", "final")
        ],
    )


def _get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def align_branch_relations(board: Any, pillars: Any = None) -> None:
    evidence = _get(board, "branch_relations")
    if evidence is None:
        return
    day = _get(evidence, "day_ganzhi")
    cal = _get(evidence, "calendar_branches") or {}
    if pillars is not None:
        for role in ("year", "month", "day", "hour"):
            actual = _get(_get(pillars, role), "branch")
            if actual is not None and role in cal and cal[role] != actual:
                raise ValueError("六壬支位关系年月日时支与四柱不一致")
        stem = _get(_get(pillars, "day"), "stem")
        branch = _get(_get(pillars, "day"), "branch")
        if (
            day is not None
            and stem is not None
            and branch is not None
            and day != stem + branch
        ):
            raise ValueError("六壬支位关系占日与四柱不一致")
    general = _get(_get(board, "month_general"), "branch")
    own_general = _get(evidence, "month_general_branch")
    if general is not None and own_general is not None and own_general != general:
        raise ValueError("六壬支位关系月将与本课不一致")
    sky = _get(evidence, "sky_by_earth") or {}
    for row in _get(board, "twelve_board") or []:
        earth, upper = _get(row, "earth_branch"), _get(row, "sky_branch")
        if earth in sky and upper is not None and sky[earth] != upper:
            raise ValueError("六壬支位关系与同时返回的天地盘不一致")
    lessons = _get(evidence, "lesson_branches")
    if lessons is not None:
        actual_lessons = _get(board, "four_lessons")
        if actual_lessons is not None:
            if len(lessons) != len(actual_lessons):
                raise ValueError("六壬支位关系四课队列不一致")
            for own, actual in zip(lessons, actual_lessons):
                for k in ("index", "lower_branch", "upper_branch"):
                    a, b = _get(own, k), _get(actual, k)
                    if a is not None and b is not None and a != b:
                        raise ValueError("六壬支位关系与同时返回的四课不一致")
    transmissions = _get(evidence, "transmission_branches") or {}
    actual_transmissions = _get(board, "three_transmissions")
    for position, branch in transmissions.items():
        actual = _get(_get(actual_transmissions, position), "branch")
        if actual is not None and branch != actual:
            raise ValueError("六壬支位关系与同时返回的三传不一致")


def require_complete_branch_relations(board: dict[str, Any]) -> None:
    evidence = board.get("branch_relations")
    if not isinstance(evidence, dict) or not context_available(evidence):
        raise ValueError("完整六壬输出缺少支位关系依据")
    if evidence != rebuild(evidence):
        raise ValueError("完整六壬支位关系依据缺项或不一致")
    align_branch_relations(board)
    traces = [
        r
        for r in board.get("rule_trace", [])
        if r.get("rule_id") == "liuren.branch_relations"
    ]
    expected_trace = {
        "rule_id": "liuren.branch_relations",
        "source_url": evidence["source_url"],
        "source_section": evidence["source_title"],
        "result": {
            "row_count": 47,
            "annotated_harmony_rows": [
                r["id"]
                for r in evidence["rows"]
                if r["facts"]["harmony_annotation"] is not None
            ],
            "comprehensive_judgement": None,
        },
    }
    if traces != [expected_trace]:
        raise ValueError("六壬支位关系轨迹与本次条件不一致")

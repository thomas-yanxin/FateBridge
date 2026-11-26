"""Evaluate selected Ming-edition clauses against calculated Ziwei placements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import TypeAdapter
from typing_extensions import NotRequired, TypedDict

from fatebridge.core.ziwei.ziwei_rulesets import NAJ_MING_SOURCE
from fatebridge.utils.data import EARTHLY_BRANCHES

ConditionRole = Literal["required", "additional", "blocker"]
PatternStatus = Literal["met", "not_met", "source_undetermined"]
PatternScope = Literal["natal", "limits", "catalogue_only"]


class Clause(TypedDict):
    id: str
    role: ConditionRole
    reading: str


class PatternRule(TypedDict):
    id: str
    name: str
    aliases: NotRequired[list[str]]
    scope: PatternScope
    section: str
    frame: int
    quote: str
    conditions: list[Clause]


class PatternSource(TypedDict):
    id: str
    title: str
    url: str
    kind: Literal["facsimile", "transcript"]


class PatternCatalogue(TypedDict):
    id: str
    version: str
    sources: list[PatternSource]
    notes: list[str]
    rules: list[PatternRule]


class PatternCheck(TypedDict):
    id: str
    role: ConditionRole
    present: bool | None


class PatternRecord(TypedDict):
    id: str
    name: str
    frame: int
    status: PatternStatus
    conditions: list[PatternCheck]


class NatalPatternStar(TypedDict):
    star: str
    natal_branch: str
    natal_palace_name: str
    brightness: str | None
    mutagen: str | None


class ChangQuFlank(TypedDict):
    ming_branch: str
    adjacent_branches: list[str]
    matched: bool


class NatalPatternEvidence(TypedDict):
    method_id: str
    version: str
    source: str
    records: list[PatternRecord]
    stars: list[NatalPatternStar]
    chang_qu_flank: ChangQuFlank


class LimitPatternIndex(TypedDict):
    scope: str
    branch: str | None
    natal_lucun_same_palace: bool | None
    natal_tianma_same_palace: bool | None


class LimitPatternEvidence(TypedDict):
    method_id: str
    version: str
    source: str
    records: list[PatternRecord]
    target_lunar_year: int
    annual_branch: str
    natal_lucun_branch: str | None
    natal_tianma_branch: str | None
    limit_indices: list[LimitPatternIndex]


NATAL_PATTERN_STARS = frozenset(
    {"太阳", "太阴", "武曲", "紫微", "左辅", "右弼", "天相", "文昌", "文曲"}
)
QUAN_LU = frozenset({"化权", "化禄"})


@lru_cache(maxsize=1)
def _catalogue() -> PatternCatalogue:
    data = files("fatebridge").joinpath(
        "data/classical/ziwei-naj-ming-named-patterns.json"
    )
    return TypeAdapter(PatternCatalogue).validate_json(data.read_bytes())


def named_pattern_catalogue() -> PatternCatalogue:
    return deepcopy(_catalogue())


def _records(
    scope: PatternScope, checks: Mapping[str, bool | None]
) -> list[PatternRecord]:
    records: list[PatternRecord] = []
    for rule in _catalogue()["rules"]:
        if rule["scope"] != scope:
            continue
        status: PatternStatus = "met"
        conditions: list[PatternCheck] = []
        for clause in rule["conditions"]:
            check = checks[clause["id"]]
            role = clause["role"]
            conditions.append({"id": clause["id"], "role": role, "present": check})
            if role == "additional":
                continue
            if (role == "required" and check is False) or (
                role == "blocker" and check is True
            ):
                status = "not_met"
            elif check is None and status == "met":
                status = "source_undetermined"
        records.append(
            {
                "id": rule["id"],
                "name": rule["name"],
                "frame": rule["frame"],
                "status": status,
                "conditions": conditions,
            }
        )
    return records


def natal_pattern_evidence(
    stars: Iterable[NatalPatternStar], *, ming_branch: str
) -> NatalPatternEvidence:
    """Read source clauses from the actual placement and selected brightness table."""
    positions = {star["star"]: star for star in stars}
    sun, moon, wu_qu = (positions[name] for name in ("太阳", "太阴", "武曲"))
    center = EARTHLY_BRANCHES.index(ming_branch)
    adjacent = [EARTHLY_BRANCHES[(center + offset) % 12] for offset in (-1, 1)]
    chang_qu_flanks = {
        positions[name]["natal_branch"] for name in ("文昌", "文曲")
    } == set(adjacent)
    sun_moon_in_property = (
        sun["natal_palace_name"] == moon["natal_palace_name"] == "田宅宫"
    )
    quan_lu = [star for star in positions.values() if star["mutagen"] in QUAN_LU]
    quan_lu_in_ming = len(quan_lu) == 2 and all(
        star["natal_branch"] == ming_branch for star in quan_lu
    )
    brightness = {star["brightness"] for star in quan_lu}
    both_miao_wang: bool | None = None
    one_in_xian: bool | None = False
    if quan_lu_in_ming:
        if brightness - {"庙", "旺", None}:
            both_miao_wang = False
        elif None not in brightness:
            both_miao_wang = True
        one_in_xian = (
            True if "陷" in brightness else (None if None in brightness else False)
        )
    catalogue = _catalogue()
    return {
        "method_id": catalogue["id"],
        "version": catalogue["version"],
        "source": NAJ_MING_SOURCE,
        "records": _records(
            "natal",
            {
                "sun_mao_in_ming_or_career": sun["natal_branch"] == "卯"
                and sun["natal_palace_name"] in {"命宫", "官禄宫"},
                "moon_hai_in_ming": moon["natal_branch"] == ming_branch == "亥",
                "wu_qu_in_ming": wu_qu["natal_branch"] == ming_branch,
                "wu_qu_in_other_branch": wu_qu["natal_branch"] == ming_branch != "卯",
                "sun_moon_in_property": sun_moon_in_property,
                "property_in_tomb_branch": (
                    sun["natal_branch"] in {"辰", "戌", "丑", "未"}
                    if sun_moon_in_property
                    else None
                ),
                "zi_wei_assistants_in_ming": all(
                    positions[name]["natal_branch"] == ming_branch
                    for name in ("紫微", "左辅", "右弼")
                ),
                "meeting_xiang_wu_yin": None,
                "sun_moon_flank_ming": {sun["natal_branch"], moon["natal_branch"]}
                == set(adjacent),
                "auspicious_star_in_ming": None,
                "void_in_ming": None,
                "quan_lu_in_ming": quan_lu_in_ming,
                "quan_lu_in_miao_wang": both_miao_wang,
                "quan_or_lu_in_xian": one_in_xian,
            },
        ),
        "stars": list(positions.values()),
        "chang_qu_flank": {
            "ming_branch": ming_branch,
            "adjacent_branches": adjacent,
            "matched": chang_qu_flanks,
        },
    }


def limit_pattern_evidence(
    *,
    target_lunar_year: int,
    annual_branch: str,
    daxian_branch: str | None,
    xiaoxian_branch: str | None,
    natal_lucun_branch: str | None,
    natal_tianma_branch: str | None,
) -> LimitPatternEvidence:
    catalogue = _catalogue()
    indices: list[LimitPatternIndex] = [
        {
            "scope": scope,
            "branch": branch,
            "natal_lucun_same_palace": (
                branch == natal_lucun_branch if branch and natal_lucun_branch else None
            ),
            "natal_tianma_same_palace": (
                branch == natal_tianma_branch
                if branch and natal_tianma_branch
                else None
            ),
        }
        for scope, branch in (("大限", daxian_branch), ("小限", xiaoxian_branch))
    ]
    return {
        "method_id": catalogue["id"],
        "version": catalogue["version"],
        "source": NAJ_MING_SOURCE,
        "records": _records(
            "limits", {"weak_shen_ming": None, "limits_meet_lu_ma": None}
        ),
        "target_lunar_year": target_lunar_year,
        "annual_branch": annual_branch,
        "natal_lucun_branch": natal_lucun_branch,
        "natal_tianma_branch": natal_tianma_branch,
        "limit_indices": indices,
    }

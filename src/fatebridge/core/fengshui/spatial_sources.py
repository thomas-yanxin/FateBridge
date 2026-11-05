"""Typed, source-labelled registrations shared by reasoning and search."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .spatial_inputs import CompassDirection


class RegisteredSource(BaseModel):
    model_config = ConfigDict(extra="allow")
    source_id: str | None = None
    title: str
    url: str
    kind: str
    scope: str


class RegisteredRuleset(BaseModel):
    model_config = ConfigDict(extra="allow")
    ruleset_id: str
    version: str
    method: str
    source_ids: list[str]
    scope: str
    sources: list[RegisteredSource] = []


class CompassDesktopRule(BaseModel):
    rule_id: str
    representation: str
    direction: CompassDirection
    source_ids: list[str]


class ResearchCoverage(BaseModel):
    algorithm_id: str
    status: Literal["implemented", "partial", "source_blocked", "not_implemented"]
    implemented_scope: str
    remaining_scope: str | None = None
    required_resolution: str | None = None
    source_ids: list[str]
    sources: list[RegisteredSource] = []


class SpatialSourceBundle(BaseModel):
    bundle_version: str
    sources: dict[str, RegisteredSource]
    rulesets: dict[str, RegisteredRuleset]
    desktop_rules: list[CompassDesktopRule]
    limitations: list[str]
    research_coverage: list[ResearchCoverage]


@lru_cache(maxsize=1)
def _bundle() -> SpatialSourceBundle:
    path = Path(__file__).parents[2] / "data/fengshui/workstation-layout-v1.json"
    return SpatialSourceBundle.model_validate_json(path.read_bytes())


def spatial_ruleset(key: str) -> RegisteredRuleset:
    data = _bundle()
    record = data.rulesets[key].model_copy(deep=True)
    record.sources = [
        data.sources[source_id].model_copy(update=dict(source_id=source_id), deep=True)
        for source_id in record.source_ids
    ]
    return record


def desktop_compass_rules() -> list[CompassDesktopRule]:
    return [rule.model_copy(deep=True) for rule in _bundle().desktop_rules]


def spatial_limitations() -> list[str]:
    return list(_bundle().limitations)


def research_coverage() -> list[ResearchCoverage]:
    data = _bundle()
    return [
        row.model_copy(
            update=dict(
                sources=[
                    data.sources[source_id].model_copy(
                        update=dict(source_id=source_id), deep=True
                    )
                    for source_id in row.source_ids
                ]
            ),
            deep=True,
        )
        for row in data.research_coverage
    ]

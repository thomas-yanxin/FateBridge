"""Projection-safe facts for a source-layered seasonal reference."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class SeasonalHiddenPosition(PartialOutput):
    pillar: Optional[Literal["year", "month", "day", "hour"]] = None
    branch: Optional[str] = None
    hidden_rank: Optional[int] = Field(None, ge=0)


class SeasonalStemObservation(PartialOutput):
    stem: Optional[str] = None
    visible_positions: Optional[List[Literal["year", "month", "day", "hour"]]] = None
    hidden_positions: Optional[List[SeasonalHiddenPosition]] = None


class SeasonalClimateReference(PartialOutput):
    primary: Optional[str] = None
    secondary: Optional[List[str]] = None
    available: Optional[bool] = None
    method_id: Optional[str] = None
    lookup_scope: Optional[str] = None
    chart_adjudication_status: Optional[Literal["not_performed"]] = None
    source_review_status: Optional[
        Literal[
            "source_not_collated",
            "selected_jia_passages_not_full_acceptance",
            "bing_unit_developer_collation_not_full_acceptance",
        ]
    ] = None
    source_ref: Optional[Dict[str, Any]] = None
    source_layers: Optional[Dict[str, Any]] = None
    source_scope: Optional[str] = None
    stem_observations: Optional[List[SeasonalStemObservation]] = None
    observation_scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_pending_source_scope(self) -> "SeasonalClimateReference":
        if self.source_review_status == "source_not_collated" and (
            self.source_ref is not None or self.source_layers is not None
        ):
            raise ValueError("待核简表不能同时声称已核对的原典出处与层次")
        if (
            self.source_review_status
            == "bing_unit_developer_collation_not_full_acceptance"
        ):
            if self.source_ref is not None:
                expected = {
                    "id": "qiongtong_xu_qianqian_bing_v1",
                    "source_sha256": "b7f17fc7fcb7d8faa991efa74d0db391c5066a3793b3fc6787d2612bc6b350a8",
                }
                for key, value in expected.items():
                    if key in self.source_ref and self.source_ref[key] != value:
                        raise ValueError("丙火校勘状态与实际来源身份不符")
            if (
                self.source_layers is not None
                and self.source_layers.get("chart_conditions_status") is not None
                and self.source_layers["chart_conditions_status"] != "not_adjudicated"
            ):
                raise ValueError("丙火来源条件不能冒作已裁定全盘取用")
        return self

"""Projection-safe facts for a source-layered seasonal reference."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class SeasonalHiddenPosition(PartialOutput):
    pillar: Literal["year", "month", "day", "hour"] | None = None
    branch: str | None = None
    hidden_rank: int | None = Field(None, ge=0)


class SeasonalStemObservation(PartialOutput):
    stem: str | None = None
    visible_positions: list[Literal["year", "month", "day", "hour"]] | None = None
    hidden_positions: list[SeasonalHiddenPosition] | None = None


class SeasonalClimateReference(PartialOutput):
    primary: str | None = None
    secondary: list[str] | None = None
    available: bool | None = None
    method_id: str | None = None
    lookup_scope: str | None = None
    chart_adjudication_status: Literal["not_performed"] | None = None
    source_review_status: (
        Literal[
            "source_not_collated",
            "selected_jia_passages_not_full_acceptance",
            "bing_unit_developer_collation_not_full_acceptance",
            "selected_ding_spring_passages_not_full_acceptance",
            "selected_ding_summer_passages_not_full_acceptance",
            "selected_ding_autumn_passages_not_full_acceptance",
            "selected_ding_winter_passages_not_full_acceptance",
            "selected_wu_yi_passages_not_full_acceptance",
            "selected_ji_spring_passages_not_full_acceptance",
            "selected_ji_summer_passages_not_full_acceptance",
            "selected_ji_autumn_passages_not_full_acceptance",
            "selected_ji_winter_passages_not_full_acceptance",
        ]
        | None
    ) = None
    source_ref: dict[str, OpenJsonValue] | None = None
    source_layers: dict[str, OpenJsonValue] | None = None
    source_scope: str | None = None
    stem_observations: list[SeasonalStemObservation] | None = None
    observation_scope: str | None = None

    @model_validator(mode="after")
    def preserve_pending_source_scope(self) -> "SeasonalClimateReference":
        if self.source_review_status == "source_not_collated" and (
            self.source_ref is not None or self.source_layers is not None
        ):
            raise ValueError("待核简表不能同时声称已核对的原典出处与层次")
        else:
            pass
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
                    else:
                        pass
            else:
                pass
        else:
            pass
        if (
            self.source_layers is not None
            and self.source_layers.get("chart_conditions_status") is not None
            and self.source_layers["chart_conditions_status"] != "not_adjudicated"
        ):
            raise ValueError("调候来源条件不能冒作已裁定全盘取用")
        else:
            pass
        return self

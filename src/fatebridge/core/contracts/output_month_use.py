"""Projection-compatible contracts for source-scoped month-use witnesses."""

from typing import Annotated, Literal

from pydantic import model_validator

from fatebridge.core.contracts.output_base import FULL_FACT, PRESENT_FACT, PartialOutput
from fatebridge.core.month_use import MonthUseKind


class MonthUseClaim(PartialOutput):
    pdf_pages: Annotated[list[int] | None, FULL_FACT] = None
    text: Annotated[str | None, FULL_FACT] = None
    permission: Annotated[str | None, FULL_FACT] = None


class MonthUseSource(PartialOutput):
    id: Annotated[str | None, FULL_FACT] = None
    author: Annotated[str | None, FULL_FACT] = None
    title: Annotated[str | None, FULL_FACT] = None
    edition: Annotated[str | None, FULL_FACT] = None
    url: Annotated[str | None, FULL_FACT] = None
    source_sha256: Annotated[str | None, FULL_FACT] = None
    claims: Annotated[dict[str, MonthUseClaim] | None, FULL_FACT] = None


class MonthUseWitness(PartialOutput):
    id: Annotated[str | None, FULL_FACT] = None
    kind: Annotated[MonthUseKind | None, FULL_FACT] = None
    element: Annotated[str | None, FULL_FACT] = None
    role_family: Annotated[str | None, FULL_FACT] = None
    stem: Annotated[str | None, PRESENT_FACT] = None
    ten_god: Annotated[str | None, PRESENT_FACT] = None
    possible_ten_gods: Annotated[list[str] | None, FULL_FACT] = None
    month_hidden_stems: list[str] | None = None
    visible_positions: list[str] | None = None
    branches: list[str] | None = None
    branch_positions: dict[str, list[str]] | None = None
    label: str | None = None
    source_pdf_pages: Annotated[list[int] | None, FULL_FACT] = None
    source_claim_ids: Annotated[list[str] | None, FULL_FACT] = None

    @model_validator(mode="after")
    def preserve_source_precision(self) -> "MonthUseWitness":
        if self.kind == "complete_month_triad" and (
            self.stem is not None or self.ten_god is not None
        ):
            raise ValueError("会支十神类不能伪作唯一化干或确定正偏十神")
        else:
            pass
        if self.ten_god is not None and self.possible_ten_gods is not None:
            if self.possible_ten_gods != [self.ten_god]:
                raise ValueError("已确定透干的十神身份须保持精确，不扩成另一正偏")
            else:
                pass
        else:
            pass
        return self


class MonthUseResolution(PartialOutput):
    method_id: Literal["ziping_month_use_witnesses_v1"] | None = None
    month_branch: str | None = None
    policy_scope: Literal["miscellaneous_qi_source", "existing_month_rule"] | None = (
        None
    )
    witnesses: Annotated[list[MonthUseWitness] | None, FULL_FACT] = None
    source: Annotated[MonthUseSource | None, FULL_FACT] = None
    formation_status: Literal["not_adjudicated"] | None = None
    scope: str | None = None


class MonthUseMatch(PartialOutput):
    status: Annotated[
        Literal["matched", "requires_identity_adjudication", "not_observed"] | None,
        FULL_FACT,
    ] = None
    witness_ids: Annotated[list[str] | None, FULL_FACT] = None
    pending_witness_ids: Annotated[list[str] | None, FULL_FACT] = None

    @model_validator(mode="after")
    def preserve_match_identity(self) -> "MonthUseMatch":
        if self.status == "matched" and self.witness_ids == []:
            raise ValueError("月用资格matched须有同次见证，不以旧单锚补空")
        else:
            pass
        if (
            self.status == "requires_identity_adjudication"
            and self.pending_witness_ids == []
        ):
            raise ValueError("具体身份待判须保实际未决见证")
        else:
            pass
        return self

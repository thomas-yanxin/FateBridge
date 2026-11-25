"""Known month-duty facts; documentary durations never select an effective duty."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_month_use import MonthUseResolution
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
Pillar = Literal["year", "month", "day", "hour"]


def coherent_months(months: list[str]) -> None:
    if len(set(months)) > 1:
        raise ValueError("同次月令、原文分日与书影观察不能混用不同月支")
    else:
        pass


class DutyHiddenPosition(PartialOutput):
    pillar: Pillar | None = None
    branch: Branch | None = None
    hidden_rank: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="after")
    def possible_rank(self) -> "DutyHiddenPosition":
        if self.branch is not None and self.hidden_rank is not None:
            if self.hidden_rank >= len(BRANCH_HIDDEN_STEMS[self.branch]):
                raise ValueError("分日文献的藏干观察不能超出实际支中目录")
            else:
                pass
        else:
            pass
        return self


class DutyClaim(PartialOutput):
    source_name: str | None = None
    canonical_stem: Stem | None = None
    days: int | None = Field(default=None, ge=0)
    visible_positions: list[Pillar] | None = None
    hidden_positions: list[DutyHiddenPosition] | None = None

    @model_validator(mode="after")
    def preserve_identity(self) -> "DutyClaim":
        if "canonical_stem" in self.model_fields_set and self.canonical_stem is None:
            if self.visible_positions is not None or self.hidden_positions is not None:
                raise ValueError(
                    "未指认的司事字不能伪作已核对的透藏观察，空列表也不是未知"
                )
            else:
                pass
        else:
            pass
        for position in self.hidden_positions or []:
            if not any(
                (position.branch is None or position.branch == branch)
                and (position.hidden_rank is None or position.hidden_rank == rank)
                and (self.canonical_stem is None or self.canonical_stem == stem)
                for branch, stems in BRANCH_HIDDEN_STEMS.items()
                for rank, stem in enumerate(stems)
            ):
                raise ValueError("分日文献所指天干与已给藏干位置矛盾；不能增造物理根")
            else:
                pass
        return self


class DutyDurationLayer(PartialOutput):
    profile_id: str | None = None
    month_branch: Branch | None = None
    normalized_month_branch: Branch | None = None
    claims: list[DutyClaim] | None = None
    computed_literal_duration_sum: int | None = Field(default=None, ge=0)
    equals_nominal_thirty_days: bool | None = None
    chronological_order_adjudicated: Literal[False] | None = None
    selected_duty_stem: None = None
    calendar_mapping_status: Literal["not_adopted"] | None = None
    source_stems_outside_month_hidden_catalog: list[Stem] | None = None

    def known_months(self) -> list[str]:
        result: list[str] = [
            m
            for m in (self.month_branch, self.normalized_month_branch)
            if m is not None
        ]
        for claim in self.claims or []:
            result.extend(
                p.branch
                for p in claim.hidden_positions or []
                if p.pillar == "month" and p.branch is not None
            )
        return result

    def check_catalog(self, branch: str) -> None:
        if (
            self.source_stems_outside_month_hidden_catalog is None
            or self.claims is None
        ):
            return
        else:
            pass
        if not all("canonical_stem" in c.model_fields_set for c in self.claims):
            return
        else:
            pass
        expected = list(
            dict.fromkeys(
                c.canonical_stem
                for c in self.claims
                if c.canonical_stem is not None
                and c.canonical_stem not in BRANCH_HIDDEN_STEMS[branch]
            )
        )
        if self.source_stems_outside_month_hidden_catalog != expected:
            raise ValueError(
                "表中目录外天干必须忠于已给身份与月支，不能把分日记载改作藏干"
            )
        else:
            pass

    @model_validator(mode="after")
    def preserve_literal_arithmetic(self) -> "DutyDurationLayer":
        months = self.known_months()
        coherent_months(months)
        total = self.computed_literal_duration_sum
        if self.claims is not None and all(c.days is not None for c in self.claims):
            actual = sum(c.days for c in self.claims if c.days is not None)
            if total is not None and total != actual:
                raise ValueError("分日合计必须沿用已给字面日数，不能凑成三十日")
            else:
                pass
            total = actual
        else:
            pass
        if total is not None and self.equals_nominal_thirty_days is not None:
            if self.equals_nominal_thirty_days != (total == 30):
                raise ValueError("三十日比较标记必须忠于实际字面合计")
            else:
                pass
        else:
            pass
        if months:
            self.check_catalog(months[0])
        else:
            pass
        return self


class DutyAnnualArithmetic(PartialOutput):
    computed_literal_sum: int | None = Field(default=None, ge=0)
    stated_total: int | None = Field(default=None, ge=0)
    stated_total_days: int | None = Field(default=None, ge=0)
    matches: bool | None = None
    matches_stated_total: bool | None = None

    @model_validator(mode="after")
    def preserve_disagreement(self) -> "DutyAnnualArithmetic":
        stated = [
            n for n in (self.stated_total, self.stated_total_days) if n is not None
        ]
        if len(set(stated)) > 1:
            raise ValueError("同一字面年合计不能拼接不同所述总数")
        else:
            pass
        if stated and self.computed_literal_sum is not None:
            for flag in (self.matches, self.matches_stated_total):
                if flag is not None and flag != (
                    self.computed_literal_sum == stated[0]
                ):
                    raise ValueError("文献算术矛盾必须保留，不能宣称不等总数相合")
                else:
                    pass
        else:
            pass
        return self


class DutyIdentityContext(PartialOutput):
    month_branch: Branch | None = None


class DutyScannedWitness(PartialOutput):
    month_branch: Branch | None = None
    duration_source_layers: list[DutyDurationLayer] | None = None
    annual_duration_arithmetic: DutyAnnualArithmetic | None = None
    cross_chapter_identities: DutyIdentityContext | None = None
    calendar_mapping_status: Literal["not_adopted"] | None = None
    selected_duty_stem: None = None
    effective_command_status: Literal["not_adjudicated"] | None = None
    calculation_effect: Literal["none"] | None = None

    def known_months(self) -> list[str]:
        result: list[str] = [self.month_branch] if self.month_branch is not None else []
        if (
            self.cross_chapter_identities is not None
            and self.cross_chapter_identities.month_branch is not None
        ):
            result.append(self.cross_chapter_identities.month_branch)
        else:
            pass
        for layer in self.duration_source_layers or []:
            result.extend(layer.known_months())
        return result

    @model_validator(mode="after")
    def coherent_witness(self) -> "DutyScannedWitness":
        months = self.known_months()
        coherent_months(months)
        if months:
            for layer in self.duration_source_layers or []:
                layer.check_catalog(months[0])
        else:
            pass
        return self


class MonthDutySourceReference(PartialOutput):
    month_branch: Branch | None = None
    conventional_month_hidden_stems: list[Stem] | None = None
    duration_source_layers: list[DutyDurationLayer] | None = None
    annual_duration_arithmetic: DutyAnnualArithmetic | None = None
    scanned_witness: DutyScannedWitness | None = None
    effective_command_status: Literal["not_adjudicated"] | None = None
    calculation_effect: Literal["none"] | None = None

    def check_month(self, branch: str) -> None:
        if (
            self.conventional_month_hidden_stems is not None
            and self.conventional_month_hidden_stems
            != list(BRANCH_HIDDEN_STEMS[branch])
        ):
            raise ValueError("已给月支与常规藏干目录矛盾，缺少重复月支字段不消除矛盾")
        else:
            pass
        layers = list(self.duration_source_layers or [])
        if self.scanned_witness is not None:
            layers.extend(self.scanned_witness.duration_source_layers or [])
        else:
            pass
        for layer in layers:
            layer.check_catalog(branch)

    def known_months(self) -> list[str]:
        result: list[str] = [self.month_branch] if self.month_branch is not None else []
        for layer in self.duration_source_layers or []:
            result.extend(layer.known_months())
        if self.scanned_witness is not None:
            result.extend(self.scanned_witness.known_months())
        else:
            pass
        return result

    @model_validator(mode="after")
    def coherent_source(self) -> "MonthDutySourceReference":
        months = self.known_months()
        coherent_months(months)
        hidden = self.conventional_month_hidden_stems
        possible = (
            [BRANCH_HIDDEN_STEMS[months[0]]]
            if months
            else list(BRANCH_HIDDEN_STEMS.values())
        )
        if hidden is not None and not any(hidden == list(stems) for stems in possible):
            raise ValueError("常规月藏干目录不能从分日文献增补或替换")
        else:
            pass
        if months:
            self.check_month(months[0])
        else:
            pass
        return self


class IntraMonthDuty(PartialOutput):
    status: Literal["not_adjudicated"] | None = None
    selected_stem: None = None
    rule_profile: None = None
    source_reference: MonthDutySourceReference | None = None


class MonthCommand(PartialOutput):
    month_branch: Branch | None = None
    use_resolution: Annotated[MonthUseResolution | None, FULL_FACT] = None
    intra_month_duty: IntraMonthDuty | None = None

    def check_month(self, branch: str) -> None:
        if (
            self.intra_month_duty is not None
            and self.intra_month_duty.source_reference is not None
        ):
            self.intra_month_duty.source_reference.check_month(branch)
        else:
            pass

    def known_months(self) -> list[str]:
        result: list[str] = [self.month_branch] if self.month_branch is not None else []
        if (
            self.intra_month_duty is not None
            and self.intra_month_duty.source_reference is not None
        ):
            result.extend(self.intra_month_duty.source_reference.known_months())
        else:
            pass
        return result

    @model_validator(mode="after")
    def coherent_command(self) -> "MonthCommand":
        months = self.known_months()
        coherent_months(months)
        if months:
            self.check_month(months[0])
        else:
            pass
        return self

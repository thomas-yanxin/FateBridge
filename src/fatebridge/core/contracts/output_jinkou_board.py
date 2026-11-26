"""Jinkou course and supporting evidence."""

from pydantic import ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_jinkou_board_facts import (
    JinkouCombinations,
    JinkouInternalStrength,
    JinkouJue,
    JinkouMotion,
    JinkouOverview,
    JinkouRelations,
    JinkouRow,
    JinkouUseEvidence,
    LabelValue,
)
from fatebridge.core.contracts.output_jinkou_branch_stars import (
    JinkouBranchStars,
    align_branch_stars,
)
from fatebridge.core.contracts.output_jinkou_breaks import (
    JinkouBranchBreaks,
    align_branch_breaks,
)
from fatebridge.core.contracts.output_jinkou_definitions import (
    JinkouDefinitionEvidence,
    compare_present_definition_facts,
)
from fatebridge.core.contracts.output_jinkou_interactions import (
    JinkouPositionInteractions,
)
from fatebridge.core.contracts.output_jinkou_patterns import validate_pattern_anchors
from fatebridge.core.contracts.output_jinkou_qi_models import JinkouQiEvidence
from fatebridge.core.contracts.output_jinkou_relations import validate_relation_anchors
from fatebridge.core.contracts.output_jinkou_stems import JinkouStemRelations
from fatebridge.core.contracts.output_jinkou_strength import validate_strength_evidence
from fatebridge.core.contracts.output_liuren_board import (
    RenCalendarPolicy,
    RenRuleset,
    RenRuleTrace,
)
from fatebridge.core.contracts.output_ren_patterns import JinkouPatterns
from fatebridge.core.metaphysics.jinkou.patterns import definition_evidence


class JinkouCourse(PartialOutput):
    engine: str | None = None
    overview: JinkouOverview | None = None
    rows: list[JinkouRow] | None = None
    shensha: list[LabelValue] | None = None
    motions: list[JinkouMotion] | None = None
    internal_strength: JinkouInternalStrength | None = None
    qi_evidence: JinkouQiEvidence | None = None
    position_interactions: JinkouPositionInteractions | None = None
    stem_relations: JinkouStemRelations | None = None
    definition_evidence: JinkouDefinitionEvidence | None = None
    combinations: JinkouCombinations | None = None
    patterns: JinkouPatterns | None = None
    use_evidence: JinkouUseEvidence | None = None
    relations: JinkouRelations | None = None
    branch_stars: JinkouBranchStars | None = None
    branch_breaks: JinkouBranchBreaks | None = None
    calendar_policy: RenCalendarPolicy | None = None
    ruleset: RenRuleset | None = None
    rule_trace: list[RenRuleTrace] | None = None

    @model_validator(mode="after")
    def breaks_follow_this_course(self) -> "JinkouCourse":
        align_branch_breaks(self)
        return self

    @model_validator(mode="after")
    def relations_follow_this_course(self) -> "JinkouCourse":

        validate_relation_anchors(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def patterns_follow_this_course(self) -> "JinkouCourse":

        validate_pattern_anchors(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def stars_follow_this_board(self) -> "JinkouCourse":

        align_branch_stars(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def strength_and_use_follow_this_board(
        self, info: ValidationInfo
    ) -> "JinkouCourse":

        if not (info.context and info.context.get("full_result")):
            validate_strength_evidence(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def natal_relation_uses_this_general(self) -> "JinkouCourse":
        primary = (
            self.relations.si_jue.natal
            if self.relations is not None and self.relations.si_jue is not None
            else None
        )
        nodes = [primary] if primary is not None else []
        for trace in self.rule_trace or []:
            if trace.rule_id != "jinkou.jingben_relations" or trace.result is None:
                continue
            block = trace.result.get("si_jue")
            if not isinstance(block, dict) or "natal" not in block:
                continue
            traced = JinkouJue.model_validate(block).natal
            if traced is None:
                raise ValueError("将命大绝规则轨迹不可伪造为空")
            nodes.append(traced)
            if primary is not None:
                a = primary.model_dump(exclude_unset=True)
                b = traced.model_dump(exclude_unset=True)
                if any(a[k] != b[k] for k in a.keys() & b.keys()):
                    raise ValueError("将命大绝正文与同次规则轨迹不一致")
        row = next((r for r in self.rows or [] if r.label == "将神"), None)
        if row is not None and row.content is not None:
            for natal in nodes:
                if (
                    "left_branch" in natal.model_fields_set
                    and natal.left_branch != row.content
                ):
                    raise ValueError("将命大绝须使用同次四位的将神支")
        return self

    @model_validator(mode="after")
    def definition_facts_agree_with_positions(self) -> "JinkouCourse":
        if (
            self.definition_evidence is None
            or self.rows is None
            or self.overview is None
        ):
            return self
        if self.stem_relations is None or self.stem_relations.day_stem is None:
            return self
        if self.overview.is_diurnal is None:
            return self
        actual = self.definition_evidence
        if actual.hour_branch is None:
            return self
        # Only rebuild when all four raw row anchors are available. Projection
        # validation must not fabricate omitted data.
        rows = [r.model_dump(exclude_unset=True) for r in self.rows]
        needed = ("label", "content", "element")
        if len(rows) != 4 or any(any(k not in r for k in needed) for r in rows):
            return self
        if not rows[1].get("intrinsic_ganzhi"):
            return self

        expected = definition_evidence(
            day_stem=self.stem_relations.day_stem,
            hour_branch=actual.hour_branch,
            is_diurnal=self.overview.is_diurnal,
            rows=rows,
        )
        compare_present_definition_facts(
            actual.model_dump(exclude_unset=True), expected
        )
        return self

    @model_validator(mode="after")
    def stems_agree_with_four_positions(self) -> "JinkouCourse":
        if self.stem_relations is None or self.rows is None:
            return self
        by_label = {row.label: row for row in self.rows if row.label is not None}
        for label, node in (
            ("贵神", self.stem_relations.god),
            ("将神", self.stem_relations.general),
        ):
            row = by_label.get(label)
            if row is None or node is None:
                continue
            for node_field, row_field in (
                ("branch", "content"),
                ("name", "shenjiang"),
                ("dun_stem", "dun_stem"),
                ("branch_element", "element"),
                ("branch_xun_kong", "xun_kong"),
                ("branch_si_da_kong", "si_da_kong"),
            ):
                a, b = getattr(node, node_field), getattr(row, row_field)
                if a is not None and b is not None and a != b:
                    raise ValueError("遁干证据与原四位的同次事实不一致")
        god = by_label.get("贵神")
        intrinsic = self.stem_relations.guishen_intrinsic_ganzhi
        if (
            god is not None
            and god.intrinsic_ganzhi is not None
            and intrinsic is not None
            and god.intrinsic_ganzhi != intrinsic
        ):
            raise ValueError("贵神固有干支与遁干证据不一致")
        return self

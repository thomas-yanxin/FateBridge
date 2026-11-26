"""Cross-object calculation facts, without inventing missing projected anchors."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_jinkou_branch_stars import (
    require_complete_branch_stars,
)
from fatebridge.core.contracts.output_jinkou_breaks import align_branch_breaks
from fatebridge.core.contracts.output_jinkou_definitions import (
    require_complete_chapter_witness,
)
from fatebridge.core.contracts.output_jinkou_natal_course import (
    require_complete_natal_course,
)
from fatebridge.core.contracts.output_jinkou_patterns import (
    require_complete_pattern_anchors,
)
from fatebridge.core.contracts.output_jinkou_relations import require_complete_relations
from fatebridge.core.contracts.output_jinkou_strength import (
    require_complete_strength_evidence,
)
from fatebridge.core.contracts.output_liuren_branches import (
    require_complete_branch_relations,
)
from fatebridge.core.contracts.output_liuren_course_conditions import (
    require_complete_course_conditions,
)
from fatebridge.core.contracts.output_liuren_cross_harmony import (
    require_complete_cross_harmony,
)
from fatebridge.core.contracts.output_liuren_day_placements import (
    require_complete_day_placements,
)
from fatebridge.core.contracts.output_liuren_emptiness import require_complete_emptiness
from fatebridge.core.contracts.output_liuren_god_yin import require_complete_god_yin
from fatebridge.core.contracts.output_liuren_ordered_patterns import (
    require_complete_ordered_patterns,
)
from fatebridge.core.contracts.output_liuren_progression import (
    require_complete_progression,
)
from fatebridge.core.contracts.output_liuren_seasonal import require_complete_seasonal
from fatebridge.core.contracts.output_liuren_selection import validate_selection
from fatebridge.core.contracts.output_liuren_trine_seasonal import (
    require_complete_nominal_seasonal,
)
from fatebridge.core.contracts.output_ren_anchor_values import _get
from fatebridge.core.contracts.output_ren_jinkou_anchors import _jinkou
from fatebridge.core.contracts.output_ren_liuren_anchors import _liuren
from fatebridge.core.contracts.output_ren_term_dates import (
    require_complete_published_dates,
)

__all__ = [
    "RenAnchoredOutput",
    "require_complete_ren_anchors",
]


class RenAnchoredOutput(PartialOutput):
    @model_validator(mode="after")
    def shared_ren_calculation_anchors(self, info: ValidationInfo) -> RenAnchoredOutput:
        complete = bool(info.context and info.context.get("full_result"))
        pillars = _get(self, "four_pillars")
        board = _get(self, "liureng")
        sub = _get(self, "subresults", "liureng_gods")
        if sub is not None:
            subpillars = _get(sub, "four_pillars")
            _liuren(_get(sub, "liureng"), subpillars, complete=complete)
            if pillars is None:
                pillars = subpillars
        _liuren(board, pillars, _get(self, "runyear"), complete=complete)
        _jinkou(_get(self, "jinkou"), pillars, board)
        _jinkou(_get(self, "jinkou", "year_fate", "course"), pillars, board)
        _jinkou(
            _get(self, "jinkou", "natal_course", "course"),
            pillars,
            board,
        )
        return self


REN_ANCHOR_TOOLS = frozenset(
    {"jinkou", "liureng_gods", "liureng_runyear", "sanshiunited"}
)


def require_complete_ren_anchors(
    key: str, result: dict[str, Any], *, _year_course: bool = False
) -> None:
    """Only full service output: projection models deliberately stay partial."""
    if key not in REN_ANCHOR_TOOLS:
        return

    def require(obj: Any, paths: tuple[str, ...]) -> None:
        for path in paths:
            if _get(obj, *path.split(".")) is None:
                raise ValueError(f"完整六壬金口诀输出缺少计算依据：{path}")

    def pillars(obj: Any) -> None:
        for role in ("year", "month", "day", "hour"):
            require(obj, (role + ".stem", role + ".branch"))

    def liuren(obj: Any) -> None:

        require_complete_god_yin(obj)
        yin_roles = _get(obj, "god_yin", "year_fate_uppers")
        natal_earth = annual_earth = None
        if key == "liureng_runyear":
            for role in ("natal", "annual"):
                placement = _get(result, "runyear", "year_fate", role)
                if not isinstance(placement, dict) or "sky_branch" not in placement:
                    raise ValueError("完整类神阴神须保留同次年命上神及可空年命事实")
                if yin_roles[role] != placement["sky_branch"]:
                    raise ValueError("完整类神阴神不能替换同次年命上神")
            natal_earth = _get(result, "runyear", "year_fate", "natal", "earth_branch")
            annual_earth = _get(
                result, "runyear", "year_fate", "annual", "earth_branch"
            )
        elif yin_roles != {"natal": None, "annual": None}:
            raise ValueError("未提供六壬年命计算的入口不能给阴神编造年命上神")

        require_complete_seasonal(obj)

        require_complete_nominal_seasonal(obj)

        require_complete_published_dates(_get(obj, "calendar_policy"))

        require_complete_ordered_patterns(obj)
        require_complete_course_conditions(obj)
        require_complete_day_placements(obj)
        require_complete_cross_harmony(obj)
        require_complete_progression(obj)
        require_complete_branch_relations(obj)
        require_complete_emptiness(obj, natal=natal_earth, annual=annual_earth)
        require(
            obj,
            (
                "calendar_policy.effective_day_ganzhi",
                "month_general.branch",
                "xun_head",
                "kongwang",
                "life_stages.day_stem",
                "auxiliary_stars.day_ganzhi",
                "auxiliary_stars.month_building_branch",
                "transmission_relations.day_ganzhi",
                "transmission_relations.rows",
                "transmission_relations.rules",
                "transmission_relations.trines",
                "meta.guiren_profile",
                "meta.is_diurnal",
                "meta.diurnal_evidence.hour_branch",
            ),
        )

        validate_selection(obj, complete=True)

    if not _year_course:
        board = _get(result, "liureng")
        if key == "sanshiunited":
            sub = _get(result, "subresults", "liureng_gods")
            pillars(_get(sub, "four_pillars"))
            sub_board = _get(sub, "liureng")
            if sub_board is not None and sub_board is not board:
                liuren(sub_board)
        else:
            pillars(_get(result, "four_pillars"))
        liuren(board)
    if key == "liureng_runyear":
        require(result, ("runyear.year_fate.day_ganzhi",))
    if key == "jinkou":

        align_branch_breaks(result["jinkou"], complete=True)

        require_complete_published_dates(result["jinkou"]["calendar_policy"])

        require_complete_strength_evidence(result["jinkou"])

        require_complete_pattern_anchors(result["jinkou"])

        require_complete_chapter_witness(result["jinkou"])

        require_complete_branch_stars(result["jinkou"])

        require_complete_relations(result["jinkou"])
        require(
            result,
            (
                "jinkou.calendar_policy.effective_day_ganzhi",
                "jinkou.stem_relations.day_stem",
                "jinkou.definition_evidence.day_stem",
                "jinkou.definition_evidence.hour_branch",
                "jinkou.definition_evidence.entries",
                "jinkou.definition_evidence.cross_generation_hypotheses",
                "jinkou.definition_evidence.day_night_candidates",
                "jinkou.definition_evidence.ding_routes",
                "jinkou.overview.di_fen",
                "jinkou.overview.month_general.branch",
                "jinkou.overview.is_diurnal",
                "jinkou.overview.diurnal_evidence.hour_branch",
                "jinkou.rows",
                "jinkou.relations.si_jue.natal.left_branch",
                "jinkou.relations.si_jue.natal.status",
                "jinkou.relations.si_jue.natal.input_source",
                "jinkou.relations.si_jue.unavailable",
            ),
        )
        natal = _get(result, "jinkou", "relations", "si_jue", "natal")
        if not isinstance(natal, dict) or any(
            key not in natal for key in ("right_branch", "matched", "element")
        ):
            raise ValueError("完整金口诀须保留大绝的本命支及可空判定")
        traces = [
            t
            for t in _get(result, "jinkou", "rule_trace") or []
            if _get(t, "rule_id") == "jinkou.jingben_relations"
        ]
        traced = (
            _get(traces[0], "result", "si_jue", "natal") if len(traces) == 1 else None
        )
        if not isinstance(traced, dict) or any(
            key not in traced
            for key in (
                "left_branch",
                "right_branch",
                "matched",
                "element",
                "status",
                "input_source",
            )
        ):
            raise ValueError("完整金口诀须保留唯一的将命大绝规则轨迹")
        if not _year_course:

            require_complete_natal_course(result["jinkou"])
            natal_child = _get(result, "jinkou", "natal_course", "course")
            if natal_child is not None:
                require_complete_ren_anchors(
                    key, dict(result, jinkou=natal_child), _year_course=True
                )
            annual = _get(result, "jinkou", "year_fate")
            if not isinstance(annual, dict) or any(
                name not in annual
                for name in (
                    "method_id",
                    "status",
                    "birth_year_ganzhi",
                    "birth_xun",
                    "gender",
                    "age_ordinal",
                    "age_basis",
                    "course_basis",
                    "course_ground_is_observed",
                    "start_ganzhi",
                    "direction",
                    "ganzhi",
                    "branch",
                    "missing_inputs",
                    "natal_branch",
                    "natal_branch_source",
                    "age_boundary_classically_verified",
                    "birth_year_calendar_boundary_verified",
                    "comprehensive_year_fate_adjudicated",
                    "source_section",
                    "original_pdf_pages",
                    "relation_adjudication",
                    "relation_note",
                    "scope",
                    "course",
                )
            ):
                raise ValueError("完整金口诀须保留京本行年资料及可空另课")
            if annual["course"] is not None:
                require(annual["course"], ("overview.di_fen_source",))
                child = dict(result, jinkou=annual["course"])
                require_complete_ren_anchors(key, child, _year_course=True)

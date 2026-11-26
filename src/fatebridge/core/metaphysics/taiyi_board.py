"""Assemble the shared Taiyi board and its calendar summary."""

from typing import Any

from fatebridge.core.metaphysics.taiyi_conditions import five_general_conditions
from fatebridge.core.metaphysics.taiyi_counts import count_assessment
from fatebridge.core.metaphysics.taiyi_cycles import counter_cycles
from fatebridge.core.metaphysics.taiyi_elemental_relations import (
    elemental_guan_assessment,
)
from fatebridge.core.metaphysics.taiyi_enclosures import (
    enclosure_assessment,
    principal_enclosures,
)
from fatebridge.core.metaphysics.taiyi_eye_relations import eye_general_relations
from fatebridge.core.metaphysics.taiyi_geometry import PALACES, RING, SOURCES
from fatebridge.core.metaphysics.taiyi_oppositions import (
    opposition_assessment,
    opposition_summary,
)
from fatebridge.core.metaphysics.taiyi_shiji import shiji_derivation
from fatebridge.core.metaphysics.taiyi_source_alignment import count_source_assessment
from fatebridge.core.metaphysics.taiyi_victory_matrix import victory_matrix_assessment

DISPLAY_ORDER = "巽巳午未坤申酉戌乾亥子丑艮寅卯辰"


def structural_patterns(core: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate vol. 3's spatial conditions without inventing event outcomes.

    The individual reading of 囚 is independently supported by vol. 3 ju 1's
    主参一乾(囚); requiring all four generals to be with Taiyi would make the
    rule impossible away from center five. 上目无迫 is explicitly respected.
    """
    taiyi = core["taiyi_palace"]
    center = RING.index(taiyi)
    opposite = RING[(center + 8) % 16]
    positions = {"wenchang_palace": core["wenchang_palace"], "shiji": core["shiji"]}
    labels = {
        "wenchang_palace": "文昌",
        "shiji": "始击",
        "main_general": "主大将",
        "main_vice_general": "主参将",
        "guest_general": "客大将",
        "guest_vice_general": "客参将",
    }
    for field in (
        "main_general",
        "main_vice_general",
        "guest_general",
        "guest_vice_general",
    ):
        positions[field] = PALACES[core[field]]
    result: list[dict[str, Any]] = []

    def fact(field: str) -> dict[str, Any]:
        return {
            "field": (
                field
                if field in {"wenchang_palace", "taiyi_palace"}
                else "core_board." + field
            ),
            "value": core[field],
        }

    def add(
        name: str,
        subject: str,
        meaning: str,
        section: str,
        *,
        other: str = "taiyi_palace",
        variant: str | None = None,
    ) -> None:
        result.append(
            {
                "name": name,
                "subject": labels[subject],
                "variant": variant or name,
                "basis": [fact(subject), fact(other)],
                "traditional_meaning": meaning,
                "source": SOURCES["3"] + "#" + section,
                "scope": "原典空间条件；尚需全盘条件，不能单条推出事件成败",
            }
        )

    for field, palace in positions.items():
        if palace == taiyi:
            if field == "shiji":
                add("掩", field, "始击与太乙同宫", "推掩法")
            else:
                add("囚", field, f"{labels[field]}与太乙同宫", "推囚法")
        if palace == opposite:
            if field == "wenchang_palace":
                add("对", field, "文昌与太乙对宫", "推對法")
            elif field in {"shiji", "guest_general", "guest_vice_general"}:
                add("格", field, f"{labels[field]}与太乙对宫", "推格法")
        if palace not in RING:
            continue  # Center has no ring bearing; do not manufacture one.
        distance = (RING.index(palace) - center) % 16
        if distance not in (1, 2, 14, 15):
            continue
        forward = distance in (1, 2)
        adjacent_spirit = distance in (1, 15)
        if field == "shiji":
            variant = (
                ("前击" if forward else "后击")
                if adjacent_spirit
                else ("外宫击" if forward else "内宫击")
            )
            add(
                "击",
                field,
                f"始击在太乙{'前' if forward else '后'}一{'辰' if adjacent_spirit else '宫'}",
                "推撃法",
                variant=variant,
            )
        else:
            variant = ("外" if forward else "内") + (
                "辰迫" if adjacent_spirit else "宫迫"
            )
            add(
                "迫",
                field,
                f"{labels[field]}在太乙{'前' if forward else '后'}一{'辰' if adjacent_spirit else '宫'}",
                "推迫法",
                variant=variant,
            )
    for main in ("main_general", "main_vice_general"):
        for guest in ("guest_general", "guest_vice_general"):
            if positions[main] == positions[guest]:
                add(
                    "关",
                    main,
                    f"{labels[main]}与{labels[guest]}同宫",
                    "推闗法",
                    other=guest,
                )

    result.extend(principal_enclosures(core))
    # Append so all previously emitted relation indices remain stable.
    result.extend(eye_general_relations(core))
    return result


def assemble_board(
    core: dict[str, Any], *, calculation_mode: str | None = None
) -> dict[str, Any]:
    """Place every supported marker and attach same-core explanations."""

    marks: dict[str, list[str]] = {palace: [] for palace in DISPLAY_ORDER + "中"}
    placements = {
        "太乙": core["taiyi_palace"],
        "文昌": core["wenchang_palace"],
        "始击": core["shiji"],
        core.get("ruler_label", "太歲"): (
            core["ruler_branch"] if "ruler_branch" in core else core["suijun"]
        ),
        "合神": core["heshen"],
        "計神": core["jishen"],
    }
    for label, field in (
        ("主大", "main_general"),
        ("主參", "main_vice_general"),
        ("客大", "guest_general"),
        ("客參", "guest_vice_general"),
    ):
        placements[label] = PALACES[core[field]]
    for label, palace in placements.items():
        marks[palace].append(label)
    patterns = structural_patterns(core)
    oppositions = opposition_assessment(core)
    opposition_digest = opposition_summary(oppositions)
    enclosures = enclosure_assessment(patterns, core=core)
    source_alignment = count_source_assessment(core)
    source_warning = (
        {"source_table_warning": source_alignment["summary"]}
        if source_alignment["status"] != "not_assessed"
        and source_alignment["summary"]["status"] == "differences_unadjudicated"
        else {}
    )
    return {
        "engine": "fatebridge-offline",
        "counter_cycles": counter_cycles(core, calculation_mode=calculation_mode),
        "taiyi_palace": core["taiyi_palace"],
        "wenchang_palace": core["wenchang_palace"],
        "core_board": {
            **{
                key: value
                for key, value in core.items()
                if key not in {"taiyi_palace", "wenchang_palace", "count_trace"}
            },
            "taiyi_position": f"太乙在{core['taiyi_palace']}宫（{core['taiyi_number']}）",
            "wenchang_position": f"文昌在{core['wenchang_palace']}宫",
        },
        "palace_marks": [
            {"palace": palace, "markers": sorted(marks[palace])}
            for palace in DISPLAY_ORDER
        ],
        "center_marks": {"palace": "中", "markers": sorted(marks["中"])},
        "rule_trace": core["count_trace"],
        "patterns": patterns,
        "enclosure_assessment": enclosures,
        "opposition_assessment": oppositions,
        "condition_assessment": five_general_conditions(patterns, core=core),
        "count_assessment": count_assessment(core),
        "count_source_assessment": source_alignment,
        "shiji_derivation": shiji_derivation(core),
        "victory_matrix_assessment": victory_matrix_assessment(
            core, calculation_mode=calculation_mode
        ),
        "elemental_guan_assessment": elemental_guan_assessment(
            core, patterns, calculation_mode=calculation_mode
        ),
        "pattern_summary": {
            **source_warning,
            "pair_enclosures": len(enclosures["two_general_enclosure"]["patterns"]),
            "main_oppositions": opposition_digest["main_oppositions"],
            "opposition_source_disagreements": opposition_digest[
                "source_disagreements"
            ],
            "conditions": [
                {key: p[key] for key in ("name", "subject", "variant")}
                for p in patterns
            ],
            "source": SOURCES["3"],
            "scope": "仅所核空间条件，含将目关掩；主方对宫几何及格/对异称另见opposition_assessment。逐项事实与版本范围保留，不单条断成败。",
        },
    }


def calendar_summary(board: dict[str, Any]) -> dict[str, Any]:
    """A compact first-read view; full adapter evidence stays in calendar_rules."""
    calendar = board["calendar_rules"]
    mode = calendar.get("calculation_mode", "year")
    common = {
        "calculation_mode": mode,
        "civil_datetime": calendar["civil_datetime"],
        "timezone": calendar["timezone"],
    }
    if mode == "year":
        used_lunar = calendar.get("historical_calendar") or calendar.get(
            "civil_lunar_calendar"
        )
        return {
            **common,
            "year": calendar["year"],
            "year_boundary": calendar["year_boundary"],
            "year_boundary_status": calendar["year_boundary_status"],
            **({"used_lunar_date": used_lunar["display"]} if used_lunar else {}),
            **(
                {"year_profile": calendar["year_profile"]}
                if "year_profile" in calendar
                else {}
            ),
        }
    return {
        **common,
        **(
            {
                "anchor_ephemeris_model": board["solar_anchors"]["boundary"][
                    "ephemeris_model"
                ],
                **(
                    {
                        "winter_anchor_ephemeris_model": board["solar_anchors"][
                            "winter_origin"
                        ]["ephemeris_model"]
                    }
                    if "winter_origin" in board["solar_anchors"]
                    else {}
                ),
            }
            if board.get("solar_anchors")
            else {}
        ),
        **{
            key: calendar[key]
            for key in (
                "anchor_name",
                "anchor_utc",
                "counter",
                "clock_basis",
                "hour_profile",
                "month_profile",
                "day_profile",
                "input_calendar",
            )
            if key in calendar
        },
        "convention": (
            calendar["modern_conventions"]
            if mode in {"hour", "day"} or calendar.get("month_origin")
            else calendar["leap_month_policy"]
        ),
    }

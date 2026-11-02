"""Compare calculation traces with literal source clauses, keeping every dispute.

An agreement count certifies neither a complete classical book nor predictive
efficacy. In particular, this evaluator never edits a source to fit an engine.
"""

from typing import Any, cast

from fatebridge.core.fengshui.bazhai import sectors
from fatebridge.core.fengshui.bazhai_interpretation import palace_star_relationship
from fatebridge.core.fengshui.directions import rule_data
from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import xuankong_natal

MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
TRIGRAM_DIRECTIONS = dict(zip("坎艮震巽离坤兑乾", "N NE E SE S SW W NW".split()))
STAR_CODES = dict(
    zip("六天五祸绝延生", ("六煞", "天医", "五鬼", "祸害", "绝命", "延年", "生气"))
)


def audit_city_gate_reference(reference: dict[str, Any]) -> dict[str, Any]:
    """All selected printed clauses, including unused/negative period cases."""
    periods = reference["zi_gate_nine_periods"]
    geometry = reference["same_yuan_gates"]
    cases = reference["specific_numeric_cases"]
    if any(
        not {
            "period",
            "facing",
            "gate",
            "seed",
            "mapped_mountain",
            "eligible",
        }.issubset(c)
        or c["facing"] != "乾"
        or c["gate"] != "子"
        or type(c["eligible"]) is not bool
        for c in periods
    ) or any("eligible" not in c or type(c["eligible"]) is not bool for c in cases):
        raise ValueError(
            "Required original clause fields may not be omitted or coerced"
        )
    if any(
        (c["period"], c["facing"], c["gate"]) == (9, "酉", "乾")
        and not {"seed", "mapped_mountain"}.issubset(c)
        for c in cases
    ):
        raise ValueError("The printed nine-period Qian-gate fields are required")
    if len(periods) != 9 or {c["period"] for c in periods} != set(range(1, 10)):
        raise ValueError("All nine unique printed period clauses are required")
    if len(geometry) != 8 or {c["facing"] for c in geometry} != set("子午卯酉乾巽丙丁"):
        raise ValueError("All eight unique printed same-yuan examples are required")
    if len(cases) != 3 or {(c["period"], c["facing"], c["gate"]) for c in cases} != {
        (9, "酉", "乾"),
        (2, "午", "巽"),
        (3, "午", "巽"),
    }:
        raise ValueError("All three specific numeric source cases are required")

    def gates(facing: str, period: int) -> list[dict[str, Any]]:
        request = XuankongRequest.model_validate(
            {
                "house": {
                    "facing_degrees": MOUNTAINS.index(facing) * 15,
                    "north_reference": "magnetic",
                },
                "city_gate": {
                    "reference_period_number": period,
                    "period_evidence": "Independent printed numeric clause audit",
                },
            }
        )
        return cast(
            list[dict[str, Any]],
            xuankong_natal(request)["city_gate_analysis"]["candidates"][0]["gates"],
        )

    disagreements = []
    for case in periods + cases:
        actual = next(
            g
            for g in gates(case["facing"], case["period"])
            if g["mountain"]["name"] == case["gate"]
        )
        values = {
            "eligible": actual["reference_star_reaches_gate_by_reverse_flight"],
            "seed": actual["seed_star_number"],
            "mapped_mountain": actual["mapped_mountain"],
        }
        if any(case[k] != v for k, v in values.items() if k in case):
            disagreements.append({"source_case": case, "actual": values})
    for case in geometry:
        actual_gates = [g["mountain"]["name"] for g in gates(case["facing"], 2)]
        if len(case["gates"]) != 2 or set(actual_gates) != set(case["gates"]):
            disagreements.append({"source_case": case, "actual": actual_gates})
    return {
        "checked": 20,
        "matched": 20 - len(disagreements),
        "disagreements": disagreements,
        "scoped_acceptance_passed": not disagreements,
        "scope": "selected_printed_numeric_clauses_not_whole_book_or_complete_physical_site",
        "whole_book_conformity_established": False,
        "real_world_prediction": "not_tested",
    }


def audit_bazhai_depth(
    transformations: dict[str, Any], elements: dict[str, Any]
) -> dict[str, Any]:
    """Check complete literal pairs and all five-by-five directed relations."""
    cases = transformations["cases"]
    expected_pairs = {
        (a, b) for a in TRIGRAM_DIRECTIONS for b in TRIGRAM_DIRECTIONS if a != b
    }
    if len(cases) != 56 or {(c["base"], c["target"]) for c in cases} != expected_pairs:
        raise ValueError("All 56 unique non-self trigram pairs are required")
    names = elements["elements"]
    rows = elements["palace_by_star_labels"]
    if (
        len(names) != 5
        or set(names) != set("木火土金水")
        or len(rows) != 5
        or any(len(row) != 5 for row in rows)
    ):
        raise ValueError(
            "The complete five-by-five directed element matrix is required"
        )
    errors = []
    for case in cases:
        entry = sectors(case["base"], "source-audit", "source")[
            TRIGRAM_DIRECTIONS[case["target"]]
        ]
        if (
            entry["star"]["name"] != case["star_name"]
            or entry["you_nian_trace"]["operation_count"] != case["operation_count"]
        ):
            errors.append(
                {
                    "kind": "you_nian_transformation",
                    "source_case": case,
                    "actual_star": entry["star"]["name"],
                    "actual_trace": entry["you_nian_trace"],
                }
            )
    for i, palace in enumerate(names):
        for j, star in enumerate(names):
            actual = palace_star_relationship(palace, "element-audit", star)[
                "traditional_label"
            ]
            if actual != rows[i][j]:
                errors.append(
                    {
                        "kind": "directed_element_relation",
                        "palace_element": palace,
                        "star_element": star,
                        "expected": rows[i][j],
                        "actual": actual,
                    }
                )
    stars = {
        star["name"]: star["element"] for star in rule_data("bazhai_stars").values()
    }
    if len(elements["selected_star_elements"]) != 8 or set(
        elements["selected_star_elements"]
    ) != set(stars):
        raise ValueError("The complete eight-star source table is required")
    for name, expected in elements["selected_star_elements"].items():
        if stars[name] != expected:
            errors.append(
                {
                    "kind": "star_element",
                    "star_name": name,
                    "expected": expected,
                    "actual": stars[name],
                }
            )
    return {
        "audit_id": "bazhai_literal_depth_v1",
        "checked_transformation_pairs": 56,
        "checked_directed_element_pairs": 25,
        "checked_star_elements": 8,
        "disagreements": errors,
        "scoped_acceptance_passed": not errors,
        "whole_book_conformity_established": False,
        "real_world_prediction": "not_tested",
        "scope": "仅累计变爻、选定八星五行表及有向生克，不认证门主灶完整结构、所有伏位语境或现实吉凶。",
    }


def audit_classical_reference(
    reference: dict[str, Any], facsimile: dict[str, Any] | None = None
) -> dict[str, Any]:
    disagreements = []
    counts = {
        "bazhai": {"checked": 0, "matched": 0},
        "xuankong": {"checked": 0, "matched": 0},
    }
    shen_keys = [
        (row["period"], row["facing_mountain"]) for row in reference["shen_cases"]
    ]
    if len(shen_keys) != 216 or set(shen_keys) != {
        (p, m) for p in range(1, 10) for m in MOUNTAINS
    }:
        raise ValueError(
            "Source audit requires every one of the 216 unique mountain-period pairs"
        )
    verses = reference["you_nian_verses"]
    if len(verses) != 8 or {v["base"] for v in verses} != set(TRIGRAM_DIRECTIONS):
        raise ValueError("Source audit requires all eight distinct You Nian verses")
    for verse in verses:
        base = verse["base"]
        if (
            len(verse["destinations"]) != 7
            or len(verse["star_codes"]) != 7
            or set(verse["destinations"]) != set(TRIGRAM_DIRECTIONS) - {base}
            or set(verse["star_codes"]) != set(STAR_CODES)
        ):
            raise ValueError("Malformed You Nian verse; truncated sources cannot pass")
        expected = {
            base: "伏位",
            **{
                d: STAR_CODES[c]
                for d, c in zip(verse["destinations"], verse["star_codes"])
            },
        }
        chart = sectors(base, "source-audit", "literal_you_nian_verse")
        for trigram, star in expected.items():
            direction = TRIGRAM_DIRECTIONS[trigram]
            actual = chart[direction]["star"]["name"]
            counts["bazhai"]["checked"] += 1
            counts["bazhai"]["matched"] += actual == star
            if actual != star:
                disagreements.append(
                    dict(
                        method="bazhai",
                        base=base,
                        direction=direction,
                        expected=star,
                        actual=actual,
                    )
                )
    for row in reference["shen_cases"]:
        request = XuankongRequest.model_validate(
            {
                "house": {
                    "facing_degrees": 15 * MOUNTAINS.index(row["facing_mountain"]),
                    "north_reference": "magnetic",
                },
                "period": {
                    "basis": "expert_confirmed",
                    "period_number": row["period"],
                    "evidence": "Literal source clause audit; synthetic house",
                },
            }
        )
        chart = xuankong_natal(request)["chart"]
        expected = {
            key: row[key]
            for key in (
                "mountain_seed",
                "facing_seed",
                "mountain_flight",
                "facing_flight",
            )
        }
        actual = {
            f"{role}_{field}": chart["trace"][role][
                "seed_star_number" if field == "seed" else "flight"
            ]
            for role in ("mountain", "facing")
            for field in ("seed", "flight")
        }
        counts["xuankong"]["checked"] += 1
        counts["xuankong"]["matched"] += actual == expected
        if actual != expected:
            disagreements.append(
                dict(
                    method="xuankong",
                    period=row["period"],
                    sitting_mountain=row["sitting_mountain"],
                    facing_mountain=row["facing_mountain"],
                    literal_clause=row["literal_clause"],
                    expected=expected,
                    actual=actual,
                )
            )
    checks = []
    if facsimile is not None:
        seen = set()
        for clause in facsimile["cases"]:
            key = (
                clause["period"],
                clause["sitting_mountain"],
                clause["facing_mountain"],
            )
            if key in seen:
                raise ValueError("Duplicate facsimile spot check")
            seen.add(key)
            dispute = next(
                (
                    r
                    for r in disagreements
                    if r["method"] == "xuankong"
                    and (r["period"], r["sitting_mountain"], r["facing_mountain"])
                    == key
                ),
                None,
            )
            if dispute is None:
                raise ValueError(
                    "Facsimile correction must identify a recorded transcription disagreement"
                )
            expected = {k: clause[k] for k in dispute["actual"]}
            check = {
                "period": key[0],
                "sitting_mountain": key[1],
                "facing_mountain": key[2],
                "pdf_page_one_based": clause["pdf_page_one_based"],
                "panel": clause["panel"],
                "literal_clause": clause["literal_clause"],
                "facsimile_expected": expected,
                "engine_matches_facsimile": expected == dispute["actual"],
            }
            dispute["facsimile_check"] = check
            checks.append(check)
    return {
        "audit_id": "fengshui_literal_source_audit_v1",
        "counts": counts,
        "disagreements": disagreements,
        "numeric_clause_acceptance_passed": not disagreements,
        "numeric_clause_gate_scope": "unaltered_web_transcription_only",
        "facsimile_spot_checks": checks,
        "unresolved_disagreement_count": sum(
            not r.get("facsimile_check", {}).get("engine_matches_facsimile", False)
            for r in disagreements
        ),
        "facsimile_source": (
            {k: v for k, v in facsimile.items() if k != "cases"}
            if facsimile is not None
            else None
        ),
        "whole_book_conformity_established": False,
        "original_print_collated": reference["original_print_collated"],
        "real_world_prediction": "not_tested",
        "authority_certified": False,
        "scope": "八宅64项游年关系及玄空216条下卦种子与顺逆；未核验整本、替卦、实际空间与现实结果。转录不一致保留原句，不预断原典或引擎孰误。",
        "sources": reference["sources"],
    }

"""Explicit classical counting rules, with source ambiguity retained."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from .divination import BAGUA_BY_NAME, BAGUA_BY_NUMBER, compose_meihua_hexagram
from .meihua import meihua_ruleset, meihua_stage_relations
from .meihua_tones import build_text_tone_basis
from .requests.meihua import MeihuaCasting

_ADAPTER = TypeAdapter(MeihuaCasting)
_NUMBERS = {name: number for number, name in BAGUA_BY_NUMBER.items()}
_CODE_NUMBERS = {
    "".join(map(str, BAGUA_BY_NAME[name]["lines"])): number
    for name, number in _NUMBERS.items()
}
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def explicit_ruleset(*, casting_method: str | None = None) -> dict[str, Any]:
    common = meihua_ruleset()
    extra = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/explicit-casts-v1.json"
        ).read_text(encoding="utf-8")
    )
    result = {
        **common,
        **extra,
        "sources": [*common["sources"], *extra.get("sources", [])],
        "rules": [
            *[
                r
                for r in common["rules"]
                if r["id"] not in {"time_seed", "calendar_policy"}
            ],
            *extra["rules"],
        ],
    }
    if casting_method == "observed_categories":
        from .meihua_observed import observed_category_profile

        selected = observed_category_profile()
        result.update(
            id=selected["id"],
            version=selected["version"],
            title=selected["title"],
            scope=selected["scope"],
            observation_mapping=selected,
        )
        result["sources"].append(
            {"id": "nlc1925_observed_categories", **selected["source"]}
        )
        result["rules"].append(
            {
                "id": "observed_categories",
                "source_id": "nlc1925_observed_categories",
                "kind": "selected_declared_category_and_direction_lookup",
                "quote": selected["source"]["formula"]["quote"],
                "statement": "只查已报五种物象及八方，保留来、往、所在关系，不从描述取象或自动反方；物卦与方位按先天卦序相加，加原时支数一次取爻。",
            }
        )
    return result


def cast_explicit_meihua(
    casting: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Never infer a method from a question or fill absent casting facts."""
    parameters = _ADAPTER.validate_python(casting).model_dump(mode="json")
    method = parameters["method"]
    hour = (
        _BRANCHES.index(parameters["hour_branch"]) + 1
        if "hour_branch" in parameters
        else 0
    )
    ignored: dict[str, Any] = {}
    alternate = None
    observation_basis = None
    if method == "lunar_time_added_count":
        year = _BRANCHES.index(parameters["year_branch"]) + 1
        upper = (
            year
            + parameters["lunar_month"]
            + parameters["lunar_day"]
            + parameters["added_count"]
        )
        lower = upper + hour
        total = lower
    elif method == "sound_groups":
        upper, lower = parameters["first_count"], parameters["second_count"]
        raw_sum, reduced_sum = (
            upper + lower + hour,
            (upper % 8 or 8) + (lower % 8 or 8) + hour,
        )
        total = raw_sum if parameters["line_sum_basis"] == "raw_counts" else reduced_sum
        alternate = (
            reduced_sum if parameters["line_sum_basis"] == "raw_counts" else raw_sum
        ) % 6 or 6
    elif method == "object_count":
        upper, lower = parameters["count"], hour
        raw_sum = upper + hour
        reduced_sum = (upper % 8 or 8) + hour
        total = raw_sum if parameters["line_sum_basis"] == "raw_counts" else reduced_sum
        alternate = (
            reduced_sum if parameters["line_sum_basis"] == "raw_counts" else raw_sum
        ) % 6 or 6
    elif method == "observed_categories":
        from .meihua_observed import resolve_reported_observation

        upper, lower, observation_basis = resolve_reported_observation(parameters)
        total = upper + lower + hour
    elif method == "observed_trigrams":
        upper, lower = (
            _NUMBERS[parameters["upper_trigram"]],
            _NUMBERS[parameters["lower_trigram"]],
        )
        total = upper + lower + hour
    elif method == "length_zhang_chi":
        upper, lower = parameters["zhang"], parameters["chi"]
        total = upper + lower
        if parameters["cun"] is not None:
            ignored["cun"] = parameters["cun"]
    elif method == "length_chi_cun":
        upper, lower = parameters["chi"], parameters["cun"]
        total = upper + lower + hour
        if parameters["fen"] is not None:
            ignored["fen"] = parameters["fen"]
    elif method in {"text_tones", "text_strokes"}:
        counts = parameters["tones" if method == "text_tones" else "strokes"]
        split = len(counts) // 2
        upper, lower = sum(counts[:split]), sum(counts[split:])
        total = upper + lower
    elif method == "single_character_strokes":
        upper, lower = parameters["left_strokes"], parameters["right_strokes"]
        total = parameters["total_strokes"]
    elif method == "text_count":
        upper = parameters["character_count"] // 2
        lower = parameters["character_count"] - upper
        raw_sum = upper + lower
        reduced_sum = (upper % 8 or 8) + (lower % 8 or 8)
        total = raw_sum if parameters["line_sum_basis"] == "raw_counts" else reduced_sum
        alternate = (
            reduced_sum if parameters["line_sum_basis"] == "raw_counts" else raw_sum
        ) % 6 or 6
    else:  # existing; the discriminated union rejects every other method.
        code = parameters["hexagram_code"]
        upper, lower = _CODE_NUMBERS[code[3:]], _CODE_NUMBERS[code[:3]]
        total = parameters["moving_line"]

    moving_line = total % 6 or 6
    seed: dict[str, Any] = {
        "casting_method": method,
        "upper_number": upper % 8 or 8,
        "lower_number": lower % 8 or 8,
        "moving_line": moving_line,
        "parameters": parameters,
        "ignored_components": ignored,
    }
    if "hour_branch" in parameters:
        seed["hour_branch"] = parameters["hour_branch"]
    if observation_basis is not None:
        seed["observation_basis"] = observation_basis
    if method == "text_tones":
        seed["text_tone_basis"] = build_text_tone_basis(parameters)
    if method == "text_count":
        facsimile = parameters["text_basis"] == "nlc1925_selected_span"
        seed["text_count_basis"] = {
            "text_basis": parameters["text_basis"],
            "selected_wording": "百餘字" if facsimile else "百字",
            "selected_source_id": "nlc_1925" if facsimile else "meihua-volume-1",
            "source_original_pdf_index": 17 if facsimile else None,
            "character_count": parameters["character_count"],
            "range_status": (
                "software_extension_exact_textual_extent_unadjudicated"
                if parameters["character_count"] > 100
                else "within_fixed_transcription_working_range"
            ),
            "exact_facsimile_upper_bound_adjudicated": False,
            "software_count_guard": 1_000_000,
            "line_sum_convention_uniquely_classical": False,
        }
    if method != "existing":
        seed.update(
            {"raw_upper_number": upper, "raw_lower_number": lower, "line_sum": total}
        )
    if alternate is not None:
        seed.update(
            {
                "line_sum_basis": parameters["line_sum_basis"],
                "alternate_moving_line": alternate,
                "count_boundary_status": (
                    "convention_changes_result"
                    if alternate != moving_line
                    else "conventions_agree_for_this_input"
                ),
            }
        )
    formulas = {
        "lunar_time_added_count": "upper_raw=year_branch_number+lunar_month+lunar_day+added_count; lower_raw=upper_raw+original_hour_number; line_sum=lower_raw; reduce trigrams modulo 8 and line modulo 6, zero maps to 8/6; do not add hour again",
        "object_count": "upper=count; lower=hour_number; line_sum=(raw count or reduced upper trigram number)+original hour_number; hour added once, never reduced to lower trigram number",
        "sound_groups": f"upper=first_count; lower=second_count; line_sum={parameters.get('line_sum_basis', '')}+hour_number",
        "observed_trigrams": "upper/lower=confirmed pre-heaven trigram numbers; line_sum=upper+lower+hour_number",
        "observed_categories": "upper=selected reported subject category; lower=selected reported compass side, preserving from/toward/at without inversion; line_sum=pre-heaven upper number+pre-heaven lower number+original hour number once; no Luo Shu number substitution",
        "length_zhang_chi": "upper=zhang; lower=chi; line_sum=zhang+chi; exclude cun; no hour added",
        "length_chi_cun": "upper=chi; lower=cun; line_sum=chi+cun+hour_number; exclude fen",
        "text_tones": "split characters floor(n/2)/ceil(n/2); sum supplied historical tones for each trigram; line_sum=all tones; no hour added",
        "text_strokes": "split characters floor(n/2)/ceil(n/2); sum actual glyph strokes for each trigram; line_sum=all strokes; no hour added",
        "single_character_strokes": "upper=left_strokes; lower=right_strokes; line_sum=total_strokes; no hour added",
        "text_count": "upper_raw=floor(character_count/2); lower_raw=ceil(character_count/2); line_sum=sum raw halves or their reduced trigram numbers as explicitly declared; no hour added; text_basis and exact source extent retained separately",
        "existing": "preserve existing hexagram and its supplied moving line; do not recast",
    }
    trace = [
        {
            "rule_id": method,
            "operation": formulas[method],
            "inputs": parameters,
            "result": {
                "raw_upper_number": upper,
                "raw_lower_number": lower,
                "hour_number_used": hour if "hour_branch" in parameters else None,
                "line_sum_or_supplied_line": total,
                "upper_number": seed["upper_number"],
                "lower_number": seed["lower_number"],
                "moving_line": moving_line,
                "ignored_components": ignored,
            },
        }
    ]
    variants: list[dict[str, Any]] = []
    if alternate is not None and alternate != moving_line:
        for basis, line in [
            (parameters["line_sum_basis"], moving_line),
            (
                (
                    "trigram_numbers"
                    if parameters["line_sum_basis"] == "raw_counts"
                    else "raw_counts"
                ),
                alternate,
            ),
        ]:
            variant = compose_meihua_hexagram(
                upper_number=seed["upper_number"],
                lower_number=seed["lower_number"],
                moving_line=line,
            )
            for key in ("base_hexagram", "changed_hexagram", "mutual_hexagram"):
                variant[key]["meaning_source_kind"] = "modern_editorial_summary"
            variants.append(
                {
                    "line_sum_basis": basis,
                    "selected": line == moving_line,
                    "moving_line": line,
                    "base_code": variant["base_hexagram"]["binary_code"],
                    "changed_code": variant["changed_hexagram"]["binary_code"],
                    "mutual_code": variant["mutual_hexagram"]["binary_code"],
                    **{
                        key: variant[key]
                        for key in (
                            "base_hexagram",
                            "changed_hexagram",
                            "mutual_hexagram",
                            "body_trigram",
                            "use_trigram",
                        )
                    },
                    "body": variant["body_trigram"]["name"],
                    "use": variant["use_trigram"]["name"],
                    "moving_palace": variant["moving_palace"],
                    "body_use_relation": variant["body_use_relation"],
                    "stage_relations": meihua_stage_relations(
                        variant, fact_prefix=f"meihua.counting_variants.{len(variants)}"
                    ),
                }
            )
    return {
        "method": "meihua_" + method,
        "seed": seed,
        "counting_variants": variants,
        **compose_meihua_hexagram(
            upper_number=seed["upper_number"],
            lower_number=seed["lower_number"],
            moving_line=moving_line,
            label="梅花显式卦",
        ),
    }, trace

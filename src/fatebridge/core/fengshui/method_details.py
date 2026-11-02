"""Source-labelled method and palace references; these do not judge a house."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, cast

from .bazhai_interpretation import fuwei_element_context
from .directions import rule_data
from .materials import material_reference


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "expert-methods-v1.json"
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _supplement() -> Dict[str, Any]:
    path = (
        Path(__file__).parents[2]
        / "data"
        / "fengshui"
        / "method-reference-supplement-v1.json"
    )
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def reference_data(key: str) -> Any:
    """Return isolated data so projections and callers cannot mutate the cache."""
    return deepcopy(_bundle()[key])


def method_reference_provenance() -> Dict[str, Any]:
    record = reference_data("ruleset")
    sources = reference_data("sources")
    sources.update(deepcopy(_supplement()["sources"]))
    foundation = rule_data("sources")
    for key in ("S10", "S12"):
        sources["FOUNDATION_" + key] = foundation[key]
    for source in material_reference()["ruleset"]["sources"]:
        source = deepcopy(source)
        source_id = source.pop("source_id")
        if source_id in sources and sources[source_id] != source:
            raise ValueError(f"Conflicting method reference source: {source_id}")
        sources[source_id] = source
    source_ids = list(dict.fromkeys([*record["source_ids"], *sources]))
    return {
        **record,
        "bundle_version": _bundle()["bundle_version"],
        "source_ids": source_ids,
        "sources": [dict(source_id=s, **sources[s]) for s in source_ids],
    }


def _flying_star_references() -> Dict[str, Any]:
    """Join registered Luo Shu numbers to labelled, non-operational references.

    The classical text supplies trigram symbols, not the flying-star number
    relation. Neither those symbols nor the modern author's example chart is
    allowed to identify an occupant or assign an object to a physical sector.
    """
    fixed_by_number = {
        str(palace["palace_number"]): palace
        for palace in rule_data("directions").values()
    }
    symbols = _supplement()["cross_text_trigram_symbols"]
    teaching = _supplement()["flying_star_teaching"]
    result = {}
    for number, star in rule_data("annual_stars").items():
        fixed = fixed_by_number.get(number)
        trigram = fixed["trigram"] if fixed else None
        result[number] = {
            **deepcopy(teaching[number]),
            "number": int(number),
            "name": star["name"],
            "element": star["element"],
            "reference_frame": "arriving_flying_star",
            "lookup_key": "actual_layer_star_number",
            "symbolic_trigram": trigram,
            "symbol_derivation": (
                "registered_luoshu_number_to_classical_trigram_symbols"
                if trigram
                else "no_trigram_or_family_role_for_five"
            ),
            "symbolic_person_and_object_reference": (
                deepcopy(symbols[trigram]) if trigram else None
            ),
            "symbol_scope": (
                "cross_text_reference_not_actual_occupant_or_furniture_assignment"
            ),
            "source_ids": list(
                dict.fromkeys(["FOUNDATION_S4", *teaching[number]["source_ids"]])
            ),
        }
    return result


def method_details(methods: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Explain selected engines, keeping fixed palaces and visiting stars apart.

    An omitted filter gives the three method families. An explicit empty list
    gives no method chapters while retaining the common directional reference.
    """
    families = {
        "annual_stars": "nine_palace_flying_stars",
        "monthly_stars": "nine_palace_flying_stars",
        "xuankong_natal": "nine_palace_flying_stars",
        "nine_palace_flying_stars": "nine_palace_flying_stars",
        "jinsuo": "jinsuo",
        "bazhai": "bazhai",
    }
    chapters = reference_data("method_details")
    selected = (
        list(chapters)
        if methods is None
        else list(dict.fromkeys(families[m] for m in methods))
    )
    palaces = reference_data("direction_references")
    supplement = deepcopy(_supplement())
    for direction, record in palaces.items():
        if direction != "C":
            fixed = rule_data("directions")[direction]
            record.update(
                direction=direction,
                label=fixed["label"],
                fixed_palace_number=fixed["palace_number"],
                fixed_palace_trigram=fixed["trigram"],
                fixed_palace_element=fixed["element"],
                cross_text_symbol_reference={
                    "trigram": fixed["trigram"],
                    "lookup": "cross_text_trigram_symbols[fixed_palace_trigram]",
                    "scope": "fixed_palace_symbol_reference_not_arriving_star",
                    "source_ids": ["MEIHUA_TRIGRAM_SYMBOLS", "SHUOGUA_PRIMARY"],
                },
            )
        else:
            record.update(
                direction="C",
                label="中宫",
                fixed_palace_number=5,
                fixed_palace_trigram=None,
                fixed_palace_element="土",
                cross_text_symbol_reference=None,
            )
    for key in selected:
        chapters[key]["application_references"] = supplement["application_references"][
            key
        ]
    sand_water = reference_data("sand_water_reference")
    sand_water["form_condition_references"] = supplement["application_references"][
        "jinsuo"
    ]["form_condition_references"]
    return {
        "status": "reference_only",
        "scope": "source_labelled_reference_not_additional_selected_calculation",
        "ruleset": method_reference_provenance(),
        "methods": {key: chapters[key] for key in selected},
        "palaces": palaces,
        "star_elements": {
            number: {"name": star["name"], "element": star["element"]}
            for number, star in rule_data("annual_stars").items()
        },
        "mapping_boundaries": supplement["mapping_boundaries"],
        "flying_star_references": _flying_star_references(),
        "cross_text_trigram_symbols": supplement["cross_text_trigram_symbols"],
        "object_observation_references": supplement["object_observation_references"],
        "material_shape_reference": material_reference(),
        "bazhai_you_nian_references": {
            star["name"]: {
                **star,
                "status": "reference_only",
                "reference_frame": "bazhai_you_nian",
                "lookup_key": "actual_bazhai_star_name",
                "scope": "bazhai_relation_star_not_flying_star_number",
                "source_ids": ["FOUNDATION_S3", "FOUNDATION_S10"],
                **(
                    {
                        "element_policy": "selected_star_table_fixed_fuwei_wood",
                        "source_context_variation": fuwei_element_context(
                            "FOUNDATION_"
                        ),
                    }
                    if star["name"] == "伏位"
                    else {}
                ),
            }
            for star in rule_data("bazhai_stars").values()
        },
        "sand_water_reference": sand_water,
        "limitations": reference_data("limitations") + supplement["limitations"],
    }

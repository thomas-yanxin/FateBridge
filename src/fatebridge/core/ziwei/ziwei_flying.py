"""Palace-stem transformations located on the computed natal chart."""

from collections.abc import Iterable, Mapping

_SIHUA_ORDER = ("化禄", "化权", "化科", "化忌")


def palace_sihua_relations(
    palaces: Iterable[tuple[str, str, Iterable[str]]],
    selected_rules: Mapping[str, Mapping[str, str]],
    *,
    sihua_rule: str,
) -> dict[str, object]:
    """Group all palace-stem assignments by transformation and target star.

    Input tuples contain the natal palace name, ganzhi and ordered base star
    names. The palace and star order matches the paths in the full natal result.
    """
    target_stars = {star for row in selected_rules.values() for star in row.values()}
    occurrences: dict[str, list[dict[str, str]]] = {}
    origins: dict[str, dict[str, list[tuple[str, str]]]] = {
        transformation: {} for transformation in _SIHUA_ORDER
    }
    for palace_index, (palace_name, ganzhi, stars) in enumerate(palaces):
        stem, branch = ganzhi[0], ganzhi[1]
        for transformation, by_star in origins.items():
            target_star = selected_rules[stem][transformation]
            by_star.setdefault(target_star, []).append((palace_name, ganzhi))
        for star_index, star in enumerate(stars):
            if star in target_stars:
                occurrences.setdefault(star, []).append(
                    {
                        "palace_name": palace_name,
                        "branch": branch,
                        "calculation_path": (
                            f"ziwei_birth.palaces.{palace_index}.stars_detail.{star_index}"
                        ),
                    }
                )

    groups = []
    for transformation, by_star in origins.items():
        for star, sending_palaces in by_star.items():
            targets = occurrences.get(star, [])
            target_branches = {target["branch"] for target in targets}
            groups.append(
                {
                    "transformation": transformation,
                    "target_star": star,
                    "target_occurrences": targets,
                    "origins": [
                        {
                            "source_palace": palace_name,
                            "source_stem": ganzhi[0],
                            "source_branch": ganzhi[1],
                            "self_transformation": (
                                ganzhi[1] in target_branches if targets else None
                            ),
                        }
                        for palace_name, ganzhi in sending_palaces
                    ],
                }
            )
    return {
        "policy": "selected_natal_table_reused_for_palace_stems",
        "sihua_rule": sihua_rule,
        "groups": groups,
    }

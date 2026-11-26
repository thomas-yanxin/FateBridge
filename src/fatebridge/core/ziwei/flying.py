"""Feixing / Qintian 12-palace flying SiHua matrix, Laiyin palace, and clash chains."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from fatebridge.core.ziwei.tables import SIHUA_ORDER
from fatebridge.utils.data import ZIWEI_BRANCH_SEQUENCE


def find_laiyin_gong(
    palaces: Iterable[Mapping[str, Any]], year_stem: str
) -> dict[str, str]:
    """Return 来因宫: the palace whose stem == natal year stem, excluding 子/丑."""
    for palace in palaces:
        ganzhi = str(palace["ganzhi"])
        if ganzhi[0] == year_stem and ganzhi[1] not in ("子", "丑"):
            return {
                "name": str(palace["name"]),
                "branch": ganzhi[1],
                "ganzhi": ganzhi,
            }
    raise ValueError(f"未找到年干 {year_stem} 对应的来因宫")


def build_flying_sihua(
    palaces: list[dict[str, Any]],
    selected_rules: Mapping[str, Mapping[str, str]],
    *,
    year_stem: str,
    sihua_rule: str,
) -> dict[str, Any]:
    """Compute compact 12-palace flying SiHua matrix, 离心/向心自化, 忌冲, and 禄转忌/忌转忌."""
    by_branch = {p["ganzhi"][1]: p for p in palaces}
    star_locations: dict[str, list[tuple[str, str]]] = {}
    for palace in palaces:
        branch = palace["ganzhi"][1]
        for star in palace["stars_detail"]:
            star_locations.setdefault(star["name"], []).append((palace["name"], branch))

    def opposite_branch(branch: str) -> str:
        idx = ZIWEI_BRANCH_SEQUENCE.index(branch)
        return ZIWEI_BRANCH_SEQUENCE[(idx + 6) % 12]

    inward_received: dict[str, list[str]] = {p["name"]: [] for p in palaces}
    raw_rows: dict[str, dict[str, Any]] = {}
    first_targets: dict[str, dict[str, tuple[str | None, str | None, str | None]]] = {}

    for palace in palaces:
        src_name = palace["name"]
        src_gz = palace["ganzhi"]
        src_stem, src_branch = src_gz[0], src_gz[1]
        opp_branch = opposite_branch(src_branch)
        opp_name = by_branch[opp_branch]["name"]
        transforms: dict[str, str] = {}
        outward_self: list[str] = []
        ji_clash: str | None = None
        first_targets[src_name] = {}

        for tr in SIHUA_ORDER:
            target_star = selected_rules[src_stem][tr]
            locs = star_locations.get(target_star, [])
            if locs:
                tgt_name, tgt_branch = locs[0]
                clash_branch = opposite_branch(tgt_branch)
                clash_name = by_branch[clash_branch]["name"]
                if any(b == src_branch for _, b in locs):
                    outward_self.append(tr)
                if any(b == opp_branch for _, b in locs):
                    inward_received[opp_name].append(f"{src_name}:{tr}({target_star})")
                transforms[tr] = f"{target_star}->{tgt_name}"
                first_targets[src_name][tr] = (target_star, tgt_name, clash_name)
                if tr == "化忌":
                    ji_clash = f"{tgt_name}({tgt_branch})冲{clash_name}({clash_branch})"
            else:
                transforms[tr] = f"{target_star}->未落盘"
                first_targets[src_name][tr] = (target_star, None, None)

        row_entry: dict[str, Any] = {
            "palace": src_name,
            "ganzhi": src_gz,
            "transforms": transforms,
            "ji_clash": ji_clash,
        }
        if src_stem == year_stem and src_branch not in ("子", "丑"):
            row_entry["is_original_palace"] = True
        if outward_self:
            row_entry["outward_self"] = outward_self
        raw_rows[src_name] = row_entry

    matrix: list[dict[str, Any]] = []
    for palace in palaces:
        src_name = palace["name"]
        row = raw_rows[src_name]
        if inward_received[src_name]:
            row["inward_self"] = inward_received[src_name]
        for chain_key, first_tr in (("lu_to_ji", "化禄"), ("ji_to_ji", "化忌")):
            _, via_palace, _ = first_targets[src_name][first_tr]
            if via_palace is None:
                row[chain_key] = None
            else:
                ji_star, tgt_palace, clash_palace = first_targets[via_palace]["化忌"]
                row[chain_key] = (
                    f"{via_palace}->{ji_star}@{tgt_palace}(冲{clash_palace})"
                    if tgt_palace
                    else f"{via_palace}->{ji_star}@未落盘"
                )
        matrix.append(row)

    return {
        "sihua_rule": sihua_rule,
        "laiyin_gong": find_laiyin_gong(palaces, year_stem),
        "matrix": matrix,
    }


def palace_sihua_relations(
    palaces: Iterable[tuple[str, str, Iterable[str]]],
    selected_rules: Mapping[str, Mapping[str, str]],
    *,
    sihua_rule: str,
) -> dict[str, object]:
    """Group all palace-stem assignments by transformation and target star."""
    target_stars = {star for row in selected_rules.values() for star in row.values()}
    occurrences: dict[str, list[dict[str, str]]] = {}
    origins: dict[str, dict[str, list[tuple[str, str]]]] = {
        transformation: {} for transformation in SIHUA_ORDER
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

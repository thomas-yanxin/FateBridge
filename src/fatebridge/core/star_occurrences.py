"""Count supplied physical star entries, separately from weighted force scores."""

from typing import Any, Mapping, Sequence

from fatebridge.utils.data import TenGod


def build_star_occurrences(
    stars: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    counts = {}
    for god, entries in stars.items():
        visible = hidden = 0
        for entry in entries:
            if entry["location"] == "天干":
                if entry["pillar"] == "day":
                    raise ValueError("被评日干不能混入支持星的实数")
                visible += 1
            elif entry["location"] == "地支藏干":
                hidden += 1
            else:
                raise ValueError("未知星位层不能悄悄计为零")
        counts[god] = {
            "visible_count": visible,
            "hidden_count": hidden,
            "total_count": visible + hidden,
        }
    return {
        "method_id": "physical_ten_god_occurrences_v1",
        "quantity_kind": "physical_occurrences_not_force_or_weighted_score",
        "day_stem_counted_as_support": False,
        "status": (
            "complete_star_categories"
            if set(stars) == {g.value for g in TenGod}
            else "partial_star_categories"
        ),
        "gods": counts,
        "scope": "只数同次ten_gods实际星位：非日干每项1、每个藏干每项1，透藏分列；未提供类别不补零。不是0.5藏干加权、有效力量、制杀成败或独立人数；印不透不等于无藏印。",
    }

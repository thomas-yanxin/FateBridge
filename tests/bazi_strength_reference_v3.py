"""Independent rational budget arithmetic under a literal seasonal table.

No FateBridge imports or numerical-output inputs. Relations are supplied discrete
premises, not independently adjudicated rules. Coefficients are declared decimal
engineering policy, not classical constants. The frozen v2 reference remains
unchanged; its reversed 囚/死 mapping is retained explicitly for historical replay.
"""

from fractions import Fraction as Q

ORDER = ("year", "month", "day", "hour")
ELEMENTS = "木火土金水"
STEM_ELEMENT = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
HIDDEN = dict(
    zip(
        "子丑寅卯辰巳午未申酉戌亥",
        (
            "癸",
            "己癸辛",
            "甲丙戊",
            "乙",
            "戊乙癸",
            "丙庚戊",
            "丁己",
            "己丁乙",
            "庚壬戊",
            "辛",
            "戊辛丁",
            "壬甲",
        ),
    )
)
GENERATES = dict(zip(ELEMENTS, "火土金水木"))
SHARES = {1: (Q(1),), 2: (Q(2, 3), Q(1, 3)), 3: (Q(4, 7), Q(2, 7), Q(1, 7))}
PHASE_FACTORS = {"旺": Q(2), "相": Q(3, 2), "休": Q(1), "囚": Q(3, 4), "死": Q(1, 2)}
MONTH_SEASONS = dict(
    zip(
        "寅卯巳午申酉亥子辰未戌丑",
        (
            "春",
            "春",
            "夏",
            "夏",
            "秋",
            "秋",
            "冬",
            "冬",
            "季月",
            "季月",
            "季月",
            "季月",
        ),
    )
)
# Element order is 木火土金水. These are literal rows, not the production
# generation/control branches. 辰未戌丑整月属土 is the declared software scope.
SEASONAL_PHASES = {
    "春": dict(zip(ELEMENTS, ("旺", "相", "死", "囚", "休"))),
    "夏": dict(zip(ELEMENTS, ("休", "旺", "相", "死", "囚"))),
    "秋": dict(zip(ELEMENTS, ("死", "囚", "休", "旺", "相"))),
    "冬": dict(zip(ELEMENTS, ("相", "死", "囚", "休", "旺"))),
    "季月": dict(zip(ELEMENTS, ("囚", "休", "旺", "相", "死"))),
}
LEGACY_SEASONAL_PHASES = {
    "春": dict(zip(ELEMENTS, ("旺", "相", "囚", "死", "休"))),
    "夏": dict(zip(ELEMENTS, ("休", "旺", "相", "囚", "死"))),
    "秋": dict(zip(ELEMENTS, ("囚", "死", "休", "旺", "相"))),
    "冬": dict(zip(ELEMENTS, ("相", "囚", "死", "休", "旺"))),
    "季月": dict(zip(ELEMENTS, ("死", "休", "旺", "相", "囚"))),
}
POLICY = {
    "branch_budget": "2",
    "month_multiplier": "2",
    "seasonal_spread": "1",
    "floating_stem": "0.25",
    "rooted_stem": "1",
    "reveal_multiplier": "1.25",
    "strong_share": "0.60",
    "weak_share": "0.40",
    "clash_winner": "0.90",
    "clash_loser": "0.50",
    "clash_equal": "0.75",
    "punishment": "0.90",
    "binding": "0.85",
    "partial_transfer": "0.20",
    "transformation_transfer": "0.80",
}


def seasonal_phases(month_branch, *, legacy=False):
    table = LEGACY_SEASONAL_PHASES if legacy else SEASONAL_PHASES
    return dict(table[MONTH_SEASONS[month_branch]])


def reconstruct(values, relations, policy=None):
    """Rebuild every energy with Fractions, conditional on relation decisions."""
    p = {key: Q(value) for key, value in (POLICY if policy is None else policy).items()}
    pillars = dict(zip(ORDER, values))
    masses = {}
    synthetic = {name: {element: Q(0) for element in ELEMENTS} for name in ORDER}
    loss = {name: {element: Q(1) for element in ELEMENTS} for name in ORDER}
    for name, (_, branch) in pillars.items():
        budget = p["branch_budget"] * (p["month_multiplier"] if name == "month" else 1)
        for stem, share in zip(HIDDEN[branch], SHARES[len(HIDDEN[branch])]):
            masses[name, stem] = budget * share
    for event in relations:
        kind, status, positions = event["kind"], event["status"], event["positions"]
        if kind in {"三会", "三合", "六合", "半合"}:
            if status in {"conditioned_transformation", "partial_tendency"}:
                target = event["target"]
                fraction = (
                    p["transformation_transfer"]
                    if status == "conditioned_transformation"
                    else p["partial_transfer"]
                )
                for name in positions:
                    for stem in HIDDEN[pillars[name][1]]:
                        if STEM_ELEMENT[stem] != target:
                            transferred = masses[name, stem] * fraction
                            masses[name, stem] -= transferred
                            synthetic[name][target] += transferred
            elif status == "binding":
                for name in positions:
                    for element in ELEMENTS:
                        loss[name][element] = min(loss[name][element], p["binding"])
        if status == "active" and kind == "六冲" and "root_multipliers" in event:
            for name, multiplier in event["root_multipliers"].items():
                for element in ELEMENTS:
                    loss[name][element] = min(loss[name][element], Q(str(multiplier)))
        if "storage_effect" in event:
            for row in event["storage_effect"]["root_effects"]:
                name, element = row["pillar"], row["element"]
                loss[name][element] = min(
                    loss[name][element], Q(str(row["event_retention_multiplier"]))
                )
        elif status == "active" and kind in {"刑", "自刑"}:
            for name in positions:
                for element in ELEMENTS:
                    loss[name][element] = min(loss[name][element], p["punishment"])
    phases = seasonal_phases(values[1][1])
    factors = {
        element: 1 + (PHASE_FACTORS[phases[element]] - 1) * p["seasonal_spread"]
        for element in ELEMENTS
    }
    visible = {pillar[0] for pillar in values}
    roots = {element: Q(0) for element in ELEMENTS}
    energies = {element: Q(0) for element in ELEMENTS}
    for (name, stem), mass in masses.items():
        element = STEM_ELEMENT[stem]
        remaining = mass * loss[name][element]
        roots[element] += remaining
        energies[element] += (
            remaining
            * factors[element]
            * (p["reveal_multiplier"] if stem in visible else 1)
        )
    for name in ORDER:
        for element, mass in synthetic[name].items():
            energies[element] += mass * loss[name][element] * factors[element]
    binding = {name: Q(1) for name in ORDER}
    for event in relations:
        if event["kind"] == "天干合" and event["status"] == "binding":
            for name in event["positions"]:
                if name == "day":
                    raise ValueError("Default binding cannot consume the day stem")
                binding[name] = p["binding"]
        if (
            event["kind"] == "天干合"
            and event["status"] == "conditioned_transformation"
        ):
            raise ValueError("Non-adopted stem conversion is outside this reference")
    for name in ("year", "month", "hour"):
        element = STEM_ELEMENT[pillars[name][0]]
        activation = p["floating_stem"] + (p["rooted_stem"] - p["floating_stem"]) * min(
            1, roots[element]
        )
        energies[element] += binding[name] * activation * factors[element]
    body = STEM_ELEMENT[values[2][0]]
    seal = next(element for element in ELEMENTS if GENERATES[element] == body)
    support = energies[body] + energies[seal]
    weaken = sum(
        value for element, value in energies.items() if element not in {body, seal}
    )
    share = support / (support + weaken) if support + weaken else Q(1, 2)
    grade = (
        "强"
        if share > p["strong_share"]
        else "弱" if share < p["weak_share"] else "中和"
    )
    return {
        "energies": energies,
        "support": support,
        "weaken": weaken,
        "share": share,
        "numerical_grade": grade,
        "requires_special_structure_review": share < Q(3, 20) or share > Q(17, 20),
        "body": energies[body],
        "seal": energies[seal],
        "body_within_support": energies[body] / support,
        "body_seal_relation": (
            "body_greater"
            if energies[body] > energies[seal]
            else "seal_greater" if energies[body] < energies[seal] else "equal"
        ),
    }

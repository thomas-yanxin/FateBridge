"""Rational budget reconstruction, conditional on supplied discrete decisions.

No FateBridge import and no reading of its energies, shares or grades. Literal
tables and decimal engineering coefficients are stated here independently of
the numerical output under examination. This does not adjudicate relations.
"""
from fractions import Fraction as Q

ORDER = ("year", "month", "day", "hour")
ELEMENTS = "木火土金水"
STEM_ELEMENT = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
HIDDEN = dict(zip("子丑寅卯辰巳午未申酉戌亥", ("癸", "己癸辛", "甲丙戊", "乙", "戊乙癸", "丙庚戊", "丁己", "己丁乙", "庚壬戊", "辛", "戊辛丁", "壬甲")))
GENERATES = dict(zip(ELEMENTS, ELEMENTS[1:] + ELEMENTS[:1]))
CONTROLS = dict(zip(ELEMENTS, "土金水木火"))
SHARES = {1: (Q(1),), 2: (Q(2, 3), Q(1, 3)), 3: (Q(4, 7), Q(2, 7), Q(1, 7))}
PHASE = {"旺": Q(2), "相": Q(3, 2), "休": Q(1), "囚": Q(3, 4), "死": Q(1, 2)}
POLICY = {
    "branch_budget": "2", "month_multiplier": "2", "seasonal_spread": "1",
    "floating_stem": "0.25", "rooted_stem": "1", "reveal_multiplier": "1.25",
    "strong_share": "0.60", "weak_share": "0.40", "clash_winner": "0.90",
    "clash_loser": "0.50", "clash_equal": "0.75", "punishment": "0.90",
    "binding": "0.85", "partial_transfer": "0.20", "transformation_transfer": "0.80",
}


def reconstruct(values, relations, policy=None):
    p = {k: Q(v) for k, v in (policy or POLICY).items()}
    pillars = dict(zip(ORDER, values))
    masses = {}
    synthetic = {n: {e: Q(0) for e in ELEMENTS} for n in ORDER}
    loss = {n: {e: Q(1) for e in ELEMENTS} for n in ORDER}
    for n, (_, branch) in pillars.items():
        budget = p["branch_budget"] * (p["month_multiplier"] if n == "month" else 1)
        for stem, share in zip(HIDDEN[branch], SHARES[len(HIDDEN[branch])]):
            masses[n, stem] = budget * share
    for event in relations:
        kind, status, positions = event["kind"], event["status"], event["positions"]
        if kind in {"三会", "三合", "六合", "半合"}:
            if status in {"conditioned_transformation", "partial_tendency"}:
                target = event["target"]
                fraction = p["transformation_transfer"] if status == "conditioned_transformation" else p["partial_transfer"]
                for n in positions:
                    for stem in HIDDEN[pillars[n][1]]:
                        if STEM_ELEMENT[stem] != target:
                            transferred = masses[n, stem] * fraction
                            masses[n, stem] -= transferred
                            synthetic[n][target] += transferred
            elif status == "binding":
                for n in positions:
                    for element in ELEMENTS:
                        loss[n][element] = min(loss[n][element], p["binding"])
        if status == "active" and kind == "六冲" and "root_multipliers" in event:
            for n, multiplier in event["root_multipliers"].items():
                for element in ELEMENTS:
                    loss[n][element] = min(loss[n][element], Q(str(multiplier)))
        if "storage_effect" in event:
            for row in event["storage_effect"]["root_effects"]:
                n, element = row["pillar"], row["element"]
                loss[n][element] = min(loss[n][element], Q(str(row["event_retention_multiplier"])))
        elif status == "active" and kind in {"刑", "自刑"}:
            for n in positions:
                for element in ELEMENTS:
                    loss[n][element] = min(loss[n][element], p["punishment"])
    visible = {pillar[0] for pillar in values}
    month_element = STEM_ELEMENT[HIDDEN[values[1][1]][0]]
    factors = {}
    for element in ELEMENTS:
        phase = "旺" if element == month_element else "相" if GENERATES[month_element] == element else "休" if GENERATES[element] == month_element else "囚" if CONTROLS[month_element] == element else "死"
        factors[element] = 1 + (PHASE[phase] - 1) * p["seasonal_spread"]
    roots = {e: Q(0) for e in ELEMENTS}
    energies = {e: Q(0) for e in ELEMENTS}
    for (n, stem), mass in masses.items():
        element = STEM_ELEMENT[stem]
        remaining = mass * loss[n][element]
        roots[element] += remaining
        energies[element] += remaining * factors[element] * (p["reveal_multiplier"] if stem in visible else 1)
    for n in ORDER:
        for element, mass in synthetic[n].items():
            energies[element] += mass * loss[n][element] * factors[element]
    binding = {n: Q(1) for n in ORDER}
    for event in relations:
        if event["kind"] == "天干合" and event["status"] == "binding":
            for n in event["positions"]:
                if n == "day":
                    raise ValueError("Default binding cannot consume the day stem")
                binding[n] = p["binding"]
        if event["kind"] == "天干合" and event["status"] == "conditioned_transformation":
            raise ValueError("Non-adopted stem conversion is outside this reference")
    for n in ("year", "month", "hour"):
        element = STEM_ELEMENT[pillars[n][0]]
        activation = p["floating_stem"] + (p["rooted_stem"] - p["floating_stem"]) * min(1, roots[element])
        energies[element] += binding[n] * activation * factors[element]
    body = STEM_ELEMENT[values[2][0]]
    parent = next(e for e in ELEMENTS if GENERATES[e] == body)
    support = energies[body] + energies[parent]
    weaken = sum(v for e, v in energies.items() if e not in {body, parent})
    share = support / (support + weaken) if support + weaken else Q(1, 2)
    grade = "强" if share > p["strong_share"] else "弱" if share < p["weak_share"] else "中和"
    return {"energies": energies, "support": support, "weaken": weaken, "share": share, "numerical_grade": grade}

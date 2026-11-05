"""Independent literal candidate catalogue; no production imports or strengths."""

from itertools import combinations

ORDER = ("year", "month", "day", "hour")
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
FULL = (
    ("三会", "寅卯辰", "木"),
    ("三会", "巳午未", "火"),
    ("三会", "申酉戌", "金"),
    ("三会", "亥子丑", "水"),
    ("三合", "申子辰", "水"),
    ("三合", "亥卯未", "木"),
    ("三合", "寅午戌", "火"),
    ("三合", "巳酉丑", "金"),
)
PAIRS = {
    frozenset(p): t
    for p, t in (
        ("子丑", "土"),
        ("寅亥", "木"),
        ("卯戌", "火"),
        ("辰酉", "金"),
        ("巳申", "水"),
        ("午未", "土"),
    )
}
HALF = (
    ("申子辰", "子", "水"),
    ("亥卯未", "卯", "木"),
    ("寅午戌", "午", "火"),
    ("巳酉丑", "酉", "金"),
)


def identifier(kind, target, positions):
    return "bc1:" + kind + ":" + target + ":" + "-".join(positions)


def geometries(branches):
    rows = []
    for kind, group, target in FULL:
        seats = [i for i, b in enumerate(branches) if b in group]
        if set(branches[i] for i in seats) == set(group):
            rows.append((kind, target, tuple(ORDER[i] for i in seats)))
    for pair in combinations(range(4), 2):
        target = PAIRS.get(frozenset(branches[i] for i in pair))
        if target is not None:
            rows.append(("六合", target, tuple(ORDER[i] for i in pair)))
    for group, peak, target in HALF:
        for pair in combinations(range(4), 2):
            observed = set(branches[i] for i in pair)
            if len(observed) == 2 and peak in observed and observed < set(group):
                rows.append(("半合", target, tuple(ORDER[i] for i in pair)))
    return rows

"""Independent literal topology oracle; no production relation helpers or labels."""

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
    frozenset(p): e
    for p, e in (
        ("子丑", "土"),
        ("寅亥", "木"),
        ("卯戌", "火"),
        ("辰酉", "金"),
        ("巳申", "水"),
        ("午未", "土"),
    )
}
CLASHES = [set(p) for p in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")]


def affiliations(branches):
    """Return pair and full physical seats; clashes, pair-only and rivals excluded."""
    full = []
    for kind, letters, target in FULL:
        seats = tuple(i for i, b in enumerate(branches) if b in letters)
        if set(branches[i] for i in seats) == set(letters):
            full.append((kind, seats, target))
    result = []
    for i in range(3):
        pair = (i, i + 1)
        target = PAIRS.get(frozenset(branches[j] for j in pair))
        if target is None or any(set(pair) <= set(f[1]) for f in full):
            continue
        for kind, seats, element in full:
            union = sorted(set(pair) | set(seats))
            if target != element or not set(pair) & set(seats):
                continue
            if any(
                set((branches[a], branches[b])) in CLASHES
                for a, b in combinations(union, 2)
            ):
                continue
            result.append((pair, kind, seats, target))
    return result

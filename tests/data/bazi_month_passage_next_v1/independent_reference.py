"""Frozen literal physical reference; imports no FateBridge producer or tables."""

from itertools import product

PILLARS = ("year", "month", "day", "hour")
ELEMENTS = "木火土金水"
STEMS = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
HIDDEN = dict(zip("子丑寅卯辰巳午未申酉戌亥", ("癸", "己癸辛", "甲丙戊", "乙", "戊乙癸", "丙戊庚", "丁己", "己丁乙", "庚壬戊", "辛", "戊辛丁", "壬甲")))


def geometry(positions):
    a, m, b = map(PILLARS.index, positions)
    if len(set(positions)) < 3:
        return "shared_pillar_step"
    if min(a, b) < m < max(a, b):
        return "adjacent_mediator_between" if abs(a - m) == abs(m - b) == 1 else "between_with_gap"
    return "outside_interval"


def possible_path(value):
    """Existence of one physical completion, without writing inferred fields."""
    refs = [value.get(k) for k in ("from_node", "via_node", "to_node")]
    known = [r.split(":") if r else None for r in refs]
    for start in range(5):
        es = [ELEMENTS[(start + offset) % 5] for offset in range(3)]
        if value.get("elements") is not None and value["elements"] != es:
            continue
        if any(k and STEMS[k[2]] != es[i] for i, k in enumerate(known)):
            continue
        pos = [([k[0]] if k else PILLARS) for k in known]
        if value.get("positions") is not None:
            if any(k and k[0] != value["positions"][i] for i, k in enumerate(known)):
                continue
            pos = [[p] for p in value["positions"]]
        planes = [([k[1]] if k else ("stem", "hidden")) for k in known]
        glyphs = [([k[2]] if k else [s for s in STEMS if STEMS[s] == es[i]]) for i, k in enumerate(known)]
        for ps, ls in product(product(*pos), product(*planes)):
            layer = ls[0] if len(set(ls)) == 1 else "mixed"
            if value.get("plane") is not None and value["plane"] != layer:
                continue
            if value.get("position_status") is not None and value["position_status"] != geometry(ps):
                continue
            if any(sum(p == q and l == "stem" for q, l in zip(ps, ls)) > 1 for p in PILLARS):
                continue
            for ss in product(*glyphs):
                choices = []
                for p in PILLARS:
                    local = [s for q, l, s in zip(ps, ls, ss) if q == p and l == "hidden"]
                    if local:
                        allowed = [h for h in HIDDEN.values() if len(set(local)) == len(local) and all(s in h for s in local)]
                        choices.append([all(h.index(s) == 0 for s in local) for h in allowed])
                if any(not c for c in choices):
                    continue
                for principal_flags in product(*choices):
                    principal = all(l == "hidden" for l in ls) and all(principal_flags)
                    if value.get("principal_hidden_only") is None or value["principal_hidden_only"] == principal:
                        return True
    return False

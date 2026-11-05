"""Corrected primitive input order; first independent reference remains retained."""

from fractions import Fraction
from itertools import product

ORDER = ("year", "month", "day", "hour")
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
GEOMETRIES = (
    "寅亥巳申",
    "寅亥申巳",
    "巳申寅亥",
    "巳申亥寅",
    "申巳寅亥",
    "申巳亥寅",
    "亥寅巳申",
    "亥寅申巳",
)
HIDDEN = {"寅": "甲丙戊", "亥": "壬甲", "巳": "丙庚戊", "申": "庚壬戊"}
ELEMENT = dict(zip(STEMS, "木木火火土土金金水水"))
PRINCIPAL = {"寅": "木", "亥": "水", "巳": "火", "申": "金"}
CONFLICT = {"寅": "申", "申": "寅", "巳": "亥", "亥": "巳"}
PUNISHED = frozenset("寅巳申")


def inputs():
    for branches in GEOMETRIES:
        choices = [STEMS[BRANCHES.index(b) % 2 :: 2] for b in branches]
        for stems in product(*choices):
            yield [s + b for s, b in zip(stems, branches)]


def remaining_masses(branches, punishment):
    initial = {}
    for p, branch in zip(ORDER, branches):
        hidden = HIDDEN[branch]
        weights = [2**i for i in reversed(range(len(hidden)))]
        budget = Fraction(4 if p == "month" else 2)
        initial[p] = [(s, budget * w / sum(weights)) for s, w in zip(hidden, weights)]
    powers = {
        e: sum(
            (
                mass
                for roots in initial.values()
                for s, mass in roots
                if ELEMENT[s] == e
            ),
            Fraction(0),
        )
        for e in "木火土金水"
    }
    losses = dict.fromkeys(ORDER, Fraction(1))
    for i, (p, b) in enumerate(zip(ORDER, branches)):
        for q, other in list(zip(ORDER, branches))[i + 1 :]:
            if CONFLICT[b] != other:
                continue
            a, c = powers[PRINCIPAL[b]], powers[PRINCIPAL[other]]
            m, n = (
                (Fraction(3, 4), Fraction(3, 4))
                if a == c
                else (
                    (Fraction(9, 10), Fraction(1, 2))
                    if a > c
                    else (Fraction(1, 2), Fraction(9, 10))
                )
            )
            losses[p], losses[q] = min(losses[p], m), min(losses[q], n)
    for p, b in zip(ORDER, branches):
        if b in PUNISHED:
            losses[p] = min(losses[p], punishment)
    return {
        (p, s): mass * losses[p] for p, roots in initial.items() for s, mass in roots
    }


def corrected_relations(events):
    # This reference identifies a contradiction from actual co-known events,
    # rather than recognizing any chart ids or branch-pattern lookup in a rule.
    adopted = {
        p
        for e in events
        if e["kind"] in {"三会", "三合", "六合"}
        and e["status"] in {"binding", "conditioned_transformation"}
        for p in e["positions"]
    }
    return [
        (
            {**e, "status": "active"}
            if e["kind"] == "刑"
            and e["status"] == "resolved_by_combination"
            and not set(e["positions"]) <= adopted
            else e
        )
        for e in events
    ]

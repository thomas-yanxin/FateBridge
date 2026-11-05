"""Lock the semantics of the shared ten-god scan primitive.

``iter_pillar_gods`` / ``count_ten_gods`` replaced seven hand-rolled loops across
the analysis layer. The subtle invariant they encode is the two-camp behavior:

- ``skip_day_pillar=False`` (default): skip the day *stem* only, but still count
  the day branch's hidden stems (personality / wealth / education / relatives /
  children).
- ``skip_day_pillar=True``: skip the *entire* day pillar (career / marriage).

These tests guard that distinction so a future refactor can't silently merge it.
"""

from __future__ import annotations

from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    TenGod,
    count_ten_gods,
    iter_pillar_gods,
)

# 戊 day master; day branch 午 hides 丁/己 so the day-pillar-hidden contribution
# is non-empty (which is exactly what the two camps disagree about).
PILLARS = {
    "year": ("甲", "子"),
    "month": ("丙", "寅"),
    "day": ("戊", "午"),
    "hour": ("壬", "戌"),
}
DAY_STEM = "戊"


def test_day_stem_is_never_emitted_as_a_stem_entry():
    for entry in iter_pillar_gods(PILLARS, DAY_STEM):
        assert not (entry.pillar == "day" and entry.location == "天干")


def test_default_counts_day_branch_hidden_stems():
    day_hidden_entries = [
        e
        for e in iter_pillar_gods(PILLARS, DAY_STEM)
        if e.pillar == "day" and e.location == "地支藏干"
    ]
    # 午 hides two stems, both surface at weight 0.5
    assert len(day_hidden_entries) == len(BRANCH_HIDDEN_STEMS["午"])
    assert all(e.weight == 0.5 for e in day_hidden_entries)


def test_skip_day_pillar_drops_the_whole_day_pillar():
    entries = list(iter_pillar_gods(PILLARS, DAY_STEM, skip_day_pillar=True))
    assert all(e.pillar != "day" for e in entries)


def test_stem_and_hidden_weights():
    for e in iter_pillar_gods(PILLARS, DAY_STEM):
        assert e.weight == (1.0 if e.location == "天干" else 0.5)


def test_count_matches_iter_sum():
    counts = count_ten_gods(PILLARS, DAY_STEM)
    manual = {tg: 0.0 for tg in TenGod}
    for e in iter_pillar_gods(PILLARS, DAY_STEM):
        manual[e.ten_god] += e.weight
    assert counts == manual


def test_two_camps_differ_by_exactly_the_day_branch_hidden():
    default = count_ten_gods(PILLARS, DAY_STEM)
    skipped = count_ten_gods(PILLARS, DAY_STEM, skip_day_pillar=True)
    # the only difference is the day branch's hidden stems
    delta = {tg: round(default[tg] - skipped[tg], 1) for tg in TenGod}
    expected = {tg: 0.0 for tg in TenGod}
    for hidden in BRANCH_HIDDEN_STEMS["午"]:
        from fatebridge.utils.data import get_ten_god

        expected[get_ten_god(DAY_STEM, hidden)] += 0.5
    assert delta == {tg: round(v, 1) for tg, v in expected.items()}

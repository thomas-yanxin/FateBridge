"""Two original stem-head formulae, preserved literal conflict and strict inputs."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.core.numerology_pillars as source
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.heluo import calculate, four_pillar_number_totals
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_numerology import (
    NumerologyPillarLink,
    NumerologyPillarLinks,
)
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parents[1] / "fixtures/numerology_pillar_links_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


def _valid(target, basis_stem, branch, expected_stem):
    p = dict(year="甲子", month="丙寅", day="甲子", hour="甲子")
    basis = "year" if target == "month" else "day"
    i = source.GAN.index(basis_stem)
    p[basis] = basis_stem + source.ZHI[i]
    p[target] = expected_stem + branch
    return p


@pytest.mark.parametrize("target", ["month", "hour"])
def test_120_valid_links_and_480_same_parity_wrong_links_per_formula(target):
    # Ten directly printed paired-stem groups yield 240 distinct valid links,
    # not 240 original birth examples. Wrong alternatives stay valid Ganzhi.
    total = wrong = 0
    for group in REFERENCE[target + "_heads"]:
        for stem in group["basis_stems"]:
            for branch, expected in zip(
                REFERENCE[target + "_branch_order"], group["expected_stems"]
            ):
                p = _valid(target, stem, branch, expected)
                e = source.require_pillar_links(p)
                row = next(r for r in e["links"] if r["target"] == target)
                assert row["head_pillar"] == group["head"]
                assert (
                    row["expected_pillar"] == row["actual_pillar"] == expected + branch
                )
                NumerologyPillarLinks.model_validate(e)
                total += 1
                for alt in source.GAN:
                    if alt == expected or alt + branch not in source.CYCLE:
                        continue
                    bad = {**p, target: alt + branch}
                    with pytest.raises(ValueError, match="衔接不一致"):
                        source.require_pillar_links(bad)
                    wrong += 1
    assert total == 120 and wrong == 480


def test_shared_calendar_month_and_hour_methods_follow_the_independent_source_heads():
    for group in REFERENCE["month_heads"]:
        for stem in group["basis_stems"]:
            year = 1984 + source.GAN.index(stem)
            for branch, expected in zip(
                REFERENCE["month_branch_order"], group["expected_stems"]
            ):
                assert BaZiCalendar.calculate_month_pillar_by_branch(year, branch) == (
                    expected,
                    branch,
                )
    seen = set()
    for delta in range(10):
        d = date(2000, 5, 15) + timedelta(days=delta)
        stem, _ = BaZiCalendar.calculate_day_pillar(d.year, d.month, d.day)
        group = next(r for r in REFERENCE["hour_heads"] if stem in r["basis_stems"])
        seen.add(stem)
        for hour, branch, expected in zip(
            range(0, 24, 2), REFERENCE["hour_branch_order"], group["expected_stems"]
        ):
            assert BaZiCalendar.calculate_hour_pillar(d.year, d.month, d.day, hour) == (
                expected,
                branch,
            )
    assert len(seen) == 10


@pytest.mark.parametrize(
    "p",
    [
        dict(year="甲子", month="甲寅", day="甲子", hour="甲子"),
        dict(year="甲子", month="丙寅", day="甲子", hour="丙子"),
    ],
)
def test_fixed_pillar_birth_entry_rejects_individually_valid_but_incompatible_pillars(
    p,
):
    assert all(v in source.CYCLE for v in p.values())
    with pytest.raises(ValueError, match="衔接不一致"):
        calculate(
            four_pillars=p,
            gender="男",
            birth_year=1924,
            month_zhi=p["month"][1],
            hour_zhi=p["hour"][1],
        )


def test_literal_introductory_source_example_is_preserved_as_arithmetic_not_a_birth_chart():
    c = REFERENCE["literal_source_conflict"]
    p = dict(zip(("year", "month", "day", "hour"), c["pillars"]))
    e = source.pillar_link_evidence(p)
    assert e["links"][0]["actual_pillar"] == "戊戌"
    assert e["links"][0]["expected_pillar"] == "丙戌"
    assert e["links"][0]["matches"] is False and e["links"][1]["matches"] is True
    with pytest.raises(ValueError, match="月柱与年干"):
        calculate(
            four_pillars=p, gender="女", birth_year=1930, month_zhi="戌", hour_zhi="亥"
        )
    totals = four_pillar_number_totals(p)
    assert {k: totals[k] for k in ["tian", "di", "tianNum", "diNum"]} == dict(
        tian=35, di=24, tianNum=1, diNum=4
    )
    assert "xian" not in totals and "not_birth_chart_validation" in totals["scope"]
    assert (
        json.loads(
            (
                ROOT.parents[2] / "tests/fixtures/numerology-classical-reference.json"
            ).read_text()
        )["heluo"][2]["pillars"]
        == c["pillars"]
    )


@pytest.mark.parametrize(
    "inp,year,day,hour",
    [
        (
            dict(date="2001-01-24", time="09:33", use_true_solar_time=False),
            "庚辰",
            None,
            None,
        ),
        (
            dict(date="2000-05-15", time="23:30", use_true_solar_time=False),
            "庚辰",
            "甲戌",
            "甲子",
        ),
        (
            dict(date="2000-05-16", time="00:30", use_true_solar_time=False),
            "庚辰",
            "甲戌",
            "甲子",
        ),
        (
            dict(date="2000-05-16", time="00:10", use_true_solar_time=True, lon=75),
            "庚辰",
            "癸酉",
            "癸亥",
        ),
    ],
)
def test_actual_selected_year_and_day_are_not_replaced_with_civil_labels(
    inp, year, day, hour
):
    r = build_heluo_result(**inp, zone="+08:00", gender="男")
    e = r["numerology_evidence"]["pillar_links"]
    assert e["pillars"]["year"] == year
    if day:
        assert e["pillars"]["day"] == day and e["pillars"]["hour"] == hour
    assert e["all_links_match"] is True and e["complete_calendar_assessment"] is False
    assert e["links"][0]["basis_pillar"] == year
    assert e["links"][1]["basis_pillar"] == e["pillars"]["day"]
    trace = next(
        x["facts"]
        for x in r["numerology_evidence"]["rule_trace"]
        if x["rule_id"] == source.RULESET_ID
    )
    assert e == trace and "[四柱干支衔接·卷七附法]" in r["snapshot_text"]
    e["links"][0]["actual_pillar"] = "甲寅"
    assert trace["links"][0]["actual_pillar"] != "甲寅"


@pytest.mark.parametrize(
    "patch",
    [
        {"basis": "day"},
        {"basis_pillar": "乙丑"},
        {"basis_stem": "乙"},
        {"source_stem_group": "甲己乙"},
        {"head_pillar": "戊寅"},
        {"branch_step": 1},
        {"actual_pillar": "戊寅"},
        {"expected_pillar": "丁寅"},
        {"matches": False},
        {"matches": "true"},
    ],
)
def test_typed_evidence_rejects_wrong_basis_head_steps_and_matches(patch):
    e = source.require_pillar_links(
        dict(year="甲子", month="丙寅", day="甲子", hour="甲子")
    )
    e["links"][0].update(patch)
    with pytest.raises(ValidationError):
        NumerologyPillarLinks.model_validate(e)


def test_typed_global_match_and_known_field_projection():
    e = source.require_pillar_links(
        dict(year="甲子", month="丙寅", day="甲子", hour="甲子")
    )
    e["all_links_match"] = False
    with pytest.raises(ValidationError):
        NumerologyPillarLinks.model_validate(e)
    row = NumerologyPillarLink.model_validate(
        {"target": "hour", "expected_pillar": "甲子"}
    )
    assert row.basis_stem is None and row.matches is None


@pytest.mark.parametrize("target", ["month", "hour"])
def test_internally_computed_conflict_is_not_reported_as_a_user_birth_fault(target):
    p = dict(year="甲子", month="丙寅", day="甲子", hour="甲子")
    p[target] = "甲寅" if target == "month" else "丙子"
    with pytest.raises(NumerologySourceError) as err:
        source.verified_computed_pillars(p)
    assert err.value.reason == "runtime_pillar_link_conflict"


@pytest.mark.parametrize(
    "change",
    [
        {"ruleset_id": "wrong"},
        {"month_branch_order": "子丑寅卯辰巳午未申酉戌亥"},
        {"month_heads": []},
        {"hour_heads": []},
    ],
)
def test_source_data_fault_is_rejected_before_comparison(tmp_path, monkeypatch, change):
    d = json.loads(source.SOURCE_PATH.read_text())
    d.update(change)
    p = tmp_path / "source.json"
    p.write_text(json.dumps(d))
    source._source.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(source, "SOURCE_PATH", p)
            with pytest.raises(NumerologySourceError):
                source.pillar_link_evidence(
                    dict(year="甲子", month="丙寅", day="甲子", hour="甲子")
                )
    finally:
        source._source.cache_clear()


def test_witnesses_and_prior_references_are_not_rewritten_to_make_links_match():
    for w in REFERENCE["witnesses"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    for p, h in REFERENCE["prior_reference_hashes"].items():
        assert hashlib.sha256((ROOT.parents[2] / p).read_bytes()).hexdigest() == h
    assert (
        REFERENCE["direct_formula_groups"] == 10
        and REFERENCE["derived_unique_valid_links"] == 240
    )
    assert (
        REFERENCE["new_complete_natal_examples"]
        == REFERENCE["new_independent_calendar_instants"]
        == REFERENCE["independent_second_reviews"]
        == 0
    )


def test_audit_cannot_erase_the_retained_original_conflict(monkeypatch):
    from scripts.numerology import audit_numerology as audit

    original = audit.pillar_link_evidence
    literal = REFERENCE["literal_source_conflict"]["pillars"]

    def hide_conflict(pillars):
        result = original(pillars)
        if list(pillars.values()) == literal:
            result["all_links_match"] = True
            result["links"][0]["expected_pillar"] = result["links"][0]["actual_pillar"]
            result["links"][0]["matches"] = True
        return result

    monkeypatch.setattr(audit, "pillar_link_evidence", hide_conflict)
    result = audit.pillar_link_source_checks()
    assert result["checks_passed"] is False
    assert {"kind": "retained_literal_pillar_link_conflict"} in result["failures"]

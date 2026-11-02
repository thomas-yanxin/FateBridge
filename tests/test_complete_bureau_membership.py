"""One source-checked repeated bureau plus explicit engineering generalizations."""

import hashlib
import itertools
import json
import math
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.complete_bureaus import complete_bureau_snapshot_lines
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_root_ledger import HiddenStemLedgerEntry
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate
from fatebridge.utils.data import STEM_ELEMENTS
from tests.test_strength_v2 import pillars, score

FOLDER = Path(__file__).parent / "fixtures/bazi_complete_bureau_v1"


def test_scanned_source_retains_one_complete_gold_bureau_with_two_roosters():
    raw = (FOLDER / "reference.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == (FOLDER / "reference.sha256").read_text().strip()
    )
    reference = json.loads(raw)
    assert (
        hashlib.sha256((FOLDER / "source-pages.pdf").read_bytes()).hexdigest()
        == reference["source"]["retained_pages_sha256"]
    )
    case = reference["case"]
    result = score(" ".join(case["pillars"]))
    events = [r for r in result["relations"] if r["kind"] == "三合"]
    assert len(events) == 1
    event = events[0]
    assert event["target"] == "金" and event["positions"] == [
        "year",
        "month",
        "day",
        "hour",
    ]
    assert event["status"] == "conditioned_transformation"
    assert event["membership_policy"] == "same_bureau_all_physical_positions_v1"
    assert not any(r["kind"] == "半合" for r in result["relations"])
    assert result["strength_level"] == case["explicit_strength"] == "弱"
    # The text says 全金局, not 80% transfer. These are declared policy receipts.
    fire = next(
        r
        for r in result["hidden_stem_ledger"]
        if r["pillar"] == "year" and r["stem"] == "丙"
    )
    assert fire["retention_fraction"] == pytest.approx(0.2)
    assert fire["combined_relation_loss_factor"] == 1
    assert result["root_qualifications"][0]["qualified_for_structural_rule"] is False
    assert "年支巳、月支酉、日支酉、时支丑" in "\n".join(
        complete_bureau_snapshot_lines(result)
    )


@pytest.mark.parametrize(
    "kind,group",
    [
        ("三合", "申子辰"),
        ("三合", "亥卯未"),
        ("三合", "寅午戌"),
        ("三合", "巳酉丑"),
        ("三会", "寅卯辰"),
        ("三会", "巳午未"),
        ("三会", "申酉戌"),
        ("三会", "亥子丑"),
    ],
)
def test_every_duplicate_member_is_one_physical_position_under_all_permutations(
    kind, group
):
    # Synthetic topology probes, never extra source examples or accuracy labels.
    for duplicate in group:
        for branches in set(itertools.permutations(group + duplicate)):
            chart = dict(
                zip(
                    ("year", "month", "day", "hour"),
                    [("甲", b) for b in branches],
                    strict=True,
                )
            )
            result = _evaluate(
                chart,
                ElementAnalysis.seasonal_phases(chart["month"][1]),
                DEFAULT_POLICY,
            )
            (event,) = [e for e in result["relations"] if e["kind"] == kind]
            assert len(event["positions"]) == len(set(event["positions"])) == 4
            assert event["status"] in {"binding", "conditioned_transformation"}
            assert not any(e["kind"] == "半合" for e in result["relations"])
            ledger = result["hidden_stem_ledger"]
            assert len({(r["pillar"], r["stem"]) for r in ledger}) == len(ledger)
            for position, budget in result["branch_budgets"].items():
                actual = sum(
                    r["remaining_mass"] for r in ledger if r["pillar"] == position
                )
                synthetic = sum(
                    r["mass"]
                    for r in result["combination_contributions"]
                    if r["pillar"] == position
                )
                assert math.isclose(
                    actual + synthetic, budget["remaining"], abs_tol=1e-12
                )
                assert budget["remaining"] <= budget["initial"] + 1e-12


def test_incompatible_different_relations_and_incomplete_shared_peak_stay_unresolved():
    # Full 寅午戌 and outside 戌卯六合 remain distinct relation claims.
    result = score("甲寅 丙午 戊戌 乙卯")
    full = next(e for e in result["relations"] if e["kind"] == "三合")
    assert full["status"] == "contested_or_clashed"
    half = score("甲辰 丁卯 甲子 戊辰")
    assert {e["status"] for e in half["relations"] if e["kind"] == "半合"} == {
        "contested"
    }


def test_synthetic_contributions_never_become_physical_stem_roots():
    # A smaller branch budget is a controlled engineering ablation. It exposes
    # activation differences hidden by saturation under the default policy.
    result = score("甲寅 丙午 丙辰 丁酉", branch_budget=0.5)
    ledger = result["hidden_stem_ledger"]
    assert all(row["stem"] is not None for row in ledger)
    assert result["combination_contributions"]
    for stem in result["revealed_stems"]:
        element = STEM_ELEMENTS[stem["stem"]][0]
        real = sum(r["remaining_mass"] for r in ledger if r["element"] == element.value)
        assert stem["root_mass"] == pytest.approx(real, abs=1e-6)
        assert (
            stem["root_activation_policy"] == "remaining_physical_hidden_stems_only_v1"
        )
    fire = next(r for r in result["revealed_stems"] if r["pillar"] == "month")
    assert fire["non_root_combination_mass"] > 0
    # 寅中丙 .5*2/7 plus 午中丁 (.5*2)*2/3 = 17/21;
    # .25 + .75*(17/21), times summer fire factor 2, is 12/7.
    assert fire["root_mass"] == pytest.approx(17 / 21, abs=1e-6)
    assert fire["energy"] == pytest.approx(12 / 7, abs=1e-6)


def test_body_and_seal_get_copied_surviving_roots_without_becoming_classical_labels():
    chart = pillars("辛巳 丁酉 丁酉 辛丑")
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    force = build_natal_evidence(chart, strength)["force_components"]
    actual = strength["assessment"]["hidden_stem_ledger"]
    for component in force["components"].values():
        roots = component["remaining_hidden_roots"]
        assert roots == [r for r in actual if r["element"] == component["element"]]
        for row in roots:
            HiddenStemLedgerEntry.model_validate(row)
    assert set(force["classical_adjudication"].values()) == {"not_adjudicated"}
    force["components"]["body"]["remaining_hidden_roots"][0]["remaining_mass"] = 999
    assert actual[0]["remaining_mass"] != 999
    absent = build_natal_evidence(chart)["force_components"]
    assert all(
        c["remaining_hidden_roots"] is None for c in absent["components"].values()
    )
    valid = deepcopy(actual[0])
    for change in [
        {"remaining_mass": valid["initial_mass"] + 1},
        {"retention_fraction": 1.0},
        {"remaining_mass": "0.1"},
        {"combined_relation_loss_factor": 0.1},
    ]:
        with pytest.raises(ValidationError):
            HiddenStemLedgerEntry.model_validate({**valid, **change})
    for fake in [
        {"initial_mass": 0.0, "remaining_mass": 0.0, "retention_fraction": 1.0},
        {"remaining_mass": 0.0, "engineering_energy": 2.0},
    ]:
        with pytest.raises(ValidationError):
            HiddenStemLedgerEntry.model_validate(fake)

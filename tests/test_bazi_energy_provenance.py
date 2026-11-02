"""Energy attribution is a native receipt, not a new classical strength verdict."""

import itertools
from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.energy_provenance import build_energy_provenance
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.output_energy_provenance import EnergyProvenance
from fatebridge.core.output_source_annotations import SourceCurrentCalculation


def assessment():
    return {
        "method_id": "fixture-method",
        "effective_elements_unrounded": {
            e: (3.0 if e == "水" else 0.0) for e in "木火土金水"
        },
        "threshold_arithmetic": {"day_element": "水"},
        "hidden_stem_ledger": [
            {"pillar": "year", "stem": "癸", "element": "水", "engineering_energy": 1.0}
        ],
        "combination_contributions": [
            {
                "pillar": "month",
                "element": "水",
                "origin": "fixture",
                "energy": 0.123457,
                "energy_unrounded": 0.123456789,
            }
        ],
        "stem_energy_accounting": {
            "ledger": [
                {"pillar": "hour", "effective_element": "水", "energy": 1.876543211}
            ]
        },
    }


def packet():
    a = assessment()
    return {
        "method_id": a["method_id"],
        "assessment": a,
        "energy_provenance": build_energy_provenance(a, "水"),
    }


def test_native_sources_close_without_changing_or_recomputing_input():
    a = assessment()
    original = deepcopy(a)
    p = build_energy_provenance(a, "水")
    assert a == original
    assert p["status"] == "complete"
    assert p["fronts"]["body"]["synthetic_branch"]["energy_unrounded"] == 0.123456789
    assert p["fronts"]["body"]["synthetic_branch"]["refs"] == [
        "combination_contributions:0"
    ]
    SourceCurrentCalculation.model_validate(packet())
    p["synthetic_contributions"][0]["mass"] = 9
    assert "mass" not in a["combination_contributions"][0]


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"element": None},
        {"element": "水", "pillar": "year"},
        {"element": "水", "pillar": "year", "energy_unrounded": float("nan")},
        {"element": "水", "pillar": "year", "energy_unrounded": -1.0},
    ],
)
def test_unknown_or_invalid_native_row_never_becomes_zero_or_rounded_energy(bad):
    a = assessment()
    a["combination_contributions"] = [bad]
    p = build_energy_provenance(a, "水")
    assert p["status"] == "partial"
    assert all(
        f["synthetic_branch"]["energy_unrounded"] is None for f in p["fronts"].values()
    )


@pytest.mark.parametrize(
    "kind",
    ["hidden_stem_ledger", "combination_contributions", "stem_energy_accounting"],
)
def test_missing_and_null_are_unknown_but_known_empty_is_zero(kind):
    for absent in (True, False):
        a = assessment()
        if absent:
            del a[kind]
        else:
            a[kind] = None
        assert build_energy_provenance(a, "水")["status"] == "partial"
    p = build_energy_provenance(
        {
            "hidden_stem_ledger": [],
            "combination_contributions": [],
            "stem_energy_accounting": {"ledger": []},
            "effective_elements_unrounded": {e: 0.0 for e in "木火土金水"},
        },
        "水",
    )
    assert p["status"] == "complete"
    assert all(
        f["total_energy_unrounded"] == 0 and f["attributed_energy_unrounded"] == 0
        for f in p["fronts"].values()
    )


@pytest.mark.parametrize(
    "fault",
    [
        "sum",
        "residual",
        "method",
        "day",
        "role",
        "refs",
        "copied_native",
        "redistribute",
        "duplicate_hidden",
        "visible_source",
    ],
)
def test_co_known_false_attribution_is_rejected_even_if_total_is_unchanged(fault):
    p = packet()
    q = p["energy_provenance"]
    f = q["fronts"]["body"]
    if fault == "sum":
        f["attributed_energy_unrounded"] += 1
    elif fault == "residual":
        f["residual"] = 0.1
    elif fault == "method":
        q["strength_method_id"] = "other"
    elif fault == "day":
        p["assessment"]["threshold_arithmetic"]["day_element"] = "火"
    elif fault == "role":
        f["element"] = "木"
    elif fault == "refs":
        f["physical_hidden"]["refs"] = []
    elif fault == "copied_native":
        q["synthetic_contributions"][0]["energy_unrounded"] += 1
    elif fault == "redistribute":
        f["physical_hidden"]["energy_unrounded"] -= 0.1
        f["non_day_visible"]["energy_unrounded"] += 0.1
    elif fault == "duplicate_hidden":
        f["physical_hidden"]["refs"] *= 2
    elif fault == "visible_source":
        p["assessment"]["stem_energy_accounting"]["ledger"][0]["energy"] += 0.1
    with pytest.raises(ValidationError):
        SourceCurrentCalculation.model_validate(p)


def test_natal_physical_and_visible_sources_are_bound_without_source_assessment():
    p = packet()
    chain = {
        "strength_context": {
            "method_id": "fixture-method",
            "stem_energy_accounting": p["assessment"]["stem_energy_accounting"],
        },
        "force_components": {
            "energy_provenance": p["energy_provenance"],
            "components": {
                "body": {
                    "element": "水",
                    "engineering_energy_unrounded": 3.0,
                    "remaining_hidden_roots": p["assessment"]["hidden_stem_ledger"],
                }
            },
        },
    }
    BaziEvidenceChain.model_validate(chain)
    # Move energy between real roots and visible stems while preserving the sum.
    front = chain["force_components"]["energy_provenance"]["fronts"]["body"]
    front["physical_hidden"]["energy_unrounded"] -= 0.1
    front["non_day_visible"]["energy_unrounded"] += 0.1
    with pytest.raises(ValidationError):
        BaziEvidenceChain.model_validate(chain)


def test_partial_field_combinations_preserve_missing_facts_and_valid_zero():
    full = packet()["energy_provenance"]
    paths = [
        ("fronts", "body", "physical_hidden"),
        ("fronts", "body", "total_energy_unrounded"),
        ("fronts", "body", "residual"),
        ("fronts", "body", "status"),
        ("day_element",),
        ("synthetic_contributions",),
    ]
    for flags in itertools.product([False, True], repeat=len(paths)):
        partial = {}
        for use, path in zip(flags, paths):
            if not use:
                continue
            source, target = full, partial
            for name in path[:-1]:
                source, target = source[name], target.setdefault(name, {})
            target[path[-1]] = deepcopy(source[path[-1]])
        model = EnergyProvenance.model_validate(partial)
        assert model.model_dump(exclude_unset=True) == partial


def test_nonclosing_supplied_values_are_reported_without_tuning_or_recalculation():
    a = assessment()
    a["effective_elements_unrounded"]["水"] += 0.1
    p = build_energy_provenance(a, "水")
    assert p["status"] == "partial"
    assert p["fronts"]["body"]["status"] == "not_closed"
    assert abs(p["fronts"]["body"]["residual"] - 0.1) < 1e-12
    # The diagnostic remains visible; it is not silently relabelled complete.
    EnergyProvenance.model_validate(p)

"""Printed original facts, explicit complete lookup and faithful public evidence."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.cli import run
from fatebridge.core.fengshui.xuankong import (
    _star_trace,
    natal_rules,
    validate_replacement_catalog,
)
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.validation.fengshui_replacement import audit_replacement_reference
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

FOLDER = Path(__file__).parent / "fixtures/fengshui_replacement_v1"
ORIGINAL = json.loads((FOLDER / "reference.json").read_text())
PRINTED = json.loads((FOLDER / "wang-numeric-reference.json").read_text())
EXPECTED = {
    name: group["star"] for group in ORIGINAL["groups"] for name in group["mountains"]
}


def request(angle=354):
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 7,
            "evidence": "原书数字例，不是真实房屋",
        },
    }


def test_all24_primary_rows_four_clauses_and_five_full_nine_palace_charts():
    result = audit_replacement_reference(ORIGINAL, PRINTED)
    assert result["scoped_acceptance_passed"]
    assert result["complete_table_entries"] == 24
    assert (
        result["changed_number_entries"] == 13 and result["same_number_entries"] == 11
    )
    assert (
        result["same_yuan_clauses"] == 4 and result["printed_numeric_components"] == 135
    )
    assert not result["whole_book_conformity_established"]
    for filename, digest in json.loads((FOLDER / "hashes.json").read_text()).items():
        assert hashlib.sha256((FOLDER / filename).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_complete_explicit_table_distinguishes_changed_and_same_star(name, expected):
    rules = natal_rules()
    physical = next(m for m in rules["mountains"] if m["name"] == name)
    original = rules["replacement_catalog"][name]["native_star_number"]
    # Non-five lookup has no date/period inference; seed and original same-yuan
    # mountain suffice. All contexts must produce the same mapped result.
    for period in range(1, 10):
        trace = _star_trace(original, physical, period, "replacement")
        assert trace["mapped_mountain"] == name
        assert trace["center_star_number"] == expected
        assert trace["polarity"] == physical["polarity"]
        assert trace["replacement_applied"] == (original != expected)
        decision = trace["replacement_lookup"]["decision"]
        assert decision == (
            "different_star_substituted"
            if original != expected
            else "same_star_explicitly_retained"
        )


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_same",
        "missing_changed",
        "wrong_native",
        "wrong_boolean",
        "bool_star",
        "out_of_range",
        "legacy_missing",
        "legacy_boolean",
        "extra_mountain",
    ],
)
def test_incomplete_or_conflicting_catalog_cannot_silently_fall_back(corruption):
    rules = natal_rules()
    if corruption == "missing_same":
        del rules["replacement_catalog"]["子"]
    elif corruption == "missing_changed":
        del rules["replacement_catalog"]["甲"]
    elif corruption == "wrong_native":
        rules["replacement_catalog"]["子"]["native_star_number"] = 8
    elif corruption == "wrong_boolean":
        rules["replacement_catalog"]["子"]["changes_number"] = True
    elif corruption == "bool_star":
        rules["replacement_catalog"]["子"]["replacement_star_number"] = True
    elif corruption == "out_of_range":
        rules["replacement_catalog"]["子"]["replacement_star_number"] = 5
    elif corruption == "legacy_missing":
        del rules["replacement_stars"]["甲"]
    elif corruption == "legacy_boolean":
        rules["replacement_stars"]["甲"] = True
    else:
        rules["mountains"].append(deepcopy(rules["mountains"][0]))
    with pytest.raises(ValueError):
        validate_replacement_catalog(rules)


def test_missing_or_mutated_independent_oracle_never_appears_as_acceptance():
    original = deepcopy(ORIGINAL)
    original["groups"][0]["mountains"] = "子癸甲"
    with pytest.raises(ValueError):
        audit_replacement_reference(original, PRINTED)
    printed = deepcopy(PRINTED)
    printed["cases"].pop()
    with pytest.raises(ValueError):
        audit_replacement_reference(ORIGINAL, printed)
    printed = deepcopy(PRINTED)
    printed["cases"][0]["palaces"]["N"].pop()
    with pytest.raises(ValueError):
        audit_replacement_reference(ORIGINAL, printed)
    printed = deepcopy(PRINTED)
    printed["cases"][0]["palaces"]["N"][0] = 1
    result = audit_replacement_reference(ORIGINAL, printed)
    assert (
        not result["scoped_acceptance_passed"] and result["printed_chart_disagreements"]
    )


def test_all_four_decisions_have_distinct_calculation_and_readable_evidence():
    found = set()
    for angle in [180, 354, 84, 309]:
        result = calculate_xuankong_natal(**request(angle))
        chart = result["layers"]["xuankong_natal"]["chart"]
        for trace in chart["trace"].values():
            lookup = trace["replacement_lookup"]
            found.add(lookup["decision"])
            assert lookup["selected_center_star_number"] == trace["center_star_number"]
            assert lookup["original_seed_star_number"] == trace["seed_star_number"]
            assert lookup["source_ids"] == ["X8", "X9"]
        assert "替星判断：" in result["snapshot_text"]
        assert "顺逆仍按原同元龙阴阳" in result["snapshot_text"]
    assert found == {
        "lower_chart_not_using_replacement",
        "five_yellow_has_no_substitute",
        "same_star_explicitly_retained",
        "different_star_substituted",
    }
    lower = calculate_xuankong_natal(**request(180))["layers"]["xuankong_natal"][
        "chart"
    ]
    trace = lower["trace"]["mountain"]
    assert (
        trace["replacement_lookup"]["catalog_star_number"]
        != trace["center_star_number"]
    )
    assert not trace["replacement_applied"]


@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_full_lookup_matches_rest_real_mcp_cli_and_keeps_primary_sources(
    monkeypatch, tmp_path, capsys, name
):
    data = request()
    if name == "assess":
        data = {"methods": ["xuankong_natal"], "xuankong": data}
    http = rest_client(monkeypatch).post("/api/fengshui/" + name, json=data)
    protocol = asyncio.run(mcp_call(name, data))
    path = tmp_path / "replacement.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_" + name, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    record = next(
        r for r in cli["rulesets"] if r["ruleset_id"] == "xuankong_zhongzhou_v1"
    )
    assert record["version"] == "1.4.0"
    assert {"X8", "X9"}.issubset({s["source_id"] for s in record["sources"]})


def test_strict_mcp_projection_retains_same_star_decision_and_original_polarity():
    result = asyncio.run(
        mcp_call(
            "xuankong_natal",
            {
                **request(309),
                "fields": [
                    "layers.xuankong_natal.chart.trace",
                    "rulesets",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error
    traces = result.structured_content["layers"]["xuankong_natal"]["chart"]["trace"]
    assert (
        traces["mountain"]["replacement_lookup"]["decision"]
        == "same_star_explicitly_retained"
    )
    assert (
        traces["facing"]["replacement_lookup"]["decision"]
        == "different_star_substituted"
    )
    assert traces["facing"]["polarity"] == "yang"

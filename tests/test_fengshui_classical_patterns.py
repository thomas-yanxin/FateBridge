"""Independent original lists and counterexamples separating three reference frames."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.cli import run
from fatebridge.core.fengshui.numeric_patterns import numeric_patterns
from fatebridge.core.fengshui.xuankong import _chart, natal_rules
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.validation.fengshui_patterns import audit_classical_patterns
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

FOLDER = Path(__file__).parent / "fixtures/fengshui_patterns_v1"
REFERENCE = json.loads((FOLDER / "reference.json").read_text())
NAMES = [m["name"] for m in natal_rules()["mountains"]]


def chart(period, facing, mode="lower"):
    return _chart(period, (NAMES.index(facing), mode, "numeric_test"))


def patterns(period, facing, mode="lower"):
    return chart(period, facing, mode)["structure"]["classical_patterns"]


def request(period=5, angle=225):
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": period,
            "evidence": "原典数字例，非实测住宅",
        },
    }


def test_complete216_domain_matches_original16_and28_lists_and_all_negative_cases():
    result = audit_classical_patterns(REFERENCE)
    assert result["scoped_acceptance_passed"]
    assert result["lower_chart_domain_checked"] == 216
    assert result["parental"]["actual_positive_cases"] == 16
    assert result["named_refrain"]["actual_positive_cases"] == 28
    assert result["parental"]["negative_cases_checked"] == 200
    assert result["named_refrain"]["negative_cases_checked"] == 188
    assert not result["whole_book_conformity_established"]
    for filename, digest in json.loads((FOLDER / "hashes.json").read_text()).items():
        assert hashlib.sha256((FOLDER / filename).read_bytes()).hexdigest() == digest


def test_five_period_named_fan_is_not_mislabelled_as_five_in_center_or_whole_reversal():
    c = chart(5, "坤")
    p = c["structure"]["classical_patterns"]
    assert p["parental_triples"]["all_nine_match"]
    assert p["volume_two_named_refrain"]["numeric_match"] is True
    assert p["volume_two_named_refrain"]["own_role_sitting_facing_both_opposite_ground"]
    assert all(c["trace"][r]["center_star_number"] != 5 for r in ["mountain", "facing"])
    assert not any(
        r["whole_ground_reverse"] or r["whole_ground_repeat"]
        for r in p["ground_comparison"]["roles"].values()
    )


def test_whole_reversal_does_not_automatically_enter_the_original_named_list():
    p = patterns(1, "午")
    assert p["ground_comparison"]["roles"]["facing"]["whole_ground_reverse"]
    assert not p["volume_two_named_refrain"]["numeric_match"]
    assert not p["parental_triples"]["all_nine_match"]


def test_literal_one_period_forward_five_example_matches_fixed_ground_in_every_palace():
    c = chart(1, "丙")
    p = c["structure"]["classical_patterns"]
    assert c["trace"]["facing"]["center_star_number"] == 5
    assert c["trace"]["facing"]["flight"] == "forward"
    assert p["ground_comparison"]["roles"]["facing"]["whole_ground_repeat"]
    assert p["volume_two_named_refrain"]["numeric_match"]


@pytest.mark.parametrize("period,expected", [(7, 8), (8, 9)])
def test_zu_mian_note_uses_period_overlap_not_fixed_ground_at_NW(period, expected):
    c = chart(period, "酉")
    p = c["structure"]["classical_patterns"]
    role = p["ground_comparison"]["roles"]["facing"]
    assert c["facing_chart"]["NW"] == c["period_chart"]["NW"] == expected
    assert "NW" in role["period_plate_same_directions"]
    assert "NW" not in role["same_ground_directions"]
    assert not role["whole_ground_repeat"]


def test_same_group_remainders_or_repeated_numbers_are_not_three_distinct_parent_stars():
    c = chart(5, "坤")
    c["mountain_chart"] = deepcopy(c["period_chart"])
    c["facing_chart"] = deepcopy(c["period_chart"])
    p = numeric_patterns(c)
    assert not p["parental_triples"]["all_nine_match"]
    assert all(
        row["matched_group"] is None
        for row in p["parental_triples"]["palaces"].values()
    )


@pytest.mark.parametrize(
    "corruption", ["missing_palace", "duplicate_flight", "boolean", "duplicate_star"]
)
def test_incomplete_plates_cannot_masquerade_as_complete_negative_comparisons(
    corruption,
):
    c = chart(5, "坤")
    if corruption == "missing_palace":
        del c["mountain_chart"]["N"]
    elif corruption == "duplicate_flight":
        c["flight_path"][0] = c["flight_path"][1]
    elif corruption == "boolean":
        c["mountain_chart"]["C"] = True
    else:
        c["mountain_chart"]["C"] = c["mountain_chart"]["N"]
    with pytest.raises(ValueError):
        numeric_patterns(c)


def test_replacement_does_not_inherit_the_literal_lower_chart_case_verdict():
    p = patterns(5, "坤", "replacement")
    assert p["volume_two_named_refrain"]["applicable"] is False
    assert p["volume_two_named_refrain"]["numeric_match"] is None
    assert p["ground_comparison"]["reference_numbers"]["NW"] == 6


def test_readable_snapshot_preserves_local_period_overlap_when_whole_plate_flags_are_false():
    result = calculate_xuankong_natal(**request(period=7, angle=270))
    lines = [
        line
        for line in result["snapshot_text"].splitlines()
        if line.startswith("facing 固定地盘")
    ]
    assert len(lines) == 1
    assert "与历史运盘全盘同数：False" in lines[0]
    assert "与历史运盘同数宫位：NW" in lines[0]


def test_reference_audit_rejects_dropped_rows_and_retains_valid_mutations_as_disagreements():
    r = deepcopy(REFERENCE)
    r["parental_triples"]["families"][0]["periods"].pop()
    with pytest.raises(ValueError):
        audit_classical_patterns(r)
    r = deepcopy(REFERENCE)
    r["named_refrain_examples"]["families"][0]["facing_mountains"] = "壬壬"
    with pytest.raises(ValueError):
        audit_classical_patterns(r)
    r = deepcopy(REFERENCE)
    r["named_refrain_examples"]["families"][0]["facing_mountains"] = "子丙"
    result = audit_classical_patterns(r)
    assert not result["scoped_acceptance_passed"]
    assert result["named_refrain"]["symmetric_differences"]


@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_new_patterns_match_rest_real_mcp_and_cli_with_sources(
    monkeypatch, tmp_path, capsys, name
):
    data = request()
    if name == "assess":
        data = {"methods": ["xuankong_natal"], "xuankong": data}
    http = rest_client(monkeypatch).post("/api/fengshui/" + name, json=data)
    protocol = asyncio.run(mcp_call(name, data))
    path = tmp_path / "patterns.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_" + name, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert "全局父母三般卦数字条件：True" in cli["snapshot_text"]
    assert {"X10", "X11"}.issubset(set(cli["rulesets"][0]["source_ids"]))


def test_real_mcp_projection_keeps_complete_numeric_reference_frames():
    result = asyncio.run(
        mcp_call(
            "xuankong_natal",
            {
                **request(),
                "fields": [
                    "layers.xuankong_natal.chart.structure.classical_patterns",
                    "rulesets",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error
    p = result.structured_content["layers"]["xuankong_natal"]["chart"]["structure"][
        "classical_patterns"
    ]
    assert p["parental_triples"]["all_nine_match"]
    assert p["volume_two_named_refrain"]["numeric_match"]
    assert len(p["ground_comparison"]["reference_numbers"]) == 9

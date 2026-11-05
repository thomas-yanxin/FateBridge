"""The physical join must retain source paths, center and unresolved lodgings."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.sanshi_correspondences import (
    PHYSICAL,
    palace_correspondences,
)
from fatebridge.core.output_sanshi import SanshiSynthesis
from fatebridge.services.divination import calculate_sanshiunited_analysis


@pytest.fixture(scope="module")
def result():
    return calculate_sanshiunited_analysis(
        date="2026-06-21",
        time="17:00:02",
        zone="Asia/Shanghai",
        use_true_solar_time=False,
        taiyi_options={"calculation_mode": "hour"},
    )


def resolve(root, path):
    for key in path.split("."):
        root = root[int(key)] if isinstance(root, list) else root[key]
    return root


def test_every_join_fact_reads_the_same_actual_boards(result):
    synthesis = result["synthesis"]
    SanshiSynthesis.model_validate(synthesis)
    joined = synthesis["palace_correspondences"]
    assert len(joined["entries"]) == 5
    assert joined["joint_judgment"] == "not_implemented"
    for row in joined["entries"]:
        assert resolve(result, row["taiyi_source_path"]) == row["taiyi_number"]
        qp = resolve(result, row["qimen"]["source_path"])
        assert all(
            qp[key] == value
            for key, value in row["qimen"].items()
            if key != "source_path"
        )
        lr = row["liureng"]
        if lr["status"] == "direct_branch_match":
            actual = resolve(result, lr["source_path"])
            assert all(
                actual[key] == lr[key] for key in ("earth_branch", "sky_branch", "god")
            )
            assert actual["earth_branch"] == row["taiyi_palace"]
        else:
            assert lr["status"] == "not_assessed" and lr["reason"]
    assert "[三式宫位对应]" in result["snapshot_text"]
    exported = next(
        s for s in result["snapshot_export"]["sections"] if s["title"] == "三式宫位对应"
    )
    assert exported["included"] is True and "太乙" in exported["content"]
    for profiles in synthesis["source_profiles"].values():
        for profile in profiles:
            original = resolve(result, profile["source_path"])
            assert profile["unresolved_count"] == len(original.get("unresolved", []))
            for key, value in profile.items():
                if key not in {"source_path", "source_title", "unresolved_count"}:
                    assert original[key] == value
            assert profile["source_title"] == original.get(
                "source_title", original.get("title", "")
            )


@pytest.mark.parametrize(
    "taiyi_number,trigram,qimen_number",
    [
        (1, "乾", 6),
        (2, "离", 9),
        (3, "艮", 8),
        (4, "震", 3),
        (5, "中", 5),
        (6, "兑", 7),
        (7, "坤", 2),
        (8, "坎", 1),
        (9, "巽", 4),
    ],
)
def test_all_nine_positions_do_not_reuse_taiyi_number(
    result, taiyi_number, trigram, qimen_number
):
    taiyi = deepcopy(result["taiyi"])
    taiyi["core_board"]["main_general"] = taiyi_number
    rows = palace_correspondences(taiyi, result["qimen"], result["liureng"])["entries"]
    row = next(r for r in rows if r["marker"] == "主大将")
    assert row["qimen"]["index"] == qimen_number
    assert row["trigram"] == trigram
    if taiyi_number in {1, 3, 7, 9, 5}:
        assert row["liureng"]["status"] == "not_assessed"
    else:
        assert row["liureng"]["status"] == "direct_branch_match"
    if taiyi_number == 5:
        assert row["taiyi_palace"] == "中" and row["qimen"]["trigram"] == "中"
        assert row["qimen"]["star"] is None  # No invented center star/god.


@pytest.mark.parametrize("failure", ["duplicate", "trigram"])
def test_missing_or_displaced_physical_palace_cannot_silently_join(result, failure):
    qimen = deepcopy(result["qimen"])
    number = PHYSICAL[result["taiyi"]["core_board"]["taiyi_number"]][1]
    palace = next(p for p in qimen["palaces"] if p["index"] == number)
    if failure == "duplicate":
        qimen["palaces"].append(palace)
    else:
        palace["trigram"] = "错误方位"
    with pytest.raises(ValueError, match="唯一且同方位"):
        palace_correspondences(result["taiyi"], qimen, result["liureng"])


def test_public_join_contract_rejects_numerical_facts_as_strings():
    with pytest.raises(ValidationError):
        SanshiSynthesis.model_validate(
            {"palace_correspondences": {"entries": [{"taiyi_number": "1"}]}}
        )


def test_source_profiles_resolve_in_the_current_default_year_calculation():
    # Keep the fictional request; retire its rejected accNum=0 placeholder.
    result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lon="121e28",
        lat="31n13",
        use_true_solar_time=True,
        liureng_guiren_profile="liuren_common_v1",
        liureng_is_diurnal=False,
        liureng_yue="申",
        qimen_options={"layout": "direct"},
    )
    assert result["taiyi"]["calendar_summary"]["calculation_mode"] == "year"
    assert {"qimen", "liureng"} <= result["synthesis"]["source_profiles"].keys()
    for profiles in result["synthesis"]["source_profiles"].values():
        assert profiles
        for profile in profiles:
            original = resolve(result, profile["source_path"])
            assert profile["unresolved_count"] == len(original.get("unresolved", []))
            for key, value in profile.items():
                if key not in {"source_path", "source_title", "unresolved_count"}:
                    assert original[key] == value

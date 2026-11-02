"""Whole declared-month table comparison; no fifth state or new predictions."""

import hashlib
import json
from copy import deepcopy

import pytest

from fatebridge.core.meihua_volume5_strength import (
    build_volume5_strength_comparison,
    volume5_strength_ruleset,
)
from fatebridge.services.meihua import calculate_meihua_cast
from tests.meihua_volume5_strength_reference import FOLDER, load

CELLS, EXPECTED = load()
BY_GEOMETRY = {}
for row in EXPECTED:
    BY_GEOMETRY.setdefault((row["code"], row["line"]), []).append(row)


def resolve(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def test_original_table_has_only_twenty_printed_cells_and_five_unlisted_combinations():
    profile = volume5_strength_ruleset()
    assert profile == json.loads((FOLDER / "profile.json").read_bytes())
    assert list(profile["rows"]) == ["旺", "相", "休", "囚"]
    assert "死" not in profile["rows"] and not profile["complete_five_state_table"]
    assert profile["source"]["zero_based_pdf_indices"] == [202, 203]
    assert {
        r["column"]: r["element"] for r in CELLS if r["expected_state"] is None
    } == {"春": "金", "夏": "水", "秋": "火", "冬": "土", "四季之月": "木"}


@pytest.mark.parametrize("geometry", list(BY_GEOMETRY), ids=lambda g: str(g))
def test_all_existing_geometries_and_thirteen_declared_month_contexts(geometry):
    for expected in BY_GEOMETRY[geometry]:
        out = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": expected["code"],
                "moving_line": expected["line"],
            },
            season_month_branch=expected["month"],
        )
        assert "error" not in out, out
        q = out["interpretation"]["seasonal_qualification"]
        layer = q["volume5_table_comparison"]
        assert layer["table_column"] == expected["expected_column"]
        assert layer["month_branch"] == expected["month"]
        assert len(layer["roles"]) == 5
        for row, old in zip(layer["roles"], expected["roles"], strict=True):
            assert (row["role"], row["trigram"], row["element"]) == (
                old["role"],
                old["trigram"],
                old["element"],
            )
            assert row["table_state"] == old["expected_table_state"]
            assert row["status"] == old["expected_status"]
            assert row["primary_strength"] == old["strength"]
            assert row["primary_strength_fact_path"] == old["strength_fact_path"]
            assert resolve(out, row["trigram_fact_path"])["name"] == row["trigram"]
            if row["table_state"] is not None:
                assert resolve(layer, row["table_cell_relative_path"]) == row["element"]
            else:
                assert row["table_cell_relative_path"] is None
        assert not layer["used_to_override_primary_strength"]
        assert not layer["governing_body_use_method_adjudicated"]
        assert (
            layer["complete_year_month_day_strength_synthesis"]
            is layer["net_verdict"]
            is layer["event_time"]
            is layer["real_outcome"]
            is layer["success_probability"]
            is None
        )
        del q["volume5_table_comparison"]
        assert digest(out) == expected["before_complete_output_sha256"]


def test_each_actual_counting_candidate_uses_its_own_body_and_evidence_paths():
    out = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        },
        season_month_branch="申",
    )
    assert "error" not in out, out
    for i, candidate in enumerate(out["interpretation"]["casting_readings"]):
        layer = candidate["seasonal_qualification"]["volume5_table_comparison"]
        assert layer["roles"][0]["trigram"] == candidate["body"]
        for row in layer["roles"]:
            assert resolve(out, row["trigram_fact_path"])["name"] == row["trigram"]
            assert row["primary_strength_fact_path"].startswith(
                f"interpretation.casting_readings.{i}."
            )


def test_returned_source_table_cannot_poison_the_next_call():
    first = volume5_strength_ruleset()
    first["rows"]["囚"][0] = "金"
    assert volume5_strength_ruleset()["rows"]["囚"][0] == "土"


@pytest.mark.parametrize(
    "mutation",
    [
        "role_order",
        "missing_role",
        "month",
        "season",
        "trigram",
        "primary_strength",
        "missing_month_strength",
    ],
)
def test_comparison_rejects_mixed_cast_or_month_inputs(mutation):
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "010000", "moving_line": 1},
        season_month_branch="申",
    )
    roles = deepcopy(out["interpretation"]["seasonal_qualification"]["roles"])
    seasonal = deepcopy(out["meihua"]["seasonal_strength"])
    if mutation == "role_order":
        roles.reverse()
    elif mutation == "missing_role":
        roles.pop()
    elif mutation == "month":
        seasonal["month_branch"] = "?"
    elif mutation == "season":
        seasonal["season"] = "冬"
    elif mutation == "trigram":
        roles[0]["trigram"] = "离"
    elif mutation == "primary_strength":
        roles[0]["strength"] = "旺"
    else:
        seasonal = None
    with pytest.raises(ValueError):
        build_volume5_strength_comparison(roles, seasonal)


def test_missing_month_does_not_infer_a_season_from_labels_or_question():
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "010000", "moving_line": 1},
        question="夏季，午月，土旺",
    )
    layer = out["interpretation"]["seasonal_qualification"]["volume5_table_comparison"]
    assert layer["table_column"] is layer["month_branch"] is None
    assert {r["status"] for r in layer["roles"]} == {"month_not_supplied"}
    assert all(r["table_state"] is None for r in layer["roles"])

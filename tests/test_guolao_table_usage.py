"""Conditional context is never an accepted coordinate or a changed raw cell."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import fatebridge.core.guolao_table_usage as module
from fatebridge.core.guolao_nijl_grid import compare_intro_examples, literal_cell

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-table-usage-v1"
REFERENCE = "039c00fc3a036ef94b14493c9f7283f667a0d2114934bab34c945c79ab72e746"


def test_held_originals_native_pixel_views_and_complete_prior_probe_are_bound():
    raw = (FIXTURE / "reference-complete-labels-before-domain-change.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REFERENCE
    data = module._data()
    assert data["independent_token_reference_sha256"] == REFERENCE
    for source in data["sources"]:
        assert (
            hashlib.sha256((ROOT / source["source_file"]).read_bytes()).hexdigest()
            == source["source_sha256"]
        )
    views = json.loads((FIXTURE / "reading-views.json").read_text())
    assert len(views["views"]) == 7
    for view in views["views"]:
        assert (
            hashlib.sha256((FIXTURE / view["file"]).read_bytes()).hexdigest()
            == view["sha256"]
        )
        assert (
            hashlib.sha256((ROOT / view["source_file"]).read_bytes()).hexdigest()
            == view["source_sha256"]
        )
        assert view["no_resampling"]
        if view["file"].startswith("ma591"):
            assert view["source_pixels"] == [2342, 1660]
            assert "国文学研究資料館提供" not in view["credit"]
        else:
            assert view["source_pixels"] == [5856, 4032]
            assert "国文学研究資料館提供" in view["credit"]


def test_all360_contexts_match_prior_token_probe_without_mutating_raw_cells():
    reference = json.loads(
        (FIXTURE / "reference-complete-labels-before-domain-change.json").read_text()
    )
    result = module.conditional_contexts(context_policy=module.POLICY)
    assert len(result["cells"]) == 360
    for row, held in zip(
        result["cells"], reference["all360_context_cells"], strict=True
    ):
        assert (row["palace"], row["column"]) == (held["palace"], held["column"])
        assert row["literal_label"] == held["literal_label_value"]
        context = row["candidate_context"]
        assert context["mansion"] == held["candidate_mansion_context"]
        assert context["anchor_column"] == held["anchor_column"]
        assert (
            context["mansion_printed_at_this_cell"]
            == held["source_marker_printed_here"]
        )
        assert context["conditional"] and not context["original_usage_adjudicated"]
        raw = literal_cell(palace=row["palace"], column=row["column"])["cell"]
        assert row["source_cell"] == raw
        assert raw["inherited_mansion"] is None
        assert raw["continuous_historical_degree"] is None
        assert raw["modern_longitude"] is None


@pytest.mark.parametrize(
    "mansion,label,numeral_columns,column,anchor",
    [("虚", 6, [6, 15, 26], 15, 12), ("女", 3, [9, 18, 29], 29, 21)],
)
def test_all_source_numerals_are_kept_before_context_restricts_the_candidates(
    mansion, label, numeral_columns, column, anchor
):
    result = module.locate_label(
        palace="子", mansion=mansion, label=label, context_policy=module.POLICY
    )
    assert result["numeral_only_columns"] == numeral_columns
    assert [r["column"] for r in result["candidates"]] == [column]
    assert result["candidates"][0]["candidate_context"]["anchor_column"] == anchor
    assert result["unique_candidate"] and result["selected_candidate"] is None
    assert not result["target_based_ranking"]


def test_both_original_numeric_counterexamples_survive_source_label_location():
    before = compare_intro_examples()
    result = module.audit_intro_usage(context_policy=module.POLICY)
    assert result["existing_literal_comparison"] == before
    assert [c["example"]["id"] for c in result["cases"]] == [
        "luwei_xu6_xing5",
        "luwei_nv3_liu4",
    ]
    assert [
        c["previous_column_is_the_unique_conditional_candidate"]
        for c in result["cases"]
    ] == [True, True]
    assert all(
        c["all_candidate_targets_are_numeric_counterexamples"] for c in result["cases"]
    )
    assert [
        c["same_column_targets"][0]["target_explicit_mansion_match"]
        for c in result["cases"]
    ] == [True, None]
    assert [
        c["same_column_targets"][0]["target_conditional_mansion_context_match"]
        for c in result["cases"]
    ] == [True, True]
    note = result["ma591_note_scope"]
    assert note["palaces"] == ["亥", "戌", "酉", "申", "未", "卯"]
    assert not note["only_listed_palace_correction_would_affect_these_cases"]
    assert not note["note_applied_to_nijl_grid"]
    assert not result["native_life_degree_accepted"]
    assert not result["original_usage_adjudicated"]
    assert result["real_world_prediction_cases"] == 0
    assert compare_intro_examples() == before


def test_an_initial_target_is_unknown_numeric_semantics_not_a_known_counterexample(
    monkeypatch,
):
    rows = copy.deepcopy(module._contexts())
    target = next(r for r in rows if (r["palace"], r["column"]) == ("午", 15))
    target["literal_label"] = "初"
    monkeypatch.setattr(module, "_contexts", lambda: rows)
    case = module.audit_intro_usage(context_policy=module.POLICY)["cases"][0]
    assert case["same_column_targets"][0]["target_numeric_label_match"] is None
    assert not case["all_candidate_targets_are_numeric_counterexamples"]


def test_no_source_candidate_is_not_a_vacuous_success_or_a_default_column(monkeypatch):
    rows = [r for r in module._contexts() if (r["palace"], r["column"]) != ("子", 15)]
    monkeypatch.setattr(module, "_contexts", lambda: rows)
    case = module.audit_intro_usage(context_policy=module.POLICY)["cases"][0]
    assert case["source_lookup"]["candidates"] == []
    assert case["source_lookup"]["status"] == "no_literal_candidate"
    assert case["same_column_targets"] == []
    assert not case["all_candidate_targets_are_numeric_counterexamples"]
    assert not case["previous_column_is_the_unique_conditional_candidate"]


def test_multiple_conditional_source_positions_are_retained_without_target_ranking(
    monkeypatch,
):
    rows = copy.deepcopy(module._contexts())
    extra = next(r for r in rows if (r["palace"], r["column"]) == ("子", 16))
    extra["literal_label"] = 6
    monkeypatch.setattr(module, "_contexts", lambda: rows)
    case = module.audit_intro_usage(context_policy=module.POLICY)["cases"][0]
    assert [c["column"] for c in case["source_lookup"]["candidates"]] == [15, 16]
    assert not case["source_lookup"]["unique_candidate"]
    assert case["source_lookup"]["selected_candidate"] is None
    assert [t["target_numeric_label_match"] for t in case["same_column_targets"]] == [
        False,
        True,
    ]
    assert not case["all_candidate_targets_are_numeric_counterexamples"]


@pytest.mark.parametrize(
    "palace,mansion,column",
    [("辰", "氐", 1), ("申", "觜", 19), ("亥", "奎", 1)],
)
def test_initial_queries_retain_the_initial_glyph_without_zero(palace, mansion, column):
    result = module.locate_label(
        palace=palace, mansion=mansion, label="初", context_policy=module.POLICY
    )
    assert [c["column"] for c in result["candidates"]] == [column]
    assert result["candidates"][0]["literal_label"] == "初"
    assert not result["initial_converted_to_zero"]


@pytest.mark.parametrize("bad", [None, "", "default", "accepted"])
def test_policy_is_required_and_cannot_be_upgraded_to_an_accepted_method(bad):
    with pytest.raises(ValueError, match="假设"):
        module.conditional_contexts(context_policy=bad)


@pytest.mark.parametrize(
    "change",
    [
        dict(palace="子丑"),
        dict(palace=None),
        dict(mansion="unknown"),
        dict(label=True),
        dict(label=0),
        dict(label=31),
        dict(label=1.0),
        dict(label="6"),
    ],
)
def test_inputs_never_round_alias_or_guess_source_labels(change):
    args = dict(palace="子", mansion="虚", label=6, context_policy=module.POLICY)
    with pytest.raises(ValueError):
        module.locate_label(**{**args, **change})


def test_changed_usage_notes_and_changed_bound_grid_are_rejected(monkeypatch, tmp_path):
    changed = json.loads(module.DATA.read_text())
    changed["ma591_note_palaces"].append("午")
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed))
    monkeypatch.setattr(module, "DATA", path)
    with pytest.raises(ValueError, match="指纹"):
        module.audit_intro_usage(context_policy=module.POLICY)
    changed["source_grid_id"] = "another-witness"
    path.write_text(json.dumps(changed))
    monkeypatch.setattr(
        module, "DATA_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="同一NIJL"):
        module.audit_intro_usage(context_policy=module.POLICY)


@pytest.mark.parametrize(
    "arguments,valid",
    [
        ([], False),
        (["--context-policy", module.POLICY], True),
        (["--context-policy", module.POLICY, "--all-contexts"], True),
        (
            [
                "--context-policy",
                module.POLICY,
                "--palace",
                "子",
                "--mansion",
                "虚",
                "--label",
                "6",
            ],
            True,
        ),
        (
            [
                "--context-policy",
                module.POLICY,
                "--palace",
                "亥",
                "--mansion",
                "奎",
                "--label",
                "初",
            ],
            True,
        ),
        (["--context-policy", module.POLICY, "--palace", "子"], False),
        (
            [
                "--context-policy",
                module.POLICY,
                "--palace",
                "子",
                "--mansion",
                "虚",
                "--label",
                "6",
                "--all-contexts",
            ],
            False,
        ),
        (
            [
                "--context-policy",
                module.POLICY,
                "--palace",
                "子",
                "--mansion",
                "虚",
                "--label",
                "6.0",
            ],
            False,
        ),
    ],
)
def test_actual_cli_requires_explicit_policy_and_retains_same_import_tree(
    arguments, valid
):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_guolao_table_usage.py"), *arguments],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is valid
    if valid:
        assert json.loads(result.stdout)["original_usage_adjudicated"] is False
    else:
        assert not result.stdout and result.stderr

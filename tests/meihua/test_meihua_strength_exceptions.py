"""Literal source and all reused geometry/month contexts, without forecasts."""

import asyncio
import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua_strength_exceptions import (
    _auxiliary_clause_applicability,
    build_strength_exceptions,
    strength_exception_ruleset,
)
from fatebridge.services.meihua import calculate_meihua_cast
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_strength_exceptions_v1"
GEOMETRIES = json.loads((FIXTURE / "geometry384-reused.json").read_text())
EXPECTED = json.loads(gzip.decompress((FIXTURE / "expected.json.gz").read_bytes()))[
    "cases"
]
ROLE_TRUTH = json.loads((FIXTURE / "role-prerequisites.json").read_text())["rows"]
BY_GEOMETRY = {(c["code"], c["line"]): [] for c in GEOMETRIES}
for row in EXPECTED:
    BY_GEOMETRY[row["code"], row["line"]].append(row)


def resolve(out, path):
    for part in path.split("."):
        out = out[int(part)] if isinstance(out, list) else out[part]
    return out


def test_source_profile_and_references_remain_the_preedit_selected_reading():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert m["preimplementation"] and not m["production_generated_expected"]
    assert m["derived_reference_checks"] == len(EXPECTED) == 4992
    for name, sha in m["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    assert strength_exception_ruleset() == json.loads(
        (FIXTURE / "profile.json").read_text()
    )
    supplement = json.loads(
        (FIXTURE / "eligibility-reference-supplement.json").read_text()
    )
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == supplement["original_reference_manifest_sha256"]
    )
    for name, sha in supplement["new_reference_files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha


@pytest.mark.parametrize("row", ROLE_TRUTH)
def test_known_attacking_relation_rules_out_favorable_clause_even_if_strength_unknown(
    row,
):
    assert _auxiliary_clause_applicability(row["strength"], row["attacking"]) == {
        key: row[key]
        for key in ["favorable_clause_applies", "attacker_wang_exception_applies"]
    }


@pytest.mark.parametrize("case", GEOMETRIES, ids=lambda c: f"{c['code']}-{c['line']}")
def test_all_384_geometries_under_thirteen_frozen_month_contexts(case):
    for expected in BY_GEOMETRY[case["code"], case["line"]]:
        out = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": case["code"],
                "moving_line": case["line"],
            },
            season_month_branch=expected["month"],
        )
        assert "error" not in out, out
        q = out["interpretation"]["seasonal_qualification"]
        layer = q["volume3_qualification"]
        assert [r["strength"] for r in q["roles"]] == expected["strengths"]
        assert layer["original_body"] == q["roles"][0]
        assert [r["status"] for r in layer["condition_checks"]] == expected[
            "body_condition_statuses"
        ]
        assert [r["status"] for r in layer["auxiliary_checks"]] == expected[
            "auxiliary_statuses"
        ]
        for row, source in zip(layer["auxiliary_checks"], q["roles"][1:], strict=True):
            assert row["role"] == source["role"]
            assert row["relation_to_body"] == source["relation_to_body"]
            assert resolve(out, row["fact_path"])["name"] == row["trigram"]
            assert resolve(out, row["relation_fact_path"]) == row["relation_to_body"]
            if row["strength_fact_path"] is not None:
                assert resolve(out, row["strength_fact_path"]) == row["strength"]
            assert row["effect_after_all_controls"] is None
            truth = next(
                r
                for r in ROLE_TRUTH
                if r["attacking"] is (row["relation_to_body"] == "用克体")
                and r["strength"] == row["strength"]
            )
            assert row["favorable_clause_applies"] is truth["favorable_clause_applies"]
            assert (
                row["attacker_wang_exception_applies"]
                is truth["attacker_wang_exception_applies"]
            )
        assert (
            layer["event_time"]
            is layer["real_outcome"]
            is layer["net_verdict"]
            is layer["success_probability"]
            is None
        )
        assert not layer["predictive_efficacy_established"]


@pytest.mark.parametrize(
    "topic",
    ["general", "planning", "reputation", "wealth", "transaction", "travel", "meeting"],
)
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_each_counting_candidate_keeps_own_body_exception_and_qualifications(
    topic, basis
):
    out = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        season_month_branch="午",
        interpretation_topic=topic,
    )
    for candidate in out["interpretation"]["casting_readings"]:
        q = candidate["seasonal_qualification"]
        layer = q["volume3_qualification"]
        assert layer["original_body"]["trigram"] == candidate["body"]
        assert layer["original_body"]["fact_path"].startswith(
            candidate["fact_prefix"] + "."
        )
        for row, qualification in zip(
            layer["auxiliary_checks"],
            candidate["internal_countercontrol"]["qualifications"],
            strict=True,
        ):
            assert row["internal_control_qualification"] == qualification
            assert resolve(out, row["strength_fact_path"]) == row["strength"]
        if candidate["body"] == "乾":
            assert (
                layer["auxiliary_checks"][0]["status"]
                == "excluded_by_attacker_exception"
            )
            assert "不引用乘旺皆吉" in layer["summary"]


def test_outer_support_is_not_denied_or_synthesized_by_a_month_internal_layer():
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "010111", "moving_line": 4},
        season_month_branch="午",
        external_observations=[
            {"manifestation": "actual_water", "label": "虚构已报外应，仅作工程诊断"}
        ],
    )
    assert out["interpretation"]["external_omens"]["observations"]
    for row in out["interpretation"]["seasonal_qualification"]["volume3_qualification"][
        "unresolved_source_clauses"
    ]:
        assert row["full_clause_applies"] is row["external_support_or_absence"] is None
        assert row["external_status"] == "not_adjudicated_by_this_month_internal_layer"


@pytest.mark.parametrize(
    "part", ["body", "role", "relation", "qualification", "unknown_strength"]
)
def test_mismatched_contexts_and_invented_strength_labels_are_rejected(part):
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "011010", "moving_line": 5},
        season_month_branch="申",
    )
    roles = copy.deepcopy(out["interpretation"]["seasonal_qualification"]["roles"])
    control = copy.deepcopy(out["interpretation"]["internal_countercontrol"])
    if part == "body":
        roles[0]["trigram"] = "乾"
    elif part == "role":
        roles[1]["fact_path"] = "another_cast.use_trigram"
    elif part == "relation":
        roles[1]["relation_to_body"] = "用克体"
    elif part == "qualification":
        control["qualifications"][0]["target_fact_path"] = "another_cast.use_trigram"
    else:
        roles[0]["strength"] = "中性"
    with pytest.raises(ValueError):
        build_strength_exceptions(roles, control)


def test_weather_remains_without_body_use_strength_qualification():
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "011010", "moving_line": 5},
        interpretation_topic="weather",
    )
    assert out["interpretation"]["seasonal_qualification"] is None


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_strength_card_agrees_on_rest_mcp_cli(tool, rest, tmp_path, capsys):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    args = (
        {
            "casting": {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "子",
            },
            "season_month_branch": "午",
        }
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        }
    )
    fields = suggested_fields(spec, view="strength_audit")
    response = rest.post(
        spec.rest_path,
        json=args,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    mcp = asyncio.run(
        native(
            spec, args, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    code, cli = call_cli(
        spec,
        args,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )

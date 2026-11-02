"""Primary printed day labels and own-body day/month source qualifications."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua_day_qi import civil_day_qi_context, day_qi_ruleset
from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.meihua_volume5_source_evolution import (
    reviewed_restore_old_time_fixture_view as restore_old_time_fixture_view,
)

FIXTURE = Path(__file__).parent / "fixtures/meihua_day_qi_v1"
PRINTED = json.loads((FIXTURE / "printed-day-labels60.json").read_text())
TABLE = json.loads((FIXTURE / "branch-strength-and-relations.json").read_text())
GEOMETRY = json.loads((FIXTURE / "geometry384-reused.json").read_text())
TIMES = json.loads((FIXTURE / "time-boundaries12.json").read_text())
OLD_TIMES = json.loads((FIXTURE / "old-time-outputs12.json").read_text())
TOPICS = [
    "general",
    "planning",
    "reputation",
    "wealth",
    "transaction",
    "travel",
    "meeting",
]
BRANCHES = list(TABLE["branch_element_wang_shuai"])


def cast_for(case):
    return {
        "method": "existing",
        "hexagram_code": case["code"],
        "moving_line": case["line"],
    }


def context(branch):
    return {"label": "虚构已报日支工程示例", "day_branch": branch}


def at_path(output, path):
    result = output
    for part in path.split("."):
        result = result[int(part)] if isinstance(result, list) else result[part]
    return result


def test_primary_source_and_expected_tables_frozen_before_implementation():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert not m["implementation_present_at_reference_freeze"]
    assert not m["expected_values_from_production"]
    assert m["primary_printed_calendar_cells"] == 60
    for name, digest in m["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert len({row["ganzhi"] for row in PRINTED}) == 60


@pytest.mark.parametrize("row", PRINTED, ids=lambda row: row["date"])
def test_all_sixty_printed_cells_not_a_production_generated_reference(row):
    c = civil_day_qi_context(
        datetime.fromisoformat(row["date"] + "T12:00"), bazi_day_ganzhi=row["ganzhi"]
    )
    assert c["candidates"][0]["ganzhi"] == row["ganzhi"]
    assert c["candidates"][0]["day_branch"] == row["ganzhi"][1]
    assert len(c["candidates"]) == 1


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("branch", BRANCHES)
def test_all_twelve_day_branches_on_all_human_branches(branch, topic):
    out = calculate_meihua_cast(
        casting=cast_for(GEOMETRY[0]),
        interpretation_topic=topic,
        day_qi_context=context(branch),
        season_month_branch="申",
    )
    assert "error" not in out
    layer = out["interpretation"]["day_qi"]
    row = layer["calendar_candidates"][0]
    assert (row["day_element"], row["wang_element"], row["shuai_element"]) == tuple(
        TABLE["branch_element_wang_shuai"][branch]
    )
    assert not row["day_element_is_a_unique_trigram"]
    assert at_path(out, row["day_branch_fact_path"]) == branch
    for node in row["roles"]:
        assert at_path(out, node["fact_path"])["name"] == node["trigram"]
        expected = (
            "旺"
            if node["element"] == row["wang_element"]
            else "衰" if node["element"] == row["shuai_element"] else "原文未定"
        )
        assert node["day_strength"] == expected
        assert node["net_strength"] is None
        assert at_path(out, node["month_strength_fact_path"]) == node["month_strength"]
    assert (
        layer["event_time"]
        is layer["real_outcome"]
        is layer["complete_year_month_day_strength_synthesis"]
        is None
    )
    assert not layer["full_selected_quiet_judgement_established"]
    assert not layer["changes_registered_forecast_eligibility_or_denominators"]


@pytest.mark.parametrize("body", ["木", "火", "土", "金", "水"])
@pytest.mark.parametrize("branch", BRANCHES)
def test_day_element_relation_preserves_undeclared_body_controls_day_case(body, branch):
    case = next(row for row in GEOMETRY if row["body_element"] == body)
    out = calculate_meihua_cast(casting=cast_for(case), day_qi_context=context(branch))
    row = out["interpretation"]["day_qi"]["calendar_candidates"][0]
    expected = TABLE["relationships_body_to_day_element"][body][row["day_element"]]
    assert row["day_qi_relation_to_original_body"] == expected
    pref = row["selected_day_clause_preference"]
    assert (pref is None) is (expected == "体克用")
    if expected in {"用克体", "体生用"}:
        assert pref == "not_preferred_in_selected_day_clause"
    elif expected in {"用生体", "体用比和"}:
        assert pref == "preferred_in_selected_day_clause"


@pytest.mark.parametrize("branch", BRANCHES)
def test_ambiguous_count_candidates_each_keep_own_body_and_month_paths(branch):
    out = calculate_meihua_cast(
        casting={"method": "object_count", "count": 11, "hour_branch": "丑"},
        day_qi_context=context(branch),
        season_month_branch="申",
    )
    assert "error" not in out
    candidates = out["interpretation"]["casting_readings"]
    assert len(candidates) == 2 and len({row["body"] for row in candidates}) == 2
    for index, candidate in enumerate(candidates):
        row = candidate["day_qi"]["calendar_candidates"][0]
        assert row["original_body"]["name"] == candidate["body"]
        assert (
            row["original_body"]["fact_path"]
            == f"meihua.counting_variants.{index}.body_trigram"
        )
        for node in row["roles"]:
            assert (
                at_path(out, node["month_strength_fact_path"]) == node["month_strength"]
            )


@pytest.mark.parametrize("index", range(12))
def test_time_boundary_and_old_full_output_fields_preserved(index):
    reference, old = TIMES[index], OLD_TIMES[index]
    assert reference["input"] == old["input"]
    out = calculate_meihua_analysis(**reference["input"])
    assert "error" not in out
    layer = out["interpretation"]["day_qi"]
    selected = layer["calendar_candidates"][0]
    assert selected["calendar"]["ganzhi"] == reference["midnight_day_ganzhi"]
    assert not layer["bazi_day_reference"]["used_as_selected_midnight_day"]
    assert layer["bazi_day_reference"]["matches_zi_start_reference"]
    if reference["input"]["analysis_hour"] == 23:
        alternate = layer["calendar_candidates"][1]
        assert alternate["calendar"]["ganzhi"] == reference["zi_start_day_ganzhi"]
        assert layer["boundary_changes_day_branch"]
        assert (
            at_path(out, layer["bazi_day_reference"]["fact_path"])
            == alternate["calendar"]["ganzhi"]
        )
        assert "23时另保留子初换日口径" in layer["summary"]
    else:
        assert len(layer["calendar_candidates"]) == 1
    for i, row in enumerate(layer["calendar_candidates"]):
        assert (
            at_path(out, row["day_branch_fact_path"]) == row["calendar"]["day_branch"]
        )
    for name in ["summary"]:
        out[name] = out[name].replace(layer["summary"], "", 1)
    out["interpretation"]["comprehensive_judgement"] = out["interpretation"][
        "comprehensive_judgement"
    ].replace(layer["summary"], "", 1)
    out["interpretation"].pop("day_qi")
    # Check current source conditions before reversing only reviewed historical
    # display/qualification additions. The original frozen JSON is unchanged.
    out = restore_old_time_fixture_view(out)
    # The v38 source-timing child is an explicitly frozen additive change.
    # Keep the old complete fixture unchanged and compare every other field.
    timing = out["interpretation"]["stage_emphasis"].pop("obstruction_timing")
    assert timing["ruleset_id"] == "meihua_obstruction_days_nlc1925_v1"
    assert timing["declared_scenario"] is None
    assert timing["selected_clause_applies"] is None
    assert timing["summary"] == ""
    assert timing["event_time"] is None
    assert out == old["output"]


def test_month_and_day_disagreement_is_not_voted_or_cancelled():
    case = next(row for row in GEOMETRY if row["body_element"] == "木")
    out = calculate_meihua_cast(
        casting=cast_for(case), season_month_branch="申", day_qi_context=context("寅")
    )
    body = out["interpretation"]["day_qi"]["calendar_candidates"][0]["roles"][0]
    assert (
        body["month_strength"],
        body["day_strength"],
        body["month_day_comparison"],
    ) == ("衰", "旺", "different_labels_no_aggregation")
    assert body["net_strength"] is None


def test_hour_year_lunar_day_question_do_not_fill_missing_day_branch():
    out = calculate_meihua_cast(
        casting={
            "method": "lunar_time_added_count",
            "year_branch": "寅",
            "lunar_month": 12,
            "lunar_day": 1,
            "hour_branch": "午",
            "added_count": 4,
        },
        question="虚构：寅日",
    )
    assert "error" not in out
    assert out["interpretation"]["day_qi"] is None
    assert "day_qi_context" not in out["input_normalized"]


@pytest.mark.parametrize("value", [None, "甲子", "", True, 1, {}])
def test_invalid_or_unknown_day_branch_not_coerced(value):
    result = calculate_meihua_cast(
        casting=cast_for(GEOMETRY[0]),
        day_qi_context={"label": "虚构", "day_branch": value},
    )
    assert "error" in result


@pytest.mark.parametrize(
    "value",
    [
        {"day_branch": "子"},
        {"label": " ", "day_branch": "子"},
        {"label": "虚构", "day_branch": "子", "date": "2026-01-01"},
        {"label": "虚构", "day_branch": "子", "declared_day_boundary": "guess"},
    ],
)
def test_context_not_completed_from_missing_label_or_unrecognized_fields(value):
    assert "error" in calculate_meihua_cast(
        casting=cast_for(GEOMETRY[0]), day_qi_context=value
    )


def test_day_boundary_on_reported_branch_is_not_a_verified_date():
    out = calculate_meihua_cast(
        casting=cast_for(GEOMETRY[0]),
        day_qi_context={**context("子"), "declared_day_boundary": "zi_start"},
    )
    row = out["interpretation"]["day_qi"]["calendar_candidates"][0]
    assert row["calendar"]["date"] is row["calendar"]["ganzhi"] is None
    assert row["calendar"]["day_boundary"] == "zi_start"


def test_weather_rejects_supplied_context_and_preserves_failed_primary_gate():
    payload = {"casting": cast_for(GEOMETRY[0]), "interpretation_topic": "weather"}
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate({**payload, "day_qi_context": context("子")})
    assert "error" in calculate_meihua_cast(**payload, day_qi_context=context("子"))
    out = calculate_meihua_cast(**payload)
    assert out["interpretation"]["day_qi"] is None
    primary = out["interpretation"]["weather"]["research_validation"][
        "current_profile_study"
    ]["primary"]
    assert (
        primary["cohort_days"],
        primary["correct"],
        primary["all_dates_always_dry_correct"],
        primary["primary_full_cohort_gate_met"],
    ) == (273, 29, 158, False)


def test_selected_day_words_and_cache_not_normalized_to_other_witness():
    p = day_qi_ruleset()
    assert "看所占卦日屬何卦" in p["day_clause"]["quote"]
    assert "水旺則火衰" in p["month_day_strength"]["weak_quote"]
    assert "生體之卦氣" in p["month_day_strength"]["preferences_quote"]
    p["day_branch_elements"]["子"] = "火"
    assert day_qi_ruleset()["day_branch_elements"]["子"] == "水"


CACHE = r"""
import importlib,importlib.util,json,sys
from pathlib import Path
f=Path(sys.argv[1]);importlib.import_module('fatebridge.core.requests');name='fatebridge.core.requests.meihua';spec=importlib.util.spec_from_file_location(name,f/'legacy-request-meihua.py');m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);setattr(sys.modules['fatebridge.core.requests'],'meihua',m)
assert 'day_qi_context' not in m.MeihuaCastRequest.model_fields
payload={'casting':{'method':'existing','hexagram_code':'100111','moving_line':1}}
m.MeihuaCastRequest.model_validate(payload)
try:m.MeihuaCastRequest.model_validate({**payload,'day_qi_context':{'label':'虚构','day_branch':'子'}})
except Exception:rejected=True
else:rejected=False
assert rejected
from fatebridge.services.meihua import calculate_meihua_cast
from tests.meihua_time_history_reference import restore_old_time_fixture_view
for topic in ['general','weather','travel']:
 for mode in ['omitted','none']:
  kw={**payload,'interpretation_topic':topic}
  if mode=='none':kw['day_qi_context']=None
  out=calculate_meihua_cast(**kw);assert 'error' not in out,out
print('cached schema rejects new field;6old direct defaults/None calls remain valid')
"""


def test_cached_old_request_schema_and_omitted_none_service_compatibility():
    proc = subprocess.run(
        [sys.executable, "-c", CACHE, str(FIXTURE)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr

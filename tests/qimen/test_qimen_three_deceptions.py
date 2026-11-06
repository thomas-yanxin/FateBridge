"""Source-defined triples, partial cases, shared facts and real transports."""

import asyncio
import json
import shutil
from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.qimen_three_deceptions import (
    build_three_deceptions,
    three_deception_context,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation import qimen_three_deceptions as source_audit
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen import verify_qimen_pattern_quotes
from fatebridge.validation.qimen_study import Condition, FrozenQimenPolicy, apply_policy
from tests.qimen.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v13"
REFERENCE = json.loads((BUNDLE / "source-and-three-deceptions.json").read_text())
NAMES = {
    "太阴": ("true_deception", "真诈"),
    "九地": ("heavy_deception", "重诈"),
    "六合": ("rest_deception", "休诈"),
}
RULES = {v[0] for v in NAMES.values()}


def calculate(day, hour):
    return calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=day,
        analysis_hour=hour,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )


@pytest.mark.parametrize(
    "stem,door,god", list(product("乙丙丁", ["开门", "休门", "生门"], NAMES))
)
def test_all_twenty_seven_defined_triples(stem, door, god):
    c = three_deception_context("坎", [stem], door, god)
    assert c["matched"] and (c["rule_id"], c["name"]) == NAMES[god]
    assert (
        not c["outcome_inference_allowed"]
        and not c["two_factor_auspiciousness_adopted"]
    )


@pytest.mark.parametrize("missing", ["wonder", "door", "god"])
@pytest.mark.parametrize("god", list(NAMES))
def test_each_missing_layer_prevents_full_naming(god, missing):
    c = three_deception_context(
        "乾",
        ["戊"] if missing == "wonder" else ["乙"],
        "杜门" if missing == "door" else "开门",
        "九天" if missing == "god" else god,
    )
    assert not c["matched"] and c["name"] is None and c["rule_id"] is None


def test_door_taiyin_without_wonder_retains_opposed_partial_readings():
    c = three_deception_context("离", ["戊"], "生门", "太阴")
    assert c["verse_exactly_two_components_present"]
    assert (
        c["prose_partial_case"] == "door_and_taiyin_without_wonder_priority_unresolved"
    )
    assert not c["matched"] and not c["two_factor_judgment_priority_resolved"]
    assert not c["rhetorical_fractions_converted_to_probability"]
    # The verse's named god is Taiyin; other gods cannot silently inherit it.
    other = three_deception_context("离", ["戊"], "生门", "九地")
    assert not other["verse_exactly_two_components_present"]


@pytest.mark.parametrize(
    "stems,roles",
    [
        (["戊", "乙"], [{"stem": "乙", "role": "hosted"}]),
        (
            ["乙", "丁"],
            [{"stem": "乙", "role": "main"}, {"stem": "丁", "role": "hosted"}],
        ),
    ],
)
def test_hosted_wonders_keep_roles_without_multiple_named_patterns(stems, roles):
    c = three_deception_context("乾", stems, "开门", "太阴")
    assert c["matched"] and c["wonder_roles"] == roles
    assert c["observed_heaven_stems"] == stems


@pytest.mark.parametrize(
    "args",
    [
        ("中", ["乙"], "开门", "太阴"),
        ("坎", [], "开门", "太阴"),
        ("坎", ["甲"], "开门", "太阴"),
        ("坎", ["乙", "乙"], "开门", "太阴"),
        ("坎", ["乙"], "中门", "太阴"),
        ("坎", ["乙"], "开门", "太陰"),
        ("坎", ["乙"], "开门", None),
    ],
)
def test_no_fake_centre_missing_input_or_unimplemented_alias(args):
    with pytest.raises(ValueError):
        three_deception_context(*args)


def test_source_audit_retains_three_names_three_partial_clauses_and_one_priority():
    r = source_audit.audit_three_deceptions(BUNDLE)
    assert r["printed_naming_definitions"] == 3 and r["retained_partial_clauses"] == 3
    assert (
        r["finite_single_stem_context_probes"] == 5760
        and r["finite_matched_probes"] == 216
    )
    assert r["implementation_disagreements"] == []
    assert len(r["unresolved_source_priorities"]) == 1
    assert (
        r["printed_complete_chart_cases"] == r["independent_new_reference_cases"] == 0
    )


@pytest.mark.parametrize("corruption", ["partial_as_full", "outcome", "probability"])
def test_auditor_detects_overbroad_or_outcome_claiming_implementations(
    monkeypatch, corruption
):
    actual = source_audit.three_deception_context

    def changed(*args):
        r = actual(*args)
        if (
            corruption == "partial_as_full"
            and r["verse_exactly_two_components_present"]
        ):
            r["matched"] = True
        elif corruption == "outcome":
            r["outcome_inference_allowed"] = True
        elif corruption == "probability":
            r["rhetorical_fractions_converted_to_probability"] = True
        return r

    monkeypatch.setattr(source_audit, "three_deception_context", changed)
    assert source_audit.audit_three_deceptions(BUNDLE)["implementation_disagreements"]


@pytest.mark.parametrize(
    "corruption",
    [
        "delete_partial",
        "empty_partial_text",
        "delete_name",
        "false_chart",
        "source_bytes",
    ],
)
def test_reference_cannot_drop_awkward_clauses_or_invent_printed_charts(
    tmp_path, corruption
):
    shutil.copytree(BUNDLE, tmp_path / "source")
    d = tmp_path / "source"
    x = deepcopy(REFERENCE)
    if corruption == "delete_partial":
        x["partial_clauses"].pop()
    elif corruption == "empty_partial_text":
        x["partial_clauses"][0]["clause"] = ""
    elif corruption == "delete_name":
        x["definitions"].pop()
    elif corruption == "false_chart":
        x["printed_complete_chart_cases"] = 1
    else:
        (d / x["excerpt_file"]).write_bytes(b"changed")
    (d / "source-and-three-deceptions.json").write_text(json.dumps(x))
    with pytest.raises(ValueError):
        source_audit.audit_three_deceptions(d)


def test_human_dun_overlap_is_not_independent_confirmation():
    q = calculate(2, 12)["qimen"]
    true = next(p for p in q["patterns"] if p["rule_id"] == "true_deception")
    human = next(
        p
        for p in q["patterns"]
        if p["rule_id"] == "human_dun" and p["palace"] == true["palace"]
    )
    assert true["facts"] == {
        "heaven_wonder_stems": ["丁"],
        "door": "休门",
        "god": "太阴",
    }
    assert (
        true["qualification"]["overlapping_evidence_group"]
        == human["qualification"]["overlapping_evidence_group"]
    )
    assert human["qualification"]["overlapping_rule_ids"] == ["true_deception"]
    assert not human["qualification"]["independent_confirmation"]
    different = next(
        p
        for p in calculate(2, 14)["qimen"]["patterns"]
        if p["rule_id"] == "true_deception"
    )
    assert (
        different["facts"]["door"] == "生门"
        and different["qualification"]["overlapping_rule_ids"] == []
    )


def test_three_deceptions_never_erase_an_existing_door_pressure():
    r = calculate(1, 18)
    q = r["qimen"]
    p = next(p for p in q["patterns"] if p["rule_id"] == "heavy_deception")
    assert "门迫" in p["qualification"]["coexisting_rule_names"]
    assert p["qualification"]["condition_observed"]
    assert not p["qualification"]["name_match_is_overall_auspiciousness"]
    assert any(
        x["rule_id"] == "door_pressure" and x["palace"] == p["palace"]
        for x in q["patterns"]
    )
    assert "不由三诈名称覆盖这些条件" in r["snapshot_text"]
    assert r["snapshot_export"]["export_text"] == r["snapshot_text"]


def test_actual_board_hosted_wonder_is_used_once_and_earth_only_never_substituted(
    monkeypatch,
):
    q = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 6, "hour": "丙寅"})
    hosted = next(p for p in q["palaces"] if p["trigram"] == "艮")
    assert hosted["heaven_stems"] == ["癸", "乙"]
    assert hosted["evidence"]["three_deceptions"]["matched"]
    assert hosted["evidence"]["three_deceptions"]["wonder_roles"] == [
        {"stem": "乙", "role": "hosted"}
    ]
    for p in q["palaces"]:
        if p["trigram"] == "中":
            assert "three_deceptions" not in p["evidence"]
            continue
        c = p["evidence"]["three_deceptions"]
        assert c["heaven_wonder_stems"] == [
            s for s in p["heaven_stems"] if s in "乙丙丁"
        ]
        assert not c["earth_wonder_used_as_heaven_wonder"]
        assert sum(
            x["rule_id"] in RULES and x["palace"] == p["name"] for x in q["patterns"]
        ) == int(c["matched"])


def test_earth_only_wonder_is_not_used_as_the_moving_heaven_wonder():
    # Counterfactual layer swap: a synthetic adversarial probe, not a printed
    # or dated chart. The builder must read the actual heaven field.
    p = {
        "trigram": "坎",
        "name": "坎一宫",
        "heaven_stems": ["戊"],
        "earth_stems": ["乙"],
        "door": "开门",
        "god": "太阴",
        "evidence": {},
    }
    q = {"palaces": [p], "source_disagreements": []}
    assert build_three_deceptions(q, []) == []
    assert p["evidence"]["three_deceptions"]["heaven_wonder_stems"] == []


def test_same_run_quote_cannot_delete_partial_limits_or_shared_fact_markers():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            dict(
                analysis_year=2026,
                analysis_month=1,
                analysis_day=2,
                analysis_hour=12,
                analysis_timezone="Asia/Hong_Kong",
                use_true_solar_time=False,
                qimen_options={"ju_method": "chaibu"},
            )
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    index = next(
        i
        for i, p in enumerate(payload["qimen"]["patterns"])
        if p["rule_id"] == "true_deception"
    )
    claim = CalculationClaim(
        path=f"qimen.patterns.{index}",
        value=deepcopy(payload["qimen"]["patterns"][index]),
        run_id=payload["run_metadata"]["run_id"],
    )
    assert (
        verify_qimen_pattern_quotes(payload, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )
    for part in [
        "partial_judgment",
        "overlapping_evidence_group",
        "coexisting_rule_names",
    ]:
        changed = claim.model_dump()
        changed["value"]["qualification"].pop(part)
        assert (
            verify_qimen_pattern_quotes(
                payload, [CalculationClaim.model_validate(changed)]
            )["status"]
            == "rejected"
        )


@pytest.mark.parametrize(
    "rule,day,hour",
    [("rest_deception", 1, 0), ("heavy_deception", 1, 18), ("true_deception", 2, 14)],
)
def test_frozen_policy_queries_only_the_named_full_condition(rule, day, hour):
    c = Condition(feature="pattern_present", pattern=rule, equals=True)
    policy = FrozenQimenPolicy(
        policy_id="synthetic-three-deceptions-not-calibrated",
        target_definition="Synthetic rule query, no empirical outcomes",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="use_declared_rules",
        rules=[
            {
                "rule_id": "synthetic-only",
                "all_of": [c.model_dump()],
                "probability": 0.61,
            }
        ],
        fallback_probability=None,
    )
    assert apply_policy(calculate(day, hour)["qimen"], policy)["probability"] == 0.61


@pytest.mark.parametrize(
    "day,hour,expected",
    [
        (1, 0, "rest_deception"),
        (1, 18, "heavy_deception"),
        (2, 12, "true_deception"),
        (2, 14, "true_deception"),
    ],
)
@pytest.mark.parametrize("aggregate", [False, True])
def test_named_patterns_and_limits_agree_across_real_transports(
    monkeypatch, capsys, day, hour, expected, aggregate
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["qimen", "snapshot_text", "snapshot_export"]
    payload = dict(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=day,
        analysis_hour=hour,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
    tool = "sanshiunited" if aggregate else "qimen"
    path = "/api/divination/sanshiunited" if aggregate else "/api/cn/qimen"
    if aggregate:
        payload = dict(
            date=f"2026-01-{day:02d}",
            time=f"{hour:02d}:00:00",
            zone="Asia/Hong_Kong",
            gps_lat=22.3,
            gps_lon=114.17,
            use_true_solar_time=False,
            qimen_options={"ju_method": "chaibu"},
        )
        clock_args = [
            "--date",
            payload["date"],
            "--time",
            payload["time"],
            "--zone",
            "Asia/Hong_Kong",
            "--gps-lat",
            "22.3",
            "--gps-lon",
            "114.17",
        ]
    else:
        clock_args = [
            "--analysis-year",
            "2026",
            "--analysis-month",
            "1",
            "--analysis-day",
            str(day),
            "--analysis-hour",
            str(hour),
            "--analysis-timezone",
            "Asia/Hong_Kong",
        ]
    controls = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    rest = TestClient(api.app).post(
        path,
        json=payload,
        params=[
            ("as_of", controls["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                tool, {**payload, **controls}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run(
        [
            tool,
            *clock_args,
            "--no-use-true-solar-time",
            "--qimen-options",
            json.dumps(payload["qimen_options"]),
            "--as-of",
            controls["as_of"],
            "--strict-fields",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not native.is_error and code == 0
    bodies = [
        {k: b[k] for k in fields} for b in [rest.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    q = bodies[0]["qimen"]
    assert any(p["rule_id"] == expected for p in q["patterns"])
    assert not q["rule_profiles"]["three_deceptions"][
        "two_factor_judgment_priority_resolved"
    ]
    assert (
        q["rulesets"][0]["version"] == "2.12.0"
        and not q["assessment"]["authority_certified"]
    )
    assert "十分七分不作概率" in bodies[0]["snapshot_text"]


@pytest.mark.parametrize("day,hour", [(1, 18), (2, 12)])
def test_sanshi_keeps_same_evidence_and_source_version(day, hour):
    r = calculate_sanshiunited_analysis(
        date=f"2026-01-{day:02d}",
        time=f"{hour:02d}:00:00",
        zone="Asia/Hong_Kong",
        gps_lat=22.3,
        gps_lon=114.17,
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
    assert "error" not in r, r
    q = calculate(day, hour)["qimen"]
    assert (
        r["qimen"]["palaces"] == q["palaces"]
        and r["qimen"]["patterns"] == q["patterns"]
    )
    assert r["subresults"]["qimen"]["pan"] == r["qimen"]
    assert r["synthesis"]["source_profiles"]["qimen"][0]["version"] == "2.12.0"
    assert "三诈口径" in r["snapshot_text"]

"""Five-jia printed clauses, unresolved identity and evidence delivery."""

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
from fatebridge.core.qimen_five_jia import build_five_jia, five_jia_context
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation import qimen_five_jia as source_audit
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen import verify_qimen_pattern_quotes
from fatebridge.validation.qimen_study import Condition, FrozenQimenPolicy, apply_policy
from tests.qimen.test_qimen_three_deceptions import calculate

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v14"
REFERENCE = json.loads((BUNDLE / "source-and-five-jia.json").read_text())


@pytest.mark.parametrize(
    "definition", REFERENCE["definitions"], ids=lambda d: d["rule_id"]
)
@pytest.mark.parametrize("stem_index", range(3))
def test_all_twelve_printed_naming_combinations(definition, stem_index):
    d = definition
    stem = d["heaven_stems"][stem_index]
    c = five_jia_context("坎", [stem], d["door"], d["god"])
    assert [(m["rule_id"], m["name"]) for m in c["named_matches"]] == [
        (d["rule_id"], d["name"])
    ]
    assert not c["outcome_inference_allowed"]


@pytest.mark.parametrize(
    "definition", REFERENCE["definitions"], ids=lambda d: d["rule_id"]
)
@pytest.mark.parametrize("missing", ["stem", "door", "god"])
def test_each_required_layer_is_necessary(definition, missing):
    d = definition
    c = five_jia_context(
        "离",
        ["戊"] if missing == "stem" else d["heaven_stems"][:1],
        "开门" if missing == "door" else d["door"],
        "值符" if missing == "god" else d["god"],
    )
    assert not c["named_matches"]


@pytest.mark.parametrize("god", ["六合", "太阴"])
def test_unnamed_du_door_examples_do_not_inherit_earth_jia_name(god):
    c = five_jia_context("乾", ["己"], "杜门", god)
    assert c["unnamed_du_door_clause"] and not c["named_matches"]


def test_hosted_stems_keep_roles_and_one_name_per_palace():
    c = five_jia_context("乾", ["己", "癸"], "杜门", "九地")
    assert len(c["named_matches"]) == 1
    assert c["named_matches"][0]["stem_roles"] == [
        {"stem": "己", "role": "main"},
        {"stem": "癸", "role": "hosted"},
    ]
    # Synthetic dual-qualified stems do not claim an independently printed chart.
    q = {
        "palaces": [
            {
                "name": "乾六宫",
                "trigram": "乾",
                "heaven_stems": ["戊", "己"],
                "earth_stems": ["癸"],
                "door": "杜门",
                "god": "九地",
                "evidence": {},
            }
        ],
        "source_disagreements": [],
    }
    result = build_five_jia(q, [])
    assert len(result) == 1 and result[0]["facts"]["qualifying_heaven_stems"] == ["己"]
    q["palaces"][0]["heaven_stems"] = ["戊"]
    assert build_five_jia(q, []) == []  # earth 癸 cannot substitute


@pytest.mark.parametrize("stems", [["己"], ["壬"], ["戊", "己"]])
def test_human_jia_remains_unknown_even_when_a_candidate_matches(stems):
    c = five_jia_context("艮", stems, "惊门", "九天")
    assert c["human_jia"]["adopted_match"] is None and not c["named_matches"]
    assert c["human_jia"]["unadopted_ji_stem_candidate_observed"] == ("己" in stems)
    assert not c["human_jia"]["candidate_failure_proves_absence"]


@pytest.mark.parametrize(
    "args",
    [
        ("中", ["己"], "杜门", "九地"),
        ("坎", [], "杜门", "九地"),
        ("坎", ["甲"], "杜门", "九地"),
        ("坎", ["己", "己"], "杜门", "九地"),
        ("坎", ["己"], "中门", "九地"),
        ("坎", ["己"], "杜门", "九地宫"),
    ],
)
def test_invalid_or_aliased_inputs_do_not_produce_a_pattern(args):
    with pytest.raises(ValueError):
        five_jia_context(*args)


def test_finite_source_audit_keeps_unresolved_name_and_no_empirical_claim():
    r = source_audit.audit_five_jia(BUNDLE)
    assert not r["implementation_disagreements"]
    assert r["finite_single_stem_context_probes"] == 5760
    assert r["finite_named_match_probes"] == 96
    assert r["finite_unnamed_clause_probes"] == 48
    assert r["finite_unadopted_ji_candidate_probes"] == 8
    assert len(r["unresolved_source_priorities"]) == 1
    assert (
        r["printed_complete_chart_cases"] == 0
        and not r["real_world_efficacy_validated"]
    )


def test_source_audit_detects_wrong_stem_mapping(monkeypatch):
    original = source_audit.five_jia_context

    def wrong(gua, stems, door, god):
        return original(gua, ["乙"] if stems == ["己"] else stems, door, god)

    monkeypatch.setattr(source_audit, "five_jia_context", wrong)
    assert source_audit.audit_five_jia(BUNDLE)["implementation_disagreements"]


@pytest.mark.parametrize(
    "mutation", ["rename", "stems", "human", "auxiliary", "chart_count", "image"]
)
def test_omitted_or_rewritten_source_scope_is_rejected(tmp_path, mutation):
    dest = tmp_path / "source"
    shutil.copytree(BUNDLE, dest)
    ref = deepcopy(REFERENCE)
    if mutation == "rename":
        ref["definitions"][2]["name"] = "人假"
    elif mutation == "stems":
        ref["definitions"][1]["heaven_stems"] = ["乙", "丙", "丁"]
    elif mutation == "human":
        ref["human_jia"]["ji_candidate_adopted"] = True
    elif mutation == "auxiliary":
        ref["unnamed_clauses"] = []
    elif mutation == "chart_count":
        ref["printed_complete_chart_cases"] = 5
    else:
        (dest / ref["excerpt_file"]).write_bytes(b"wrong source")
    (dest / "source-and-five-jia.json").write_text(json.dumps(ref))
    with pytest.raises(ValueError, match="五假"):
        source_audit.audit_five_jia(dest)


def test_research_rule_treats_unresolved_human_jia_as_unknown_not_absent():
    q = calculate(2, 14)["qimen"]
    for feature, expected in product(
        ["pattern_present", "pattern_conditions_observed"], [True, False]
    ):
        policy = FrozenQimenPolicy(
            policy_id="synthetic-human-unknown",
            target_definition="synthetic only",
            ju_method="chaibu",
            god_profile="yanyi_text",
            season_profile="yanyi_vol1_verse",
            use_true_solar_time=False,
            source_disagreement_action="use_declared_rules",
            rules=[
                {
                    "rule_id": "human",
                    "all_of": [
                        Condition(
                            feature=feature, pattern="human_jia", equals=expected
                        ).model_dump()
                    ],
                    "probability": 0.9,
                }
            ],
            fallback_probability=0.1,
        )
        decision = apply_policy(q, policy)
        assert (
            decision["probability"] is None
            and decision["reason"] == "unknown_potentially_matching_rule"
        )


@pytest.mark.parametrize(
    "day,hour,pattern",
    [
        (1, 16, "ghost_jia"),
        (2, 4, "spirit_jia"),
        (7, 12, "heaven_jia"),
        (12, 12, "earth_jia"),
    ],
)
def test_four_computable_names_are_readable_by_frozen_research_policies(
    day, hour, pattern
):
    q = calculate(day, hour)["qimen"]
    policy = FrozenQimenPolicy(
        policy_id="synthetic-four-jia",
        target_definition="synthetic only",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="use_declared_rules",
        rules=[
            {
                "rule_id": "four-jia",
                "all_of": [
                    {"feature": "pattern_present", "pattern": pattern, "equals": True},
                    {
                        "feature": "pattern_conditions_observed",
                        "pattern": pattern,
                        "equals": True,
                    },
                ],
                "probability": 0.8,
            }
        ],
        fallback_probability=None,
    )
    result = apply_policy(q, policy)
    assert result["selected_rule"] == "four-jia" and result["probability"] == 0.8
    # The declared 0.8 is a synthetic test hypothesis, never a calibrated rate.


def test_actual_board_retains_coexisting_rules_and_unadopted_hosted_candidate():
    q = calculate(1, 16)["qimen"]
    p = next(p for p in q["patterns"] if p["rule_id"] == "ghost_jia")
    assert not p["qualification"]["name_match_is_overall_auspiciousness"]
    assert p["qualification"]["coexisting_rule_names"]
    q = calculate(2, 14)["qimen"]
    at = next(p for p in q["palaces"] if p["trigram"] == "艮")
    assert at["heaven_stems"] == ["丙", "己"]
    assert at["evidence"]["five_jia"]["human_jia"][
        "unadopted_ji_stem_candidate_observed"
    ]
    assert all(p["rule_id"] != "human_jia" for p in q["patterns"])


@pytest.mark.parametrize(
    "day,hour,expected",
    [
        (1, 16, "ghost_jia"),
        (2, 4, "spirit_jia"),
        (7, 12, "heaven_jia"),
        (12, 12, "earth_jia"),
    ],
)
def test_whole_pattern_quote_preserves_exact_condition_and_scope(day, hour, expected):
    options = ExecutionOptions(as_of="2026-10-22T12:00:00+08:00")
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    result = execute_tool(
        spec,
        spec.request_model.model_validate(
            dict(
                analysis_year=2026,
                analysis_month=1,
                analysis_day=day,
                analysis_hour=hour,
                analysis_timezone="Asia/Hong_Kong",
                use_true_solar_time=False,
                qimen_options={"ju_method": "chaibu"},
            )
        ),
        options=options,
    )
    index = next(
        i for i, p in enumerate(result["qimen"]["patterns"]) if p["rule_id"] == expected
    )
    path = f"qimen.patterns.{index}"
    pattern = result["qimen"]["patterns"][index]
    claim = CalculationClaim.model_validate(
        {
            "run_id": result["run_metadata"]["run_id"],
            "path": path,
            "value": pattern,
        }
    )
    assert (
        verify_qimen_pattern_quotes(result, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )
    changed = deepcopy(pattern)
    changed["qualification"]["human_jia_identity_resolved"] = True
    claim = claim.model_copy(update={"value": changed})
    assert verify_qimen_pattern_quotes(result, [claim])["status"] == "rejected"


@pytest.mark.parametrize(
    "day,hour,expected",
    [
        (1, 16, "ghost_jia"),
        (2, 4, "spirit_jia"),
        (7, 12, "heaven_jia"),
        (12, 12, "earth_jia"),
        (2, 14, None),
        (2, 22, None),
    ],
)
@pytest.mark.parametrize("aggregate", [False, True])
def test_five_jia_evidence_and_limits_survive_all_real_transports(
    monkeypatch, capsys, day, hour, expected, aggregate
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["qimen", "snapshot_text", "snapshot_export"]
    if aggregate:
        tool, path = "sanshiunited", "/api/divination/sanshiunited"
        payload = dict(
            date=f"2026-01-{day:02d}",
            time=f"{hour:02d}:00:00",
            zone="Asia/Hong_Kong",
            gps_lat=22.3,
            gps_lon=114.17,
            use_true_solar_time=False,
            qimen_options={"ju_method": "chaibu"},
        )
        clock = [
            "--date",
            payload["date"],
            "--time",
            payload["time"],
            "--zone",
            payload["zone"],
            "--gps-lat",
            "22.3",
            "--gps-lon",
            "114.17",
        ]
    else:
        tool, path = "qimen", "/api/cn/qimen"
        payload = dict(
            analysis_year=2026,
            analysis_month=1,
            analysis_day=day,
            analysis_hour=hour,
            analysis_timezone="Asia/Hong_Kong",
            use_true_solar_time=False,
            qimen_options={"ju_method": "chaibu"},
        )
        clock = [
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
            *clock,
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
    if expected:
        assert any(p["rule_id"] == expected for p in q["patterns"])
    assert q["rulesets"][0]["version"] == "2.12.0"
    assert q["rule_profiles"]["five_jia"]["human_jia"]["adopted_match"] is None
    assert not q["assessment"]["authority_certified"]
    assert "人假六合身份" in bodies[0]["snapshot_text"]
    for palace in q["palaces"]:
        assert ("five_jia" in palace["evidence"]) == (palace["trigram"] != "中")

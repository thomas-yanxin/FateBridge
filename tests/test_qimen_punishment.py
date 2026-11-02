"""Current-zhifu identity, retained geometry and unresolved source example."""

import asyncio
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.qimen_punishment import describe_punishment, palace_punishment
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen import verify_qimen_pattern_quotes
from fatebridge.validation.qimen_punishment import audit_punishment
from tests.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parent / "fixtures/qimen_classical_v10"
REFERENCE = json.loads((BUNDLE / "sources-and-punishment.json").read_text())


def test_source_audit_keeps_both_readings_and_unpassed_scope_priority():
    report = audit_punishment(BUNDLE)
    assert report["definition_count"] == 6
    assert report["definition_disagreements"] == []
    assert report["example_count"] == 2 and report["matched_example_count"] == 2
    assert report["example_disagreements"] == []
    assert len(report["unresolved_source_scope_priorities"]) == 1
    assert [d["case_id"] for d in report["narrow_reading_disagreements"]] == [
        "vol2-yang1-mao-punishment-scope"
    ]
    assert not report["whole_section_reconciled"]
    mao = next(r for r in report["examples"] if "mao" in r["case_id"])
    assert mao["source_claim_matched"] is True and mao["computed_matched"] is True
    assert mao["current_zhifu_candidate_matched"] is False
    assert mao["hour_provenance"].startswith("derived_")
    assert mao["retained_geometric_observations"]


@pytest.mark.parametrize("definition", REFERENCE["definitions"])
@pytest.mark.parametrize("trigram", list("坎坤震巽乾兑艮离"))
def test_six_named_heads_and_eight_palaces_follow_frozen_source_cells(
    definition, trigram
):
    result = palace_punishment(
        definition["xun_head"], trigram, [definition["hidden_stem"]]
    )
    assert result["matched"] is (trigram == definition["trigram"])
    assert result["punished_branch"] == definition["punished_branch"]
    assert result["required_trigram"] == definition["trigram"]
    assert result["other_instrument_geometry_is_formal_match"]
    assert not result["source_scope_adjudicated"]
    assert not result["outcome_inference_allowed"]


@pytest.mark.parametrize("definition", REFERENCE["definitions"])
def test_other_heads_instrument_geometry_does_not_become_current_zhifu(definition):
    next_head = REFERENCE["definitions"][
        (REFERENCE["definitions"].index(definition) + 1) % 6
    ]["xun_head"]
    result = palace_punishment(
        next_head, definition["trigram"], [definition["hidden_stem"]]
    )
    assert result["matched"] and not result["current_zhifu_matched"]
    assert result["non_current_geometric_stems"] == [definition["hidden_stem"]]


@pytest.mark.parametrize("dun", ["阳遁", "阴遁"])
@pytest.mark.parametrize("ju", range(1, 10))
def test_internal_1080_board_sweep_preserves_every_geometric_observation(
    monkeypatch, dun, ju
):
    heads = REFERENCE["definitions"]
    by_stem = {r["hidden_stem"]: r for r in heads}
    for index in range(60):
        hour = (
            "甲乙丙丁戊己庚辛壬癸"[index % 10] + "子丑寅卯辰巳午未申酉戌亥"[index % 12]
        )
        expected_head = heads[index // 10]
        board = fixed_board(monkeypatch, {"dun": dun, "ju": ju, "hour": hour})
        formal = [
            p for p in board["patterns"] if p["rule_id"] == "six_instrument_punishment"
        ]
        expected = []
        narrow_count = 0
        for palace in board["palaces"]:
            if palace["trigram"] == "中":
                continue
            e = palace["evidence"]["six_instrument_punishment"]
            geometry = [
                s
                for s in palace["heaven_stems"]
                if s in by_stem and by_stem[s]["trigram"] == palace["trigram"]
            ]
            assert {r["hidden_stem"] for r in e["geometric_matches"]} == set(geometry)
            assert e["non_current_geometric_stems"] == [
                s
                for s in by_stem
                if s in geometry and s != expected_head["hidden_stem"]
            ]
            matched = (
                expected_head["hidden_stem"] in palace["heaven_stems"]
                and expected_head["trigram"] == palace["trigram"]
            )
            assert e["current_zhifu_matched"] is matched
            narrow_count += matched
            assert e["matched"] is bool(geometry)
            expected.extend((palace["name"], stem) for stem in geometry)
        assert [(p["palace"], p["facts"]["heaven_stem"]) for p in formal] == expected
        assert narrow_count <= 1
        for pattern in formal:
            e = pattern["qualification"]["punishment_evidence"]
            assert e["matched"] and e["xun_head"] == expected_head["xun_head"]
            assert e["hidden_stem"] == expected_head["hidden_stem"]
            identity = pattern["qualification"]["punishment_instrument_identity"]
            assert (
                identity["xun_head"]
                == by_stem[pattern["facts"]["heaven_stem"]]["xun_head"]
            )


def test_hosted_current_instrument_is_preserved(monkeypatch):
    board = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "辛亥"})
    palace = next(p for p in board["palaces"] if p["trigram"] == "巽")
    assert palace["heaven_stem"] != "壬" and "壬" in palace["heaven_stems"]
    assert palace["evidence"]["six_instrument_punishment"]["matched"]
    assert any(
        p["rule_id"] == "six_instrument_punishment" and p["palace"] == palace["name"]
        for p in board["patterns"]
    )


def test_profile_return_cannot_mutate_the_selected_rule():
    profile = describe_punishment()
    profile["definitions"][0]["trigram"] = "离"
    profile["unresolved_example"]["broader_instrument_reading_adopted"] = False
    assert describe_punishment()["definitions"][0]["trigram"] == "震"
    assert describe_punishment()["unresolved_example"][
        "broader_instrument_reading_adopted"
    ]


@pytest.mark.parametrize(
    "hour,trigram,stems",
    [
        ("甲丑", "震", ["戊"]),
        ("甲子extra", "震", ["戊"]),
        (None, "震", ["戊"]),
        ("甲子", "中", ["戊"]),
        ("甲子", "震", []),
        ("甲子", "震", ["甲"]),
        ("甲子", "震", ["戊己"]),
    ],
)
def test_bad_inputs_do_not_turn_into_negative_observations(hour, trigram, stems):
    with pytest.raises(ValueError):
        palace_punishment(hour, trigram, stems)


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_example",
        "drop_identity",
        "erase_scope",
        "delete_unresolved",
        "source_bytes",
        "erase_claim",
    ],
)
def test_source_audit_cannot_drop_inconvenient_evidence(tmp_path, mutation):
    target = tmp_path / "bundle"
    shutil.copytree(BUNDLE, target)
    path = target / "sources-and-punishment.json"
    ref = json.loads(path.read_text())
    if mutation == "drop_example":
        ref["examples"].pop()
    elif mutation == "drop_identity":
        ref["definitions"].pop()
    elif mutation == "erase_scope":
        ref["scope_clause"] = "凡六仪皆可"
    elif mutation == "delete_unresolved":
        ref["unresolved_example_ids"] = []
    elif mutation == "erase_claim":
        ref["examples"][1]["source_claim_matched"] = False
    else:
        (target / "siku-pages33-34.pdf").write_bytes(b"changed")
    path.write_text(json.dumps(ref))
    with pytest.raises(ValueError):
        audit_punishment(target)


@pytest.mark.parametrize(
    "changed", ["head", "instrument", "scope", "formal_geometry", "source_reconciled"]
)
def test_whole_pattern_quote_cannot_erase_its_identity_or_uncertainty(changed):
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 5,
                "analysis_hour": 12,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
                "qimen_options": {"ju_method": "chaibu"},
            }
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    index, pattern = next(
        (i, p)
        for i, p in enumerate(payload["qimen"]["patterns"])
        if p["rule_id"] == "six_instrument_punishment"
    )
    claim = CalculationClaim(
        run_id=payload["run_metadata"]["run_id"],
        business_output_sha256=payload["run_metadata"]["business_output_sha256"],
        path=f"qimen.patterns.{index}",
        value=deepcopy(pattern),
    )
    assert (
        verify_qimen_pattern_quotes(payload, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )
    e = claim.value["qualification"]["punishment_evidence"]
    if changed == "head":
        e["xun_head"] = "甲辰"
    elif changed == "instrument":
        e["hidden_stem"] = "壬"
    elif changed == "scope":
        e.pop("scope")
    elif changed == "formal_geometry":
        e["other_instrument_geometry_is_formal_match"] = False
    else:
        e["whole_section_reconciled"] = True
    assert verify_qimen_pattern_quotes(payload, [claim])["status"] == "rejected"


@pytest.mark.parametrize("hour,expected", [(6, False), (12, True)])
def test_source_scope_and_geometry_survive_rest_native_mcp_and_cli(
    monkeypatch, capsys, hour, expected
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["qimen", "snapshot_text"]
    payload = dict(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=5,
        analysis_hour=hour,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
    controls = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/cn/qimen",
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
                "qimen", {**payload, **controls}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    capsys.readouterr()
    code = run(
        [
            "qimen",
            "--analysis-year",
            "2026",
            "--analysis-month",
            "1",
            "--analysis-day",
            "5",
            "--analysis-hour",
            str(hour),
            "--analysis-timezone",
            "Asia/Hong_Kong",
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
    assert code == 0 and response.status_code == 200, (cli, response.text)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in [response.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    q = bodies[0]["qimen"]
    assert q["ju_number"] == 1 and q["xun_head"] == "甲子"
    assert any(p["rule_id"] == "six_instrument_punishment" for p in q["patterns"])
    assert (
        any(
            p["evidence"]
            .get("six_instrument_punishment", {})
            .get("current_zhifu_matched")
            for p in q["palaces"]
        )
        is expected
    )
    assert all(
        "six_instrument_punishment" in p["evidence"]
        for p in q["palaces"]
        if p["trigram"] != "中"
    )
    assert "广义暂定保留" in bodies[0]["snapshot_text"]
    assert not q["rule_profiles"]["six_instrument_punishment"][
        "source_scope_adjudicated"
    ]
    if not expected:
        pattern = next(
            p for p in q["patterns"] if p["rule_id"] == "six_instrument_punishment"
        )
        assert pattern["facts"]["instrument_xun_head"] == "甲辰"
        assert pattern["facts"]["hour_xun_head"] == "甲子"
        assert "非本时直符六仪的落刑宫几何观察：壬" in bodies[0]["snapshot_text"]
        assert "按暂定广义取法保留匹配" in bodies[0]["snapshot_text"]

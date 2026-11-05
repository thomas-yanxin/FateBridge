"""Offline evaluator checks; model calls are explicit, never part of pytest."""

import json
import sys
from pathlib import Path

from scripts.evaluate_agent import (
    CASES,
    command_for,
    freeze_source,
    grade_case,
    source_manifest,
)


def event(tool, arguments=None, server="fatebridge"):
    return {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": server,
            "tool": tool,
            "arguments": arguments or {},
            "status": "completed",
        },
    }


def test_grade_rejects_empty_runs_external_calls_and_out_of_scope_computation():
    case = {"no_calculation": True, "manual_review": []}
    assert grade_case(case, [], "", 1)["failures"]
    assert grade_case(case, [event("bazi_birth")], "answer", 0)["failures"]
    assert grade_case(case, [event("send_message", server="other")], "answer", 0)[
        "failures"
    ]
    assert grade_case(case, [event("knowledge_read")], "answer", 0)[
        "mechanical_checks_passed"
    ]


def test_full_export_requires_unprojected_first_call_and_confirmed_inputs():
    case = {
        "required_any": [["bazi_birth"]],
        "full_export": "bazi_birth",
        "arguments": {"bazi_birth": {"birth_hour": 10}},
        "manual_review": [],
    }
    invalid = [
        event("bazi_birth", {"fields": ["summary"], "birth_hour": 0}),
        event("bazi_birth", {"fields": None, "birth_hour": 10}),
    ]
    assert set(grade_case(case, invalid, "answer", 0)["failures"]) == {
        "projected_full_export",
        "input_mismatch:bazi_birth",
    }
    assert not grade_case(case, [], "answer", 0)["mechanical_checks_passed"]
    assert grade_case(case, [event("bazi_birth", {"birth_hour": 10})], "answer", 0)[
        "mechanical_checks_passed"
    ]


def test_cases_cover_positive_negative_missing_and_complete_requests():
    records = json.loads(CASES.read_text())["cases"]
    assert len({c["id"] for c in records}) == len(records)
    assert any(c.get("required_any") for c in records)
    assert any(c.get("no_calculation") for c in records)
    assert any(c.get("full_export") for c in records)
    assert all(c["prompt"] and c["manual_review"] for c in records)
    command = command_for("codex", Path("/workspace"), Path("/output"), records[0])
    assert "--ignore-user-config" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--model" not in command
    assert 'mcp_servers.fatebridge.env.PYTHONPATH="/workspace/src"' in command


def test_evaluation_freezes_backend_and_yaml_as_well_as_instructions(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("AGENTS.md", "pyproject.toml", "uv.lock"):
        (source / name).write_text(name)
    for name in (
        "skills/example/agents/openai.yaml",
        "src/fatebridge/example.py",
        "scripts/evaluate_agent.py",
    ):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original")
    frozen = tmp_path / "frozen"
    manifest = freeze_source(frozen, source)
    (source / "src/fatebridge/example.py").write_text("changed")
    assert source_manifest(frozen) == manifest
    assert source_manifest(source) != manifest
    assert manifest["skills/example/agents/openai.yaml"]
    (source / "scripts/evaluate_agent.py").write_text("changed judge")
    assert (frozen / "scripts/evaluate_agent.py").read_text() == "original"
    assert source_manifest(frozen) == manifest


def test_completed_transport_does_not_hide_protocol_errors_and_recovery():
    failed = event("astro_india_chart")
    failed["item"]["result"] = {"isError": True}
    case = {"manual_review": []}
    assert (
        "unrecovered_tool_failure"
        in grade_case(case, [failed], "answer", 0)["failures"]
    )
    assert grade_case(case, [failed, event("astro_india_chart")], "answer", 0)[
        "mechanical_checks_passed"
    ]


def test_skill_routes_allow_complete_alternatives_but_not_partial_compositions():
    case = {
        "expected_skill_sets": [["onda-zige"], ["onda-shiye", "onda-xueye"]],
        "manual_review": [],
    }

    def read(*skills):
        return [
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "cat "
                    + " ".join(f"skills/{s}/SKILL.md" for s in skills),
                },
            }
        ]

    assert grade_case(case, read("onda-zige"), "answer", 0)["mechanical_checks_passed"]
    assert grade_case(case, read("onda-shiye", "onda-xueye"), "answer", 0)[
        "mechanical_checks_passed"
    ]
    assert not grade_case(case, read("onda-shiye"), "answer", 0)[
        "mechanical_checks_passed"
    ]


def test_target_instants_accept_equivalent_offsets_but_reject_missing_timezones():
    case = {
        "instant_arguments": {
            "astro_germany_chart": {"analysis_datetime": "2000-02-01T00:00:00Z"}
        },
        "manual_review": [],
    }
    for value in ("2000-02-01T00:00:00+00:00", "2000-02-01T08:00:00+08:00"):
        assert grade_case(
            case, [event("astro_germany_chart", {"analysis_datetime": value})], "x", 0
        )["mechanical_checks_passed"]
    for value in (None, "invalid", "2000-02-01T00:00:00", "2000-02-01T00:00:01Z"):
        assert (
            "instant_mismatch:astro_germany_chart"
            in grade_case(
                case,
                [event("astro_germany_chart", {"analysis_datetime": value})],
                "x",
                0,
            )["failures"]
        )
    assert grade_case(case, [], "x", 0)["failures"]


def test_same_run_export_limit_counts_successes_without_hiding_failed_recovery():
    case = {
        "max_successful_calls": {"astro_germany_chart": 1},
        "manual_review": [],
    }
    success = event("astro_germany_chart")
    failed = event("astro_germany_chart")
    failed["item"]["result"] = {"isError": True}
    assert grade_case(case, [failed, success], "x", 0)["mechanical_checks_passed"]
    assert (
        "repeated_calculation:astro_germany_chart"
        in grade_case(case, [success, success], "x", 0)["failures"]
    )


def test_nested_arguments_allow_explicit_defaults_but_reject_wrong_values_and_bools():
    case = {
        "manual_review": [],
        "argument_paths": {
            "meihua_cast": {
                "casting.method": "object_count",
                "casting.count": 1,
                "casting.hour_branch": "酉",
            }
        },
        "allowed_tools": ["meihua_cast"],
    }
    good = {
        "casting": {
            "method": "object_count",
            "count": 1,
            "hour_branch": "酉",
            "line_sum_basis": "raw_counts",
        }
    }
    assert grade_case(case, [event("meihua_cast", good)], "answer", 0)[
        "mechanical_checks_passed"
    ]
    for changes in ({"count": True}, {"count": 2}, {"hour_branch": "子"}):
        bad = {"casting": {**good["casting"], **changes}}
        assert (
            "input_mismatch:meihua_cast"
            in grade_case(case, [event("meihua_cast", bad)], "answer", 0)["failures"]
        )
    assert (
        "out_of_scope_tool"
        in grade_case(case, [event("sixyao")], "answer", 0)["failures"]
    )


def test_capture_is_only_enabled_for_opted_in_evaluation_cases():
    case = {"id": "fictional", "capture_payloads": True}
    command = command_for("codex", Path("/workspace"), Path("/output"), case)
    assert (
        'mcp_servers.fatebridge.env.FATEBRIDGE_EVALUATION_LOG="/output/mcp-calls.jsonl"'
        in command
    )
    assert any("fatebridge.validation.agent_capture" in item for item in command)
    ordinary = command_for(
        "codex", Path("/workspace"), Path("/output"), {"id": "ordinary"}
    )
    assert not any(
        "agent_capture" in item or "EVALUATION_LOG" in item for item in ordinary
    )


def test_meihua_cohort_retains_all_selected_cases_and_pending_semantic_requirements():
    path = Path(__file__).parent / "fixtures/agent_behavior/meihua_semantic_cases.json"
    cases = json.loads(path.read_text())["cases"]
    assert len(cases) == len({c["id"] for c in cases}) == 10
    assert sum(len(c["manual_review"]) for c in cases) == 30
    assert sum("reference_request" in c for c in cases) == 9
    assert sum(c.get("no_calculation", False) for c in cases) == 1
    assert all(c["capture_payloads"] and c["scenario"] == "onda-zhanbu" for c in cases)


def test_prepare_only_does_not_launch_a_model_or_need_cli_configuration(
    tmp_path, monkeypatch
):
    import scripts.evaluate_agent as evaluator

    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "one", "prompt": "fictional", "manual_review": ["pending"]}
                ]
            }
        )
    )
    output = tmp_path / "prepared"
    monkeypatch.setattr(evaluator, "freeze_source", lambda target: {})
    monkeypatch.setattr(evaluator, "source_manifest", lambda source: {})

    async def prepare(
        cases, target, source, native_selection, native_working_directory
    ):
        from fatebridge.validation.evaluation_environment import capture_selection

        assert native_selection == capture_selection()
        assert native_working_directory == Path.cwd().resolve()
        assert cases[0]["id"] == "one"
        return [{"case": "one", "reference_status": "no_calculation_required"}]

    def prohibited(*args, **kwargs):
        raise AssertionError(
            "Model execution or CLI lookup is forbidden during preparation"
        )

    monkeypatch.setattr(evaluator, "prepare_references", prepare)
    monkeypatch.setattr(evaluator.subprocess, "run", prohibited)
    monkeypatch.setattr(evaluator.subprocess, "check_output", prohibited)
    monkeypatch.setattr("fatebridge.diagnostics.resolve_codex_cli", prohibited)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_agent",
            "--prepare-only",
            "--cases-file",
            str(dataset),
            "--output",
            str(output),
        ],
    )
    assert evaluator.main() == 0
    report = json.loads((output / "preparation.json").read_text())
    assert report["model_invocations"] == 0
    assert report["semantic_acceptance"] == "not_run"
    assert (output / "case-dataset.json").read_bytes() == dataset.read_bytes()
    proposal = json.loads((output / "proposed-execution.json").read_text())
    assert "--stop-on-execution-failure" in proposal["command"]
    assert "--native-environment" in proposal["command"]
    assert "--native-environment-sha256" in proposal["command"]
    assert (
        report["native_environment_sha256"]
        == __import__("hashlib")
        .sha256((output / "native-environment.json").read_bytes())
        .hexdigest()
    )


def test_execution_failure_preserves_selected_case_denominator(tmp_path, monkeypatch):
    import scripts.evaluate_agent as evaluator

    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": name, "prompt": "fictional", "manual_review": ["pending"]}
                    for name in ["one", "two"]
                ]
            }
        )
    )
    output = tmp_path / "model-run"
    monkeypatch.setattr(evaluator, "freeze_source", lambda target: {})
    monkeypatch.setattr(
        evaluator.subprocess, "check_output", lambda *args, **kwargs: "test-cli"
    )
    called = []

    def failed(cli, case, *args):
        called.append(case["id"])
        return {
            "case": case["id"],
            "exit_code": 1,
            "mechanical_checks_passed": False,
            "failures": ["execution_failed_or_empty_answer"],
        }

    monkeypatch.setattr(evaluator, "run_case", failed)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_agent",
            "--codex",
            "test-cli",
            "--stop-on-execution-failure",
            "--cases-file",
            str(dataset),
            "--output",
            str(output),
        ],
    )
    assert evaluator.main() == 1
    assert called == ["one"]
    report = json.loads((output / "report.json").read_text())
    assert report["selected_case_count"] == 2
    assert report["unrun_case_ids"] == ["two"]
    assert not report["mechanical_checks_passed"]

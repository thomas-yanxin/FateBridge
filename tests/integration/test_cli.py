"""CLI surface tests — the CLI is built from the same central tool catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from fatebridge.application.execution import result_is_error
from fatebridge.cli import run
from fatebridge.cli_arguments import _BooleanFlagAction
from fatebridge.services.tool_catalog import CATALOG


def test_missing_required_flag_emits_json_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A missing required flag is an argparse-level error. It must still land on
    # stdout as valid JSON (not an empty stdout + usage text on stderr), so an
    # agent that parses stdout gets actionable feedback instead of a PARSE-ERR.
    code = run(["bazi_wealth", "--birth-year", "1990"])  # missing month/day/hour
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 2
    assert payload["error_code"] == "usage_error"
    assert "birth" in payload["error"]


def test_result_is_error_uses_shared_envelope() -> None:
    assert result_is_error({"error": "x"}) is True
    assert result_is_error({"ok": 1}) is False


def test_cli_runs_bazi_dimension(capsys: pytest.CaptureFixture[str]) -> None:
    code = run(
        [
            "bazi_romance",
            "--birth-year",
            "1990",
            "--birth-month",
            "6",
            "--birth-day",
            "15",
            "--birth-hour",
            "10",
            "--gender",
            "male",
            "--dayun-pillar",
            "壬戌",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["analysis_type"] == "八字正缘桃花分析"
    assert "romance_analysis" in payload
    assert isinstance(payload.get("run_metadata"), dict)


def test_cli_fields_projection_trims_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(
        [
            "bazi_romance",
            "--birth-year",
            "1990",
            "--birth-month",
            "6",
            "--birth-day",
            "15",
            "--birth-hour",
            "10",
            "--gender",
            "male",
            "--dayun-pillar",
            "壬戌",
            "--fields",
            "analysis_type",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert set(payload) <= {"analysis_type", "run_metadata"}
    assert payload["analysis_type"] == "八字正缘桃花分析"
    assert "romance_analysis" not in payload


def test_cli_fields_dotted_subpath_prunes_block(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(
        [
            "bazi_birth_chart",
            "--birth-year",
            "1990",
            "--birth-month",
            "6",
            "--birth-day",
            "15",
            "--birth-hour",
            "10",
            "--gender",
            "male",
            "--fields",
            "bazi_birth.day_master",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert set(payload) <= {"bazi_birth", "run_metadata"}
    assert set(payload["bazi_birth"]) == {"day_master"}
    assert "element" in payload["bazi_birth"]["day_master"]
    assert isinstance(payload.get("run_metadata"), dict)


def test_cli_runs_knowledge_read(capsys: pytest.CaptureFixture[str]) -> None:
    code = run(
        ["knowledge_read", "--domain", "bazi", "--category", "wealth", "--key", "财库"]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["title"].startswith("财库")


def test_discover_flat_tool_emits_schema_and_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(["discover", "bazi_wealth"])
    out = capsys.readouterr().out
    info = json.loads(out)
    assert code == 0
    assert "tools" not in info
    assert info["tool"] == "bazi_wealth"
    assert info["surfaces"]["cli"] is True
    assert info["surfaces"]["rest"] == "/api/bazi/wealth"
    assert info["input_schema"]["properties"]["birth_year"]["type"] == "integer"
    assert "birth_year" in info["input_schema"]["required"]
    assert info["cli_example"].startswith("fatebridge bazi_wealth")
    assert "--birth-year" in info["cli_example"]


def test_discover_relationship_tool_lists_shared_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(["discover", "relationship_chart"])
    out = capsys.readouterr().out
    info = json.loads(out)
    assert code == 0
    assert info["tool"] == "relationship_chart"
    assert info["surfaces"]["rest"] == "/api/astrology/relationship-chart"
    assert info["surfaces"]["cli"] is True
    assert info["cli_example"].startswith("fatebridge relationship_chart")


def test_discover_multi_tool_brief_mode_and_lazy_catalog_parity(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import subprocess
    import sys

    from fatebridge.services.tool_catalog import _TOOL_MODULE_BY_NAME

    assert set(_TOOL_MODULE_BY_NAME) == {spec.name for spec in CATALOG}

    assert (
        run(["discover", "qimen", "liuren_chart", "jinkou", "--detail", "brief"]) == 0
    )
    brief_payload = json.loads(capsys.readouterr().out)
    assert brief_payload["detail"] == "brief"
    assert brief_payload["matched_count"] == 3
    assert [t["tool"] for t in brief_payload["tools"]] == [
        "qimen",
        "liuren_chart",
        "jinkou",
    ]
    assert "required_fields" in brief_payload["tools"][0]
    assert "fields" in brief_payload["tools"][0]
    assert "input_schema" not in brief_payload["tools"][0]

    assert run(["discover", "--tools", "qimen,liuren_chart", "--detail", "brief"]) == 0
    csv_payload = json.loads(capsys.readouterr().out)
    assert csv_payload["matched_count"] == 2

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "fatebridge",
            "discover",
            "qimen",
            "liuren_chart",
            "jinkou",
            "--detail",
            "brief",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    mod_payload = json.loads(proc.stdout)
    assert mod_payload["matched_count"] == 3


def test_discover_unknown_tool_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(["discover", "no_such_tool"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "validation_error"
    assert payload["issues"][0]["code"] == "unknown_tool"
    assert "no_such_tool" in payload["error"]


def test_discover_without_tool_returns_summary_manifest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(["discover"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["counts"]["total"] == len(CATALOG)
    assert sum(payload["families"].values()) == len(CATALOG)


def test_cli_validation_error_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Invalid month (passes argparse int parse, fails pydantic le=12) -> exit 1.
    code = run(
        [
            "bazi_wealth",
            "--birth-year",
            "1990",
            "--birth-month",
            "13",
            "--birth-day",
            "15",
            "--birth-hour",
            "10",
        ]
    )
    # The structured error shares stdout with success output (see
    # _JsonErrorParser / _emit_error): a json.loads(stdout) consumer never sees
    # an empty stdout and so never raises "Expecting value: line 1 column 1".
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 1
    assert payload["error_code"] == "validation_error"


def test_cli_invalid_input_renders_clean_error_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Bad input renders the same generic, structured error shape REST/MCP
    # use (status_code 400, validation_error) instead of a raw exception string.
    code = run(
        [
            "bazi_wealth",
            "--birth-year",
            "1990",
            "--birth-month",
            "2",
            "--birth-day",
            "31",  # Feb 31: passes argparse + pydantic le=31, fails monthrange
            "--birth-hour",
            "10",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    payload = json.loads(out)
    assert payload["status_code"] == 422
    assert payload["error_code"] == "validation_error"
    assert payload["issues"] == [
        {
            "path": "birth_date",
            "code": "invalid_calendar_date",
            "message": "无效的公历日期，请核对年、月、日及闰年。",
        }
    ]


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], False),
        (["--flag"], True),
        (["--flag", "true"], True),
        (["--flag", "false"], False),
        (["--flag=false"], False),
        (["--flag", "no"], False),
        (["--no-flag"], False),
    ],
)
def test_bool_flag_accepts_bare_negated_and_explicit_values(
    arguments: list[str], expected: bool
) -> None:
    """One flag supports both shell switch syntax and explicit boolean values."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--flag", dest="flag", action=_BooleanFlagAction, default=False)
    assert parser.parse_args(arguments).flag is expected


def test_cli_bool_flag_explicit_value_runs(capsys: pytest.CaptureFixture[str]) -> None:
    code = run(
        [
            "bazi_birth_chart",
            "--birth-year",
            "2000",
            "--birth-month",
            "12",
            "--birth-day",
            "10",
            "--birth-hour",
            "9",
            "--gender",
            "male",
            "--use-true-solar-time",
            "false",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert not result_is_error(payload)


def test_ipip_ratings_preserve_an_unanswered_interior_slot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A null rating leaves item 2 unanswered and keeps the next rating on item 3."""
    command = ["ipip_big_five", "--include", "*", "--as-of", "2026-10-12T02:00:00Z"]
    assert run([*command, "--responses", '{"1":5,"3":4}']) == 0
    expected = json.loads(capsys.readouterr().out)
    expected.pop("run_metadata", None)
    assert run([*command, "--ratings", "5", "null", "4"]) == 0
    captured = capsys.readouterr()
    actual = json.loads(captured.out)
    actual.pop("run_metadata", None)
    assert actual == expected
    assert expected["answered_count"] == 2
    assert captured.err == ""


def test_cli_astro_chart_accepts_gender_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # astrology_chart accepts --gender for uniform batch calling (same arg set as the
    # BaZi/ZiWei tools), even though gender is ignored in the chart math. It must
    # not die with `unrecognized arguments: --gender`.
    code = run(
        [
            "astrology_chart",
            "--birth-year",
            "2000",
            "--birth-month",
            "12",
            "--birth-day",
            "10",
            "--birth-hour",
            "9",
            "--birth-minute",
            "55",
            "--birth-place",
            "南通",
            "--gender",
            "男",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0, payload
    assert "error_code" not in payload or payload.get("error_code") != "usage_error"
    assert payload.get("planets")


def test_cli_bool_flag_unparseable_value_emits_json_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A non-boolean value is an argparse-level usage error: still valid JSON on
    # stdout (exit 2), carrying an actionable hint rather than an empty stdout.
    code = run(
        [
            "bazi_birth_chart",
            "--birth-year",
            "2000",
            "--birth-month",
            "12",
            "--birth-day",
            "10",
            "--birth-hour",
            "9",
            "--use-true-solar-time",
            "maybe",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 2
    assert payload["error_code"] == "usage_error"
    assert "true/false" in payload["error"]


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_request_file_supplies_required_and_optional_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A JSON request file alone (no birth flags on the command line) must drive a
    # full run: required fields satisfy argparse via relaxation, and optional
    # fields like gender reach the model instead of being shadowed by defaults.
    subject = _write(
        tmp_path / "request.json",
        json.dumps(
            {
                "name": "测试甲",
                "gender": "女",
                "birth_year": 1988,
                "birth_month": 8,
                "birth_day": 8,
                "birth_hour": 8,
                "birth_minute": 8,
                "birth_longitude": 120.0,
                "birth_timezone": "Asia/Shanghai",
                "use_true_solar_time": True,
            }
        ),
    )
    code = run(["bazi_birth_chart", "--request-file", subject, "--include", "*"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    chart = payload["bazi_birth"]
    assert chart["person_info"]["name"] == "测试甲"
    assert chart["person_info"]["gender"] == "女"  # optional field not shadowed
    assert chart["time_algorithm"] == "真太阳时"
    hour = chart["four_pillars"]["hour"]
    assert hour["stem"] + hour["branch"] == "庚辰"


def test_cli_flag_overrides_request_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subject = _write(
        tmp_path / "s.json",
        json.dumps(
            {
                "gender": "女",
                "birth_year": 1988,
                "birth_month": 8,
                "birth_day": 8,
                "birth_hour": 8,
            }
        ),
    )
    code = run(["bazi_birth_chart", "--request-file", subject, "--birth-year", "1990"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    year = payload["bazi_birth"]["four_pillars"]["year"]
    assert year["stem"] + year["branch"] == "庚午"  # 1990, not 1988 (戊辰)


def test_request_file_reused_across_tools(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subject = _write(
        tmp_path / "s.json",
        json.dumps(
            {
                "gender": "女",
                "birth_year": 1988,
                "birth_month": 8,
                "birth_day": 8,
                "birth_hour": 8,
                "birth_minute": 8,
                "birth_longitude": 120.0,
                "birth_timezone": "Asia/Shanghai",
                "use_true_solar_time": True,
            }
        ),
    )
    code = run(["ziwei_birth_chart", "--request-file", subject, "--include", "*"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    # This CLI-surface test only proves the request-file drives ziwei; the exact
    # 命宫 value belongs to the dedicated ziwei engine tests (pinned against
    # iztro), so assert structurally to stay robust across engine refinements.
    ming_gong = payload["ziwei_birth"]["ming_gong"]["ganzhi"]
    assert isinstance(ming_gong, str) and len(ming_gong) == 2


def test_request_file_missing_path_is_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(["bazi_birth_chart", "--request-file", "/no/such/file.json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "usage_error"


def test_request_file_invalid_json_is_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subject = _write(tmp_path / "bad.json", "{not valid json")
    code = run(["bazi_birth_chart", "--request-file", subject])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "usage_error"


def _full_subject(tmp_path: Path) -> str:
    return _write(
        tmp_path / "request.json",
        json.dumps(
            {
                "name": "测试甲",
                "gender": "女",
                "birth_year": 1988,
                "birth_month": 8,
                "birth_day": 8,
                "birth_hour": 8,
                "birth_minute": 8,
                "birth_longitude": 120.0,
                "birth_timezone": "Asia/Shanghai",
                "use_true_solar_time": True,
            }
        ),
    )


@pytest.mark.parametrize("value", [True, None])
def test_request_file_rejects_unknown_keys_before_calculation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    value: bool | None,
) -> None:
    subject_path = _full_subject(tmp_path)
    with open(subject_path, encoding="utf-8") as stream:
        subject = json.load(stream)
    subject["birth_huor"] = value
    _write(tmp_path / "request.json", json.dumps(subject))

    def unexpected_calculation(*args, **kwargs):
        pytest.fail("Invalid request keys must fail before any calculation")

    monkeypatch.setattr(
        "fatebridge.application.execution.execute_with_receipt", unexpected_calculation
    )
    code = run(["bazi_birth_chart", "--request-file", subject_path])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["error_code"] == "validation_error"
    assert len(payload["issues"]) == 1
    issue = payload["issues"][0]
    assert issue["path"] == "birth_huor"
    assert issue["code"] == "extra_forbidden"
    assert issue["message"] == "Extra inputs are not permitted"
    assert issue["constraints"]["suggestions"] == [
        "birth_hour",
        "birth_year",
        "birth_month",
        "birth_second",
        "birth_minute",
    ]
    assert "birth_hour" in issue["constraints"]["allowed_fields"]


@pytest.mark.parametrize(
    "command", ["bazi_birth_chart", "ziwei_birth_chart", "astrology_chart"]
)
def test_full_request_file_remains_reusable_across_current_birth_contracts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    args = [command, "--request-file", _full_subject(tmp_path)]
    if command == "astrology_chart":
        args.extend(["--birth-latitude", "30.0"])
    code = run(args)
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "error_code" not in payload


def test_request_file_rejects_tool_options_not_in_selected_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subject_path = _full_subject(tmp_path)
    with open(subject_path, encoding="utf-8") as stream:
        subject = json.load(stream)
    subject["house_system"] = 8
    _write(tmp_path / "request.json", json.dumps(subject))
    code = run(["bazi_birth_chart", "--request-file", subject_path])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert len(payload["issues"]) == 1
    issue = payload["issues"][0]
    assert issue["path"] == "house_system"
    assert issue["code"] == "extra_forbidden"
    assert issue["message"] == "Extra inputs are not permitted"
    assert "birth_hour" in issue["constraints"]["allowed_fields"]
    assert "house_system" not in issue["constraints"]["allowed_fields"]
    code = run(
        [
            "astrology_chart",
            "--request-file",
            subject_path,
            "--birth-latitude",
            "30.0",
            "--include",
            "*",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["chart_profile"]["house_system_code"] == 8


def test_cli_default_supports_runtime_projection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subject = _full_subject(tmp_path)
    as_of = "2026-10-12T12:00:00+08:00"

    assert (
        run(
            [
                "bazi_birth_chart",
                "--request-file",
                subject,
                "--as-of",
                as_of,
            ]
        )
        == 0
    )
    standalone_raw = capsys.readouterr().out
    standalone = json.loads(standalone_raw)
    assert "snapshot_text" not in standalone
    assert "runtime" not in standalone["run_metadata"]
    assert "duration_ms" in standalone["run_metadata"]
    assert standalone["run_metadata"]["replay"]["as_of"] == "2026-10-12T04:00:00Z"

    assert (
        run(
            [
                "bazi_birth_chart",
                "--request-file",
                subject,
                "--as-of",
                as_of,
                "--fields",
                "run_metadata.replay",
            ]
        )
        == 0
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_payload["run_metadata"]["replay"]["as_of"] == "2026-10-12T04:00:00Z"

    assert (
        run(
            [
                "bazi_birth_chart",
                "--request-file",
                subject,
                "--as-of",
                as_of,
                "--fields",
                "bazi_birth.day_master",
            ]
        )
        == 0
    )
    projected = json.loads(capsys.readouterr().out)
    assert set(projected["bazi_birth"]) == {"day_master"}

    assert (
        run(
            [
                "bazi_birth_chart",
                "--request-file",
                subject,
                "--as-of",
                as_of,
                "--fields",
                "bazi_birth",
                "bazi_birth.ten_gods",
            ]
        )
        == 0
    )
    expanded = json.loads(capsys.readouterr().out)["bazi_birth"]
    assert expanded["four_pillars"] == standalone["bazi_birth"]["four_pillars"]
    assert expanded["ten_gods"]

    assert (
        run(
            [
                "bazi_birth_chart",
                "--request-file",
                subject,
                "--fields",
                "bazi_birth.missing",
            ]
        )
        == 1
    )
    err = json.loads(capsys.readouterr().out)
    assert len(err["issues"]) == 1
    assert err["issues"][0]["path"] == "bazi_birth.missing"
    assert err["issues"][0]["code"] == "unknown_projection_path"
    assert err["issues"][0]["constraints"]["available"]


def test_batch_self_description_and_discover_batch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fatebridge.application.batch import MAX_BATCH_CALLS, BatchRequest

    assert run(["batch", "--schema"]) == 0
    schema_payload = json.loads(capsys.readouterr().out)
    assert schema_payload["tool"] == "batch"
    assert schema_payload["surface"] == ["cli", "rest", "mcp"]
    assert schema_payload["rest_path"] == "/api/batch"
    assert schema_payload["mcp_tool"] == "run_batch"
    assert schema_payload["limits"] == {"max_calls": MAX_BATCH_CALLS}
    assert schema_payload["cli_example"] == "fatebridge batch --request-file batch.json"
    assert "calls" in schema_payload["input_schema"]["properties"]
    BatchRequest.model_validate(schema_payload["example_input"])

    assert run(["batch", "--example"]) == 0
    example_payload = json.loads(capsys.readouterr().out)
    assert example_payload == schema_payload["example_input"]

    assert run(["discover", "batch"]) == 0
    discover_payload = json.loads(capsys.readouterr().out)
    assert discover_payload == schema_payload

    assert run(["batch"]) == 2
    usage_payload = json.loads(capsys.readouterr().out)
    assert usage_payload["error_code"] == "usage_error"


def test_cli_list_includes_batch_footer_and_preload_stdin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import io

    from fatebridge.cli_inputs import preload_request

    assert run(["list"]) == 0
    list_out = capsys.readouterr().out
    assert "batch" in list_out
    assert "--schema" in list_out

    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "birth_year": 1990,
                    "birth_month": 5,
                    "birth_day": 15,
                    "birth_hour": 10,
                    "gender": "male",
                }
            )
        ),
    )
    loaded = preload_request(["bazi_birth_chart", "--request-file", "-"])
    assert loaded is not None and loaded["birth_year"] == 1990


def test_discover_bazi_timing_examples_include_analysis_date_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for tool_name, expected_flags in (
        ("bazi_monthly_timing", ("--analysis-year", "--analysis-month")),
        (
            "bazi_daily_timing",
            ("--analysis-year", "--analysis-month", "--analysis-day"),
        ),
        (
            "bazi_hourly_timing",
            (
                "--analysis-year",
                "--analysis-month",
                "--analysis-day",
                "--analysis-hour",
            ),
        ),
        ("solar_term_timeline", ("--analysis-year",)),
        ("bazi_luck_cycles", ("--analysis-year",)),
    ):
        assert run(["discover", tool_name]) == 0
        info = json.loads(capsys.readouterr().out)
        assert "analysis_year" in info["example_input"]
        for flag in expected_flags:
            assert flag in info["cli_example"], (tool_name, flag)
    assert run(["discover", "bazi_monthly_timing"]) == 0
    monthly_info = json.loads(capsys.readouterr().out)
    assert "analysis_month" in monthly_info["example_input"]

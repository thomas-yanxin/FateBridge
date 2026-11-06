"""CLI surface tests — the CLI is built from the same central tool catalog."""

import json

import pytest

from fatebridge.application.execution import result_is_error
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.cli import run
from fatebridge.services.tool_catalog import CATALOG


def test_nested_model_tool_gives_hint_not_crash(capsys):
    # astro_relative uses a nested request model -> CLI-unsupported, but should
    # print a helpful hint (pointing at the flat variant) and exit 2. The hint
    # is JSON on stdout so a json.loads(stdout) consumer parses it cleanly.
    code = run(["astro_relative"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 2
    assert payload["error_code"] == "cli_unsupported"
    assert "astro_relative_chart" in payload["error"]


def test_missing_required_flag_emits_json_on_stdout(capsys):
    # A missing required flag is an argparse-level error. It must still land on
    # stdout as valid JSON (not an empty stdout + usage text on stderr), so an
    # agent that parses stdout gets actionable feedback instead of a PARSE-ERR.
    code = run(["bazi_wealth", "--birth-year", "1990"])  # missing month/day/hour
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 2
    assert payload["error_code"] == "usage_error"
    assert "birth" in payload["error"]


def test_result_is_error_honors_error_is_fatal():
    base = next(s for s in CATALOG if s.rest_path == "/api/cn/bazi/wealth")
    assert result_is_error(base, {"error": "x"}) is True
    assert result_is_error(base, {"ok": 1}) is False
    lenient = ToolSpec(
        key="t",
        bind=base.bind,
        request_model=base.request_model,
        summary="t",
        operation_label_zh="t",
        family="t",
        error_is_fatal=lambda r: False,
    )
    assert result_is_error(lenient, {"error": "non-fatal"}) is False


def test_cli_runs_bazi_dimension(capsys):
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


def test_cli_fields_projection_trims_payload(capsys):
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


def test_cli_fields_dotted_subpath_prunes_block(capsys):
    code = run(
        [
            "bazi_birth",
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


def test_cli_runs_knowledge_read(capsys):
    code = run(
        ["knowledge_read", "--domain", "bazi", "--category", "wealth", "--key", "财库"]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["title"].startswith("财库")


def test_describe_flat_tool_emits_schema_and_example(capsys):
    code = run(["describe", "bazi_wealth"])
    out = capsys.readouterr().out
    info = json.loads(out)
    assert code == 0
    assert info["tool"] == "bazi_wealth"
    assert info["surfaces"]["cli"] is True
    assert info["surfaces"]["rest_path"] == "/api/cn/bazi/wealth"
    by = next(p for p in info["parameters"] if p["name"] == "birth_year")
    assert by["required"] is True
    assert by["type"] == "int"
    assert by["flag"] == "--birth-year"
    assert by["description"]
    assert info["cli_example"].startswith("fatebridge bazi_wealth")
    assert "--birth-year" in info["cli_example"]


def test_describe_nested_tool_still_describes_with_hint(capsys):
    # Nested-model tools can't run on the CLI, but describe must still work and
    # point the agent at the right surface.
    code = run(["describe", "astro_relative"])
    out = capsys.readouterr().out
    info = json.loads(out)
    assert code == 0
    assert info["surfaces"]["cli"] is False
    assert "cli_hint" in info
    assert "cli_example" not in info


def test_describe_unknown_tool_returns_nonzero(capsys):
    code = run(["describe", "no_such_tool"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "unknown_tool"
    assert "no_such_tool" in payload["error"]


def test_describe_without_tool_returns_usage(capsys):
    code = run(["describe"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "usage_error"
    assert "describe" in payload["error"]


def test_cli_validation_error_returns_nonzero(capsys):
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


def test_cli_invalid_input_renders_clean_error_shape(capsys):
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
        {"path": "birth_date", "code": "invalid_calendar_date"}
    ]


def _bool_flag_parser():
    import argparse

    from fatebridge.cli import _BooleanFlagAction

    parser = argparse.ArgumentParser()
    parser.add_argument("--flag", dest="flag", action=_BooleanFlagAction, default=False)
    return parser


def test_bool_flag_accepts_bare_negated_and_explicit_values():
    parser = _bool_flag_parser()
    assert parser.parse_args([]).flag is False
    assert parser.parse_args(["--flag"]).flag is True
    assert parser.parse_args(["--flag", "true"]).flag is True
    assert parser.parse_args(["--flag", "false"]).flag is False
    assert parser.parse_args(["--flag=false"]).flag is False
    assert parser.parse_args(["--flag", "no"]).flag is False
    assert parser.parse_args(["--no-flag"]).flag is False


def test_cli_bool_flag_explicit_value_runs(capsys):
    code = run(
        [
            "bazi_birth",
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
    assert not result_is_error(
        next(s for s in CATALOG if (s.mcp_name or s.key) == "bazi_birth"), payload
    )


def test_cli_astro_chart_accepts_gender_flag(capsys):
    # astro_chart accepts --gender for uniform batch calling (same arg set as the
    # BaZi/ZiWei tools), even though gender is ignored in the chart math. It must
    # not die with `unrecognized arguments: --gender`.
    code = run(
        [
            "astro_chart",
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
    assert payload.get("snapshot_text")


def test_cli_bool_flag_unparseable_value_emits_json_usage_error(capsys):
    # A non-boolean value is an argparse-level usage error: still valid JSON on
    # stdout (exit 2), carrying an actionable hint rather than an empty stdout.
    code = run(
        [
            "bazi_birth",
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


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_subject_file_supplies_required_and_optional_fields(tmp_path, capsys):
    # A JSON profile alone (no birth flags on the command line) must drive a
    # full run: required fields satisfy argparse via relaxation, and optional
    # fields like gender reach the model instead of being shadowed by defaults.
    subject = _write(
        tmp_path / "subject.json",
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
    code = run(["bazi_birth", "--subject-file", subject])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    chart = payload["bazi_birth"]
    assert chart["person_info"]["name"] == "测试甲"
    assert chart["person_info"]["gender"] == "女"  # optional field not shadowed
    assert chart["time_algorithm"] == "真太阳时"
    hour = chart["four_pillars"]["hour"]
    assert hour["stem"] + hour["branch"] == "庚辰"


def test_cli_flag_overrides_subject_file(tmp_path, capsys):
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
    code = run(["bazi_birth", "--subject-file", subject, "--birth-year", "1990"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    year = payload["bazi_birth"]["four_pillars"]["year"]
    assert year["stem"] + year["branch"] == "庚午"  # 1990, not 1988 (戊辰)


def test_subject_file_reused_across_tools(tmp_path, capsys):
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
    code = run(["ziwei_birth", "--subject-file", subject])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    # This CLI-surface test only proves the subject-file drives ziwei; the exact
    # 命宫 value belongs to the dedicated ziwei engine tests (pinned against
    # iztro), so assert structurally to stay robust across engine refinements.
    ming_gong = payload["ziwei_birth"]["ming_gong"]["ganzhi"]
    assert isinstance(ming_gong, str) and len(ming_gong) == 2


def test_subject_file_missing_path_is_usage_error(capsys):
    code = run(["bazi_birth", "--subject-file", "/no/such/file.json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "usage_error"


def test_subject_file_yaml_is_supported(tmp_path, capsys):
    import importlib.util

    if importlib.util.find_spec("yaml") is None:  # optional dependency
        import pytest

        pytest.skip("pyyaml not installed")
    subject = _write(
        tmp_path / "s.yaml",
        "gender: 女\nbirth_year: 1988\nbirth_month: 8\nbirth_day: 8\n"
        "birth_hour: 8\n",
    )
    code = run(["bazi_birth", "--subject-file", subject])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["bazi_birth"]["person_info"]["gender"] == "女"


def _full_subject(tmp_path):
    return _write(
        tmp_path / "subject.json",
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
                "birth_latitude": 30.0,
                "birth_timezone": "Asia/Shanghai",
                "use_true_solar_time": True,
            }
        ),
    )


def test_profile_runs_default_three_systems(tmp_path, capsys):
    code = run(["profile", "--subject-file", _full_subject(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["analysis_type"] == "综合命盘"
    assert payload["systems"] == ["bazi", "ziwei", "astro"]
    chart = payload["profile"]
    hour = chart["bazi"]["bazi_birth"]["four_pillars"]["hour"]
    assert hour["stem"] + hour["branch"] == "庚辰"
    # ziwei ran from the shared subject; the exact 命宫 value is owned by the
    # dedicated ziwei engine tests (pinned to iztro), so assert structurally.
    ming_gong = chart["ziwei"]["ziwei_birth"]["ming_gong"]["ganzhi"]
    assert isinstance(ming_gong, str) and len(ming_gong) == 2
    assert "angles" in chart["astro"]


def test_profile_accepts_aliases_and_subset(tmp_path, capsys):
    code = run(
        ["profile", "--systems", "八字,健康", "--subject-file", _full_subject(tmp_path)]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert list(payload["profile"].keys()) == ["八字", "健康"]


def test_profile_cli_flag_overrides_subject(tmp_path, capsys):
    code = run(
        [
            "profile",
            "--systems",
            "bazi",
            "--subject-file",
            _full_subject(tmp_path),
            "--birth-year",
            "1990",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    year = payload["profile"]["bazi"]["bazi_birth"]["four_pillars"]["year"]
    assert year["stem"] + year["branch"] == "庚午"  # 1990 wins over file's 1988


def test_profile_legs_share_one_birth_instant_when_tz_omitted(tmp_path, capsys):
    # Regression: the astro leg's model once defaulted birth_timezone='UTC'. Left
    # to that default, the western leg interpreted a China wall-clock time as UTC,
    # landing ~8h off the Chinese legs (e.g. 09:55 -> 18:0x UTC) and producing a
    # wholly rotated, bogus chart. The profile must resolve ONE timezone
    # (place-derived) and feed every leg the same civil instant. True-solar policy
    # is intentionally per-tradition: the Chinese legs rebase onto apparent solar
    # time, the western leg stays on the civil clock.
    subject = _write(
        tmp_path / "s.json",
        json.dumps(
            {
                "name": "陆遥",
                "gender": "男",
                "birth_year": 2000,
                "birth_month": 12,
                "birth_day": 10,
                "birth_hour": 9,
                "birth_minute": 55,
                "birth_place": "上海",
                "birth_longitude": 121.47,
                "birth_latitude": 31.23,
                # NOTE: deliberately NO birth_timezone and NO use_true_solar_time
            }
        ),
    )
    code = run(["profile", "--systems", "bazi,astro", "--subject-file", subject])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    astro_pi = payload["profile"]["astro"]["person_info"]
    # The western leg must adopt the canonical China timezone, never the raw
    # 'UTC' model default that caused the double offset.
    assert astro_pi["birth_timezone"] != "UTC"
    assert astro_pi["birth_timezone"] == "Asia/Shanghai"
    # A 09:55 China morning is an early-UTC instant (~01-02h), never ~18h.
    assert astro_pi["utc_datetime"].startswith("2000-12-10T01") or astro_pi[
        "utc_datetime"
    ].startswith("2000-12-10T02")
    # Per-tradition true-solar policy: the western leg stays on the civil clock,
    # while the BaZi leg rebases onto apparent solar time. They share the resolved
    # timezone (one instant), not one correction policy.
    assert astro_pi["true_solar"]["applied"] is False
    assert payload["profile"]["bazi"]["bazi_birth"]["time_algorithm"] == "真太阳时"


def test_profile_unifies_instant_even_for_uncatalogued_place(tmp_path, capsys):
    # 海安 is not in the offline place catalog, so no timezone can be derived
    # from the name. The BaZi normalizer falls back to DEFAULT_BIRTH_TIMEZONE
    # (Asia/Shanghai); the profile must apply the SAME fallback to the astro leg
    # so an uncatalogued China birth does not silently leave the western leg on
    # its 'UTC' default (the original bug for this very subject).
    subject = _write(
        tmp_path / "s.json",
        json.dumps(
            {
                "name": "X",
                "gender": "男",
                "birth_year": 2000,
                "birth_month": 12,
                "birth_day": 10,
                "birth_hour": 9,
                "birth_minute": 55,
                "birth_place": "海安",
                "birth_longitude": 120.45,
                "birth_latitude": 32.54,
            }
        ),
    )
    code = run(["profile", "--systems", "bazi,astro", "--subject-file", subject])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    astro_pi = payload["profile"]["astro"]["person_info"]
    assert astro_pi["birth_timezone"] != "UTC"
    # 09:55 +08:00 (with a small true-solar shift) is an early-UTC instant.
    assert astro_pi["utc_datetime"].startswith("2000-12-10T0")


def test_profile_unknown_system_is_usage_error(tmp_path, capsys):
    code = run(
        ["profile", "--systems", "bazi,foo", "--subject-file", _full_subject(tmp_path)]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "usage_error"
    assert "foo" in payload["error"]


def test_profile_missing_required_is_usage_error(capsys):
    code = run(["profile", "--systems", "bazi"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error_code"] == "usage_error"
    assert "birth" in payload["error"]


@pytest.mark.parametrize("value", [True, None])
@pytest.mark.parametrize("command", ["bazi_birth", "profile"])
def test_subject_file_rejects_unknown_keys_before_calculation(
    tmp_path, capsys, monkeypatch, command, value
):
    subject_path = _full_subject(tmp_path)
    with open(subject_path, encoding="utf-8") as stream:
        subject = json.load(stream)
    subject["birth_huor"] = value
    _write(tmp_path / "subject.json", json.dumps(subject))

    def unexpected_calculation(*args, **kwargs):
        pytest.fail("Invalid subject keys must fail before any calculation")

    monkeypatch.setattr("fatebridge.cli.execute_tool", unexpected_calculation)
    code = run([command, "--subject-file", subject_path, "--trace-id", "subject-typo"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["error_code"] == "validation_error"
    assert payload["issues"] == [{"path": "birth_huor", "code": "extra_forbidden"}]
    assert payload["trace_id"] == "subject-typo"


@pytest.mark.parametrize("command", ["bazi_birth", "ziwei_birth", "astro_chart"])
def test_full_subject_file_remains_reusable_across_current_birth_contracts(
    tmp_path, capsys, command
):
    code = run([command, "--subject-file", _full_subject(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "error_code" not in payload


def test_subject_file_rejects_tool_options_not_in_selected_contract(tmp_path, capsys):
    subject_path = _full_subject(tmp_path)
    with open(subject_path, encoding="utf-8") as stream:
        subject = json.load(stream)
    subject["hsys"] = 8
    _write(tmp_path / "subject.json", json.dumps(subject))
    code = run(["bazi_birth", "--subject-file", subject_path])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["issues"] == [{"path": "hsys", "code": "extra_forbidden"}]
    code = run(["astro_chart", "--subject-file", subject_path])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["chart_profile"]["house_system_code"] == 8

"""Explicit file null is input data; omission and CLI override stay distinct."""

import asyncio
import json

import pytest

from fatebridge.cli import run
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize("field", ["lookup_mode", "selected_sections"])
def test_subject_null_nonnullable_field_is_rejected_on_three_protocols(
    field, rest, tmp_path, capsys
):
    spec = SPECS["gua_lookup"]
    payload = {"query": "111111", field: None}
    http = rest.post(spec.rest_path, json=payload)
    protocol = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert http.status_code == 422 and protocol.is_error and code != 0
    assert http.json()["error_code"] == cli["error_code"] == "validation_error"
    assert field in str(cli["issues"])


def test_explicit_cli_flag_overrides_null_subject_value(tmp_path, capsys):
    subject = tmp_path / "null-lookup.json"
    subject.write_text(json.dumps({"query": "111111", "lookup_mode": None}))
    code = run(
        [
            "gua_lookup",
            "--subject-file",
            str(subject),
            "--lookup-mode",
            "hexagram",
            "--response-char-limit",
            "0",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0 and "error_code" not in output


def test_profile_keeps_explicit_null_instead_of_default_zero(tmp_path, capsys):
    subject = tmp_path / "null-minute.json"
    subject.write_text(
        json.dumps(
            dict(
                birth_year=1990,
                birth_month=1,
                birth_day=1,
                birth_hour=12,
                birth_minute=None,
                birth_timezone="UTC",
                use_true_solar_time=False,
            )
        )
    )
    code = run(
        [
            "profile",
            "--systems",
            "bazi",
            "--subject-file",
            str(subject),
            "--response-char-limit",
            "0",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code != 0
    child = output["profile"]["bazi"]
    assert child["error_code"] == "validation_error"
    assert "birth_minute" in str(child["issues"])
    assert "bazi_birth" not in child


def test_omitted_optional_value_still_uses_declared_default(tmp_path, capsys):
    subject = tmp_path / "omitted-lookup.json"
    subject.write_text(json.dumps({"query": "111111"}))
    code = run(
        ["gua_lookup", "--subject-file", str(subject), "--response-char-limit", "0"]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0 and "error_code" not in output

"""Projection, snapshot controls and default output across REST and CLI."""

import json

import pytest
from fastapi.testclient import TestClient

import fatebridge.api as api_module
from fatebridge.cli import run

_BAZI_BIRTH_PATH = "/api/cn/bazi/birth"
_BAZI_BIRTH_BODY = {
    "name": "测试者",
    "birth_year": 1990,
    "birth_month": 6,
    "birth_day": 15,
    "birth_hour": 10,
    "gender": "male",
    "birth_place": "北京",
}
_BAZI_BIRTH_CLI = [
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
    "--birth-place",
    "北京",
]


def _build_client(monkeypatch) -> TestClient:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api_module.app)


# --------------------------------------------------------------------------- #
# REST                                                                         #
# --------------------------------------------------------------------------- #


def test_rest_default_preserves_full_payload(monkeypatch):
    """Default REST responses include the snapshot and structured result."""
    client = _build_client(monkeypatch)
    body = client.post(_BAZI_BIRTH_PATH, json=_BAZI_BIRTH_BODY).json()
    assert "snapshot_text" in body
    assert "bazi_birth" in body
    assert isinstance(body.get("run_metadata"), dict)


def test_rest_include_snapshot_text_false_strips_it(monkeypatch):
    client = _build_client(monkeypatch)
    body = client.post(
        _BAZI_BIRTH_PATH,
        json=_BAZI_BIRTH_BODY,
        params={"include_snapshot_text": "false"},
    ).json()
    assert "snapshot_text" not in body
    # The structured block and provenance still survive.
    assert "bazi_birth" in body
    assert isinstance(body.get("run_metadata"), dict)


def test_rest_fields_query_param_projects_dotted_subpath(monkeypatch):
    client = _build_client(monkeypatch)
    body = client.post(
        _BAZI_BIRTH_PATH,
        json=_BAZI_BIRTH_BODY,
        params={"fields": ["bazi_birth.day_master"]},
    ).json()
    # Heavy block pruned to just the requested sub-key; run_metadata always kept.
    assert set(body) <= {"bazi_birth", "run_metadata"}
    assert set(body["bazi_birth"]) == {"day_master"}
    assert "element" in body["bazi_birth"]["day_master"]
    assert isinstance(body.get("run_metadata"), dict)


def test_rest_reserved_field_guard_rejects_clashing_model():
    """A request model that declares a reserved transport field must fail loud."""
    from pydantic import BaseModel

    from fatebridge.application.bindings import person_invoke
    from fatebridge.application.tool_spec import ToolSpec
    from fatebridge.transports.rest import register_rest

    class _Clashing(BaseModel):
        fields: str = ""  # collides with the REST projection query param

    bad = ToolSpec(
        key="_clash",
        bind=person_invoke(lambda *_a, **_k: {}),
        request_model=_Clashing,
        summary="x",
        operation_label_zh="x",
        family="x",
        rest_path="/api/_clash",
    )

    class _DummyApp:
        def add_api_route(self, *a, **k):  # pragma: no cover - never reached
            raise AssertionError("route mounted despite reserved-field clash")

    with pytest.raises(ValueError, match="reserved"):
        register_rest(_DummyApp(), [bad], execute_service=lambda *a, **k: None)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def test_cli_default_is_pretty_with_snapshot(capsys):
    code = run(_BAZI_BIRTH_CLI)
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    assert "snapshot_text" in payload
    # CLI responses default to multi-line, indented JSON.
    assert "\n" in out.strip()


def test_cli_no_include_snapshot_text_strips_it(capsys):
    code = run(_BAZI_BIRTH_CLI + ["--no-include-snapshot-text"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    assert "snapshot_text" not in payload
    assert "bazi_birth" in payload
    assert isinstance(payload.get("run_metadata"), dict)


def test_cli_compact_emits_single_line(capsys):
    code = run(_BAZI_BIRTH_CLI + ["--compact"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)  # still valid JSON
    assert "bazi_birth" in payload
    # Compact output has no indentation newlines.
    assert "\n" not in out.strip()

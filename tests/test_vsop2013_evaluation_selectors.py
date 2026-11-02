"""Versioned optional source selectors keep legacy bytes readable and explicit."""

import hashlib
import json

import pytest

from fatebridge.validation import evaluation_environment as env

OLD_KEYS = (
    "SE_EPHE_PATH",
    "FATEBRIDGE_JPL_FILE",
    "FATEBRIDGE_SOLAR_TERM_MODEL",
    "FATEBRIDGE_SOLAR_SPK_FILE",
    "XDG_CACHE_HOME",
)
OLD_METHOD = "evaluation_native_environment_v1"
OLD_CONTEXT = "evaluation_native_environment_with_working_directory_v2"
NEW_METHOD = "evaluation_native_environment_with_optional_sources_v3"
NEW_CONTEXT = (
    "evaluation_native_environment_with_optional_sources_and_working_directory_v4"
)
VSOP = "FATEBRIDGE_VSOP2013_MANIFEST"
AA = "FATEBRIDGE_AA1996_MANIFEST"


def test_capture_keeps_full_optional_selector_values_and_explicit_nulls(tmp_path):
    source = {
        "FATEBRIDGE_SOLAR_TERM_MODEL": "vsop2013",
        VSOP: "/verified/source with spaces/manifest.json",
        "OPENAI_API_KEY": "private",
    }
    chosen = env.capture_selection(source)
    assert chosen[VSOP] == source[VSOP] and chosen[AA] is None
    raw = env.selection_bytes(chosen)
    assert json.loads(raw)["method_id"] == NEW_METHOD and b"private" not in raw
    p = tmp_path / "selected.json"
    p.write_bytes(raw)
    actual, original = env.load_selection(p, hashlib.sha256(raw).hexdigest())
    assert actual == chosen and original == raw
    assert json.loads(env.context_bytes(chosen, tmp_path))["method_id"] == NEW_CONTEXT


@pytest.mark.parametrize("context", [False, True])
def test_legacy_records_remain_readable_without_invented_source_selectors(
    context, tmp_path
):
    values = {key: None for key in OLD_KEYS}
    values["SE_EPHE_PATH"] = "relative ephe"
    data = dict(method_id=OLD_CONTEXT if context else OLD_METHOD, values=values)
    if context:
        data["working_directory"] = dict(flavor="posix", path=str(tmp_path))
    raw = (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    p = tmp_path / "legacy.json"
    p.write_bytes(raw)
    actual, original = env.load_selection(p, hashlib.sha256(raw).hexdigest())
    assert (
        actual == values and original == raw and VSOP not in actual and AA not in actual
    )
    assert (
        env.selection_bytes(actual)
        == (
            json.dumps(
                dict(method_id=OLD_METHOD, values=values),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode()
    )
    if context:
        assert env.context_bytes(actual, tmp_path) == raw


@pytest.mark.parametrize("method,extended", [(OLD_METHOD, True), (NEW_METHOD, False)])
def test_recomputed_hash_cannot_change_the_versioned_selector_shape(
    method, extended, tmp_path
):
    values = {key: None for key in OLD_KEYS}
    if extended:
        values.update({VSOP: None, AA: None})
    raw = json.dumps(dict(method_id=method, values=values)).encode()
    p = tmp_path / "wrong-shape.json"
    p.write_bytes(raw)
    with pytest.raises(ValueError):
        env.load_selection(p, hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("legacy", [False, True])
def test_later_ambient_optional_sources_are_cleared_without_mutating_caller(legacy):
    chosen = {key: None for key in OLD_KEYS} if legacy else env.capture_selection({})
    ambient = {
        VSOP: "/later/vsop.json",
        AA: "/later/aa.json",
        "OPENAI_API_KEY": "private",
    }
    result = env.process_environment(chosen, ambient)
    assert VSOP not in result and AA not in result
    assert result["OPENAI_API_KEY"] == "private" and ambient[VSOP] == "/later/vsop.json"


def test_command_builder_forwards_only_frozen_optional_selectors(monkeypatch, tmp_path):
    from scripts.evaluate_agent import command_for

    selected = env.capture_selection(
        {"FATEBRIDGE_SOLAR_TERM_MODEL": "vsop2013", VSOP: "/frozen/manifest.json"}
    )
    monkeypatch.setenv(VSOP, "/later/manifest.json")
    command = command_for("codex", tmp_path, tmp_path, {}, native_selection=selected)
    settings = {
        command[i + 1].split("=", 1)[0]: json.loads(command[i + 1].split("=", 1)[1])
        for i, token in enumerate(command[:-1])
        if token == "-c"
    }
    assert settings["mcp_servers.fatebridge.env." + VSOP] == "/frozen/manifest.json"
    assert "mcp_servers.fatebridge.env." + AA not in settings
    assert not any("API_KEY" in key for key in settings)

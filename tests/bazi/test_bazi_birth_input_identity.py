"""Input identity includes the component presence that changes the receipt."""

import asyncio

import pytest

from tests.bazi.test_bazi_birth_component_presence import omitted_payload
from tests.bazi.test_bazi_birth_seconds import SPECS
from tests.bazi.test_bazi_birth_seconds_transports import leaf, receipt_path
from tests.support.transports import AS_OF, call_cli, native
from tests.support.transports import rest as _shared_rest


def test_mcp_omitted_and_explicit_zero_minute_have_distinct_input_identity():
    spec = next(s for s in SPECS if s.key == "bazi_birth")
    payload = omitted_payload(spec)
    opts = dict(
        fields=[receipt_path(spec)], strict_fields=True, include_snapshot_text=False
    )
    omitted = asyncio.run(native(spec, payload, **opts)).structured_content
    explicit = asyncio.run(
        native(spec, {**payload, "birth_minute": 0}, **opts)
    ).structured_content
    assert leaf(omitted, receipt_path(spec))["omitted_components"] == [
        "minute",
        "second",
    ]
    assert leaf(explicit, receipt_path(spec))["omitted_components"] == ["second"]
    assert leaf(omitted, receipt_path(spec)) != leaf(explicit, receipt_path(spec))


rest = _shared_rest


@pytest.mark.parametrize(
    "key", ["analyze_destiny", "bazi_birth", "bazi_career", "dayun_analysis"]
)
def test_original_input_replay_and_identity_agree_across_actual_surfaces(
    key, rest, tmp_path, capsys
):
    spec = next(s for s in SPECS if s.key == key)
    payload = omitted_payload(spec)
    opts = dict(
        fields=[receipt_path(spec)], strict_fields=True, include_snapshot_text=False
    )
    flags = [
        "--fields",
        receipt_path(spec),
        "--strict-fields",
        "true",
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        "0",
    ]
    first = asyncio.run(native(spec, payload, **opts)).structured_content
    replay = first["run_metadata"]["replay"]
    # Replay uses the original input, rather than a model dump with defaults.
    assert replay["requires_original_input"] is True and replay["as_of"] == AS_OF
    code, cli = call_cli(
        spec, {**payload, **replay["overrides"]}, tmp_path, capsys, flags=flags
    )
    assert code == 0
    all_values = [first, cli]
    if spec.rest_path:
        response = rest.post(
            spec.rest_path,
            json=payload,
            params={"as_of": replay["as_of"], "response_char_limit": 0, **opts},
        )
        assert response.status_code == 200
        all_values.append(response.json())
    assert all(
        leaf(d, receipt_path(spec)) == leaf(first, receipt_path(spec))
        for d in all_values
    )
    assert all(d["run_metadata"]["replay"] == replay for d in all_values)


def test_null_second_and_omitted_second_keep_the_same_unknown_input_identity():
    spec = next(s for s in SPECS if s.key == "bazi_birth")
    payload = {**omitted_payload(spec), "birth_minute": 0}
    opts = dict(
        fields=[receipt_path(spec)], strict_fields=True, include_snapshot_text=False
    )
    a = asyncio.run(native(spec, payload, **opts)).structured_content
    b = asyncio.run(
        native(spec, {**payload, "birth_second": None}, **opts)
    ).structured_content
    assert leaf(a, receipt_path(spec)) == leaf(b, receipt_path(spec))
    assert a["run_metadata"]["replay"] == b["run_metadata"]["replay"]

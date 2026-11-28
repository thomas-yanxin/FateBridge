"""Input identity includes the component presence that changes the receipt."""

import asyncio
from pathlib import Path

import pytest

from tests.support.transports import AS_OF, call_cli, native
from tests.support.transports import rest as _shared_rest
from tests.unit_test.fixtures.bazi_birth_clock import (
    SPECS,
    leaf,
    omitted_payload,
    receipt_path,
)


def test_mcp_omitted_and_explicit_zero_minute_have_distinct_input_identity() -> None:
    spec = next(s for s in SPECS if s.name == "bazi_birth_chart")
    payload = omitted_payload(spec)
    opts = dict(fields=[receipt_path(spec)])
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
    "name", ["bazi_overview", "bazi_birth_chart", "bazi_career", "bazi_luck_cycles"]
)
def test_original_input_replay_and_identity_agree_across_actual_surfaces(
    name: str, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = next(s for s in SPECS if s.name == name)
    payload = omitted_payload(spec)
    opts = dict(fields=[receipt_path(spec)])
    flags = [
        "--fields",
        receipt_path(spec),
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
            params={"as_of": replay["as_of"], **opts},
        )
        assert response.status_code == 200
        all_values.append(response.json())
    else:
        pass
    assert all(
        leaf(d, receipt_path(spec)) == leaf(first, receipt_path(spec))
        for d in all_values
    )
    assert all(d["run_metadata"]["replay"] == replay for d in all_values)


def test_null_second_and_omitted_second_keep_the_same_unknown_input_identity() -> None:
    spec = next(s for s in SPECS if s.name == "bazi_birth_chart")
    payload = {**omitted_payload(spec), "birth_minute": 0}
    opts = dict(fields=[receipt_path(spec)])
    a = asyncio.run(native(spec, payload, **opts)).structured_content
    b = asyncio.run(
        native(spec, {**payload, "birth_second": None}, **opts)
    ).structured_content
    assert leaf(a, receipt_path(spec)) == leaf(b, receipt_path(spec))
    assert a["run_metadata"]["replay"] == b["run_metadata"]["replay"]

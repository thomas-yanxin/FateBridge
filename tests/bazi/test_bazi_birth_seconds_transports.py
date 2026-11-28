"""The actual public BaZi/timing surfaces retain the same clock evidence."""

import asyncio
from pathlib import Path

import pytest

from tests.support.transports import AS_OF, business, call_cli, inputs, native
from tests.support.transports import rest as _shared_rest
from tests.unit_test.fixtures.bazi_birth_clock import BASE, SPECS, leaf, receipt_path

rest = _shared_rest


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
@pytest.mark.parametrize("project", [False, True])
def test_seconds_and_component_receipt_on_every_actual_surface(
    spec,
    project: bool,
    rest,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    payload = {**inputs(spec), **BASE, "birth_minute": 20, "birth_second": 59}
    opts: dict[str, object] = {}
    flags: list[str] = []
    if project:
        opts["fields"] = [receipt_path(spec)]
        flags += ["--fields", receipt_path(spec)]
    else:
        opts["include"] = ["*"]
        flags += ["--include", "*"]
    result = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert not result.is_error and code == 0
    observed = [result.structured_content, cli]
    assert business(observed[0]) == business(observed[1])
    if spec.rest_path is not None:
        response = rest.post(
            spec.rest_path, json=payload, params={"as_of": AS_OF, **opts}
        )
        assert response.status_code == 200, response.text
        observed.append(response.json())
        assert business(observed[0]) == business(observed[2])
    else:
        assert spec.name == "bazi_overview"
    for data in observed:
        receipt = leaf(data, receipt_path(spec))
        assert receipt["supplied_components"] == [
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
        ]
        assert receipt["nominal_civil_datetime"] == "1990-05-15T10:20:59+00:00"
        assert (
            receipt["calculation_defaults"] == {}
            and receipt["omitted_components"] == []
        )
        assert receipt["observed_precision_certified"] is False
        spec.output_model.model_validate(data)
        if not project:
            birth = data.get("bazi_birth", data)
            person = birth.get("person_info", birth.get("personal_info"))
            if person is not None:
                assert (
                    ":59" in person["birth_datetime"]
                    or "59秒" in person["birth_datetime"]
                )
            else:
                assert spec.family == "bazi" and spec.name not in {
                    "bazi_birth_chart",
                    "bazi_overview",
                }
        else:
            pass


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_invalid_second_reaches_no_complete_report_on_every_actual_surface(
    spec, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {**inputs(spec), **BASE, "birth_minute": 20, "birth_second": 60}
    result = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert result.is_error and code != 0
    assert "four_pillars" not in cli and "bazi_birth" not in cli
    if spec.rest_path is not None:
        response = rest.post(spec.rest_path, json=payload)
        assert response.status_code == 422, response.text
    else:
        pass

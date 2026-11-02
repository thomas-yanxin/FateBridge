"""Direct CLI flags preserve a declared textual branch before model validation."""

import argparse
import json
from typing import Annotated, Optional, Union

import pytest
from pydantic import BaseModel, Field, StrictInt

import fatebridge.cli as cli
from tests.test_gauquelin_request_guard import HOUSE_SPECS, payload


@pytest.mark.parametrize(
    "annotation",
    [
        Union[int, str],
        Optional[Union[int, str]],
        int | str,
        Annotated[Union[int, str], "example"],
    ],
)
def test_textual_union_branch_is_not_discarded(annotation):
    assert cli._argument_type(annotation) is str


def test_numeric_strictness_optional_and_list_items_still_reach_pydantic_as_integers():
    class Numeric(BaseModel):
        count: Optional[StrictInt] = None
        items: list[Annotated[int, Field(ge=0)]]

    parser = argparse.ArgumentParser()
    for name, field in Numeric.model_fields.items():
        cli._add_field_argument(parser, name, field)
    namespace = parser.parse_args(["--count", "3", "--items", "0", "2"])
    result = Numeric.model_validate(vars(namespace))
    assert result.count == 3 and result.items == [0, 2]
    assert type(namespace.count) is int


@pytest.mark.parametrize(
    "value,expected", [("P", "P"), ("R", "R"), ("X", "X"), ("3", "P"), ("8", "D")]
)
def test_supported_house_flags_on_every_live_tool_reach_the_shared_dispatch(
    value, expected, monkeypatch, tmp_path, capsys
):
    from fatebridge.utils.house_systems import normalize_house_system

    captured = []

    def stop_at_dispatch(spec, request, *args, **kwargs):
        captured.append((spec.key, request.house_system))
        return {
            "error": "test_dispatch_spy",
            "error_code": "test_dispatch_spy",
            "retryable": False,
        }

    monkeypatch.setattr(cli, "execute_tool", stop_at_dispatch)
    for spec in HOUSE_SPECS:
        subject = tmp_path / f"{spec.key}.json"
        subject.write_text(
            json.dumps({k: v for k, v in payload(spec).items() if k != "house_system"})
        )
        capsys.readouterr()
        code = cli.run(
            [spec.tool_name, "--subject-file", str(subject), "--house-system", value]
        )
        result = json.loads(capsys.readouterr().out)
        # This is a dispatch spy, never a fabricated successful calculation.
        assert code == 1 and result["error_code"] == "test_dispatch_spy", (
            spec.key,
            result,
        )
        assert captured[-1][0] == spec.key
        assert normalize_house_system(captured[-1][1]) == expected
    assert len(captured) == len(HOUSE_SPECS)


def test_documented_gauquelin_direct_flags_return_shared_validation_error(
    monkeypatch, capsys
):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid direct flags reached calculation")

    monkeypatch.setattr(cli, "execute_tool", forbidden)
    code = cli.run(
        [
            "astro_horary",
            "--question-year",
            "2000",
            "--question-month",
            "1",
            "--question-day",
            "1",
            "--question-hour",
            "12",
            "--timezone-name",
            "UTC",
            "--longitude",
            "0",
            "--latitude",
            "0",
            "--house-system",
            "G",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert code == 1 and body["error_code"] == "validation_error"
    assert body["issues"][0] == {
        "path": "house_system",
        "code": "unsupported_house_system",
    }

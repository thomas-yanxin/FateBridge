"""Reject invalid trigram facts before they can become a different chart."""

import asyncio

import pytest

from fatebridge.core.local_techniques.tongshefa import build_tongshefa_result
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize("field", ["taiyin", "taiyang", "shaoyang", "shaoyin"])
@pytest.mark.parametrize("invalid", ["乾卦", ""])
def test_invalid_trigram_is_not_replaced_by_a_default(field, invalid):
    with pytest.raises(ValueError, match=field):
        build_tongshefa_result(**{field: invalid})


@pytest.mark.parametrize("field", ["taiyin", "taiyang", "shaoyang", "shaoyin"])
def test_invalid_trigram_fails_on_all_transports(field, rest, tmp_path, capsys):
    spec = SPECS["tongshefa"]
    payload = {field: "乾卦"}
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["error_code"] == "validation_error"
        assert field in output["error"]
        assert "tongshefa" not in output


def test_omitted_and_null_trigrams_keep_the_declared_default_chart():
    result = build_tongshefa_result(
        taiyin=None, taiyang=None, shaoyang=None, shaoyin=None
    )
    assert result["input_normalized"] == {
        "taiyin": "巽",
        "taiyang": "坤",
        "shaoyang": "震",
        "shaoyin": "震",
    }
    assert result["tongshefa"]["baseLeft"]["name"] == "风雷益"
    assert result["tongshefa"]["baseRight"]["name"] == "地雷复"

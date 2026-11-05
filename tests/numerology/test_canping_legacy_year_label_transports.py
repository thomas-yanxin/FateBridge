"""The corrected legacy year labels and numbers agree on actual local surfaces."""

import pytest

from tests.evaluation.test_agentic_nested_outputs import SPECS, business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_canping_legacy_year_labels import REFERENCE, request
from tests.numerology.test_heluo_poem_transports import run_three

rest = shared_rest


@pytest.fixture(autouse=True)
def native_source(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("index", [0, 1, 2])
def test_legacy_year_labels_match_rest_mcp_cli(index, rest, tmp_path, capsys):
    case = REFERENCE["cases"][index]
    fields = ["input_normalized", "four_pillars", "liunian_series", "canping_timing"]
    response, code, cli, mcp = run_three(
        SPECS["canping"], request(case), fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for value in outputs:
        SPECS["canping"].output_model.model_validate(value)
        series = value["liunian_series"]
        first = series["rows"][0]
        assert series["birth_pillar_year"] == first["year"] == case["year"]
        assert first["ganzhi"] == case["year_pillar"]
        assert series["year_boundary"] == "lichun_year_labels_only"
        assert value["canping_timing"]["first_period"] is None
        assert (
            value["canping_timing"]["schedule_basis"]["has_actual_date_mapping"]
            is False
        )
        if index == 0:
            assert (first["numShun"], first["numNi"]) == (2444, 3044)

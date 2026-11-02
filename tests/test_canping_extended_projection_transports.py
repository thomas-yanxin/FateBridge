"""Real local adapters preserve the added bounded event sources."""

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core import de440_solar
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest


@pytest.fixture(autouse=True)
def controlled_source(monkeypatch, tmp_path):
    original_cache = de440_solar._profile
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    original_cache.cache_clear()
    yield
    original_cache.cache_clear()


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize("date", ["1700-01-03", "2300-05-15"])
@pytest.mark.parametrize("projected", [False, True])
def test_complete_or_projected_actual_sources_survive_three_adapters(
    mode, date, projected, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    payload = dict(
        date=date, time="09:00", zone="UTC", gender="男", use_true_solar_time=False
    )
    fields = ["canping_timing.solar_year_context"]
    if not projected:
        fields += [
            "liunian_series.year_boundaries",
            "canping_timing.first_row",
            "canping_timing.first_period",
            "numerology_evidence.rulesets",
        ]
    spec = SPECS["canping"]
    response, code, cli, mcp = run_three(spec, payload, fields, rest, tmp_path, capsys)
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        timing = out["canping_timing"]
        ctx = timing["solar_year_context"]
        assert ctx["policy_id"] == "canping_lichun_extended_projection_context_v1"
        assert ctx["boundary_count"] == 121 and ctx["horizon_years"] == 120
        assert "moshier" not in ctx["observed_models"]
        assert ctx["registered_public_input_years"] == [1700, 2300]
        assert ctx["public_model_years_extended"] is False
        if not projected:
            assert timing["first_row"] == timing["first_period"]
            rows = out["liunian_series"]["year_boundaries"]
            assert len(rows) == 121
            assert {r["record"]["ephemeris_model"] for r in rows} == set(
                ctx["observed_models"]
            )
            assert any(
                r["ruleset_id"] == ctx["policy_id"] and r["source_url"]
                for r in out["numerology_evidence"]["rulesets"]
            )


@pytest.mark.parametrize("unrelated", [False, True])
def test_missing_selected_future_data_fail_before_any_projection(
    unrelated, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    original = de440_solar._profile

    def load(profile=de440_solar.MODEL_ID):
        if profile == "fatebridge_de440_solar_canping_extended_v1":
            raise EphemerisSourceError("solar_de440_invalid")
        return original(profile)

    monkeypatch.setattr(de440_solar, "_profile", load)
    payload = dict(
        date="2300-05-15",
        time="09:00",
        zone="UTC",
        gender="男",
        use_true_solar_time=False,
    )
    fields = ["analysis_type"] if unrelated else ["canping_timing.solar_year_context"]
    response, code, cli, mcp = run_three(
        SPECS["canping"], payload, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for out in [response.json(), cli, mcp.structured_content]:
        assert out["error_code"] == "ephemeris_source_inconsistent"
        assert out["retryable"] is False

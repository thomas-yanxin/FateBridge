"""A transient selector read cannot put another orbit family into a cached year."""

import inspect

import pytest

from fatebridge.core import almanac, solar_model_policy


@pytest.mark.parametrize(
    "mode,expected", [("auto", "fatebridge_de440_solar_v1"), ("native", "moshier")]
)
def test_captured_year_source_is_not_reselected_by_a_transient_environment_read(
    mode, expected, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    original = solar_model_policy.solar_model_policy
    injected = False

    def transient():
        nonlocal injected
        caller = inspect.currentframe().f_back
        if (
            not injected
            and caller.f_code.co_name == "de440_selected"
            and caller.f_back.f_code.co_name == "_calculate_solar_terms_for_year"
        ):
            injected = True
            monkeypatch.setenv(
                "FATEBRIDGE_SOLAR_TERM_MODEL", "native" if mode == "auto" else "auto"
            )
            selected = original()
            monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
            return selected
        return original()

    almanac.get_solar_terms_for_year.cache_clear()
    monkeypatch.setattr(solar_model_policy, "solar_model_policy", transient)
    for _ in range(2):
        terms = almanac.get_solar_terms_for_year(2026, "UTC")
        assert len(terms) == 24
        assert {term.ephemeris_model for term in terms} == {expected}
        assert all(almanac.is_calculated_solar_term(term) for term in terms)

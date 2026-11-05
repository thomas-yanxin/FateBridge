"""Taiyi endpoint inputs retain their declared local year and solar source."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core.metaphysics import qimen
from fatebridge.utils.errors import EphemerisSourceError
from scripts.taiyi.audit_taiyi_solar_guard import (
    calculate,
    inputs,
    inspect_board,
    policy,
    reference,
)
from tests.evaluation.test_agentic_nested_outputs import (  # noqa: F401 - imported pytest fixture
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

PROTOCOL, REFERENCES = reference()


@pytest.fixture(autouse=True)
def controlled_sources(monkeypatch):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)


def test_qimen_derived_cache_revalidates_active_solar_source(monkeypatch):
    with policy("de440"):
        assert qimen._qimen_build_yinyangdun_map(2000, "UTC")

        def failed_source(*args, **kwargs):
            raise EphemerisSourceError("solar_de440_invalid")

        monkeypatch.setattr(qimen, "get_jieqi_year_grid", failed_source)
        with pytest.raises(EphemerisSourceError):
            qimen._qimen_build_yinyangdun_map(2000, "UTC")


def test_qimen_derived_cache_does_not_hide_an_invalid_new_policy(monkeypatch):
    with policy("de440"):
        assert qimen._qimen_build_yinyangdun_map(2000, "UTC")
        with monkeypatch.context() as changed:
            changed.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "invalid")
            with pytest.raises(ValueError, match="FATEBRIDGE_SOLAR_TERM_MODEL"):
                qimen._qimen_build_yinyangdun_map(2000, "UTC")


@pytest.mark.parametrize("case", PROTOCOL["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("profile", PROTOCOL["profiles"])
@pytest.mark.parametrize("mode", PROTOCOL["policies"])
@pytest.mark.parametrize("tool", PROTOCOL["tools"])
def test_all_endpoint_profiles_use_frozen_source_roots(case, profile, mode, tool):
    with policy(mode):
        for solar in PROTOCOL["solar_flags"]:
            result = calculate(tool, inputs(tool, case, profile, solar))
            board = result["taiyi"]
            checked = inspect_board(board, case, profile, REFERENCES)
            assert checked["passed"], checked
            assert "jpl_de440/fatebridge_de440_solar_v1" in result["snapshot_text"]
            if tool == "sanshiunited":
                assert (
                    result["subresults"]["taiyi"]["pan"]["solar_anchors"]
                    == board["solar_anchors"]
                )
                receipt = result["qimen"]["calendar_policy"]
                assert receipt["solar_term_providers"] == ["jpl_de440"]
                expected_years = [case["year"] - 1, case["year"]]
                # Fixed23:30Dec31cases, longitude150: civil late-Zi crosses
                # NewYear; the+14apparent clock remains around19:30Dec31.
                if case["month"] == 12 and (not solar or case["zone"] != "+14:00"):
                    expected_years.append(case["year"] + 1)
                assert receipt["term_grid_years_observed"] == expected_years


@pytest.mark.parametrize(
    "case",
    [
        {**case, "year": 1699 if case["year"] == 1799 else 2301}
        for case in PROTOCOL["strict_outside_cases"]
    ],
)
@pytest.mark.parametrize("profile", PROTOCOL["profiles"])
@pytest.mark.parametrize("tool", PROTOCOL["tools"])
def test_crossing_utc_into_range_does_not_authorize_an_outside_local_year(
    case, profile, tool
):
    with policy("de440"):
        result = calculate(tool, inputs(tool, case, profile, False))
    assert "taiyi" not in result
    assert result["status_code"] == 400
    assert "1700..2300" in result["error"]
    assert result["retryable"] is False


@pytest.mark.parametrize("year", [1699, 2301])
def test_guard_cache_does_not_expand_standalone_year_api(year):
    with policy("de440"):
        almanac._solar_terms_for_context_year(
            year, "UTC", 1700 if year == 1699 else 2300
        )
        with pytest.raises(ValueError, match="1700..2300"):
            almanac.get_solar_terms_for_year(year, "UTC")


@pytest.mark.parametrize("year", [1800, 2200])
@pytest.mark.parametrize("profile", PROTOCOL["profiles"])
@pytest.mark.parametrize("tool", PROTOCOL["tools"])
def test_endpoint_profiles_match_on_rest_mcp_cli(
    year, profile, tool, rest, tmp_path, capsys  # noqa: F811 - imported pytest fixture
):
    spec = SPECS[tool]
    case = next(
        c
        for c in PROTOCOL["cases"]
        if c["year"] == year and c["month"] == 1 and c["zone"] == "+14:00"
    )
    values = inputs(tool, case, profile, False)
    fields = ["taiyi.solar_anchors", "taiyi.calendar_summary", "taiyi.calendar_rules"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    with policy("de440"):
        http = rest.post(
            spec.rest_path,
            json=values,
            params=[("fields", f) for f in fields]
            + [
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
                ("response_char_limit", "0"),
                ("as_of", AS_OF),
            ],
        )
        mcp = asyncio.run(native(spec, values, **opts))
        code, cli = call_cli(
            spec,
            values,
            tmp_path,
            capsys,
            [
                "--fields",
                *fields,
                "--strict-fields",
                "true",
                "--include-snapshot-text",
                "false",
                "--response-char-limit",
                "0",
            ],
        )
    assert http.status_code == 200, http.text
    assert not mcp.is_error, mcp.structured_content
    assert code == 0, cli
    results = [http.json(), mcp.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        assert inspect_board(value["taiyi"], case, profile, REFERENCES)["passed"]


def test_reference_corpus_is_reused_and_not_candidate_generated():
    protocol, refs = reference()
    assert len(refs) == 144
    assert protocol["reference_imports_production"] is False
    assert protocol["new_independent_observations"] == 0
    assert protocol["business_control_rows"] == 720
    assert (
        json.loads(
            (
                Path(__file__).parents[1] / "fixtures/taiyi_solar_guard_v44/freeze.json"
            ).read_text()
        )["production_edited"]
        is False
    )

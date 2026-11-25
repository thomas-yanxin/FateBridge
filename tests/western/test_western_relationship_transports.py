"""Davison variants and both Marks charts agree over actual public transports."""

import asyncio
from datetime import datetime, timezone

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views, suggested_fields
from fatebridge.core.astro.time_scales import ephemeris_time
from tests.support.relationship_inputs import payloads
from tests.support.transports import AS_OF, SPECS, business, call_cli, native, rest
from tests.western.test_western_relationship_scoring import replay


@pytest.mark.parametrize("mode", ["TimeSpace", "Marks"])
def test_relationship_dst_elapsed_hour_keeps_ut1_mean_and_quarters(
    mode, rest, tmp_path, capsys
):
    """Two hours on the spring clock are one elapsed hour for both derived methods."""
    nested, flat = payloads(mode, "uncorrected")
    for role, hour, zone in [("inner", 1, "-05:00"), ("outer", 3, "-04:00")]:
        updates = dict(
            birth_year=2024,
            birth_month=3,
            birth_day=10,
            birth_hour=hour,
            birth_minute=30,
            birth_timezone=zone,
        )
        nested[role] = {**nested[role], **updates}
        flat.update({f"{role}_{name}": value for name, value in updates.items()})
    fields = (
        [
            "chart.chart_profile.julian_day_ut1",
            "chart.chart_profile.derivation_policy",
            "marks_charts",
        ]
        if mode == "Marks"
        else [
            "chart.chart_profile.julian_day_ut1",
            "chart.chart_profile.derivation_policy",
        ]
    )
    response = rest.post(
        "/api/astro/relative",
        json=nested,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in fields],
        ],
    )
    code, local = call_cli(
        SPECS["astro_relative_chart"],
        flat,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            SPECS["astro_relative_chart"],
            flat,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    first, second = [
        ephemeris_time(datetime(2024, 3, 10, hour, 30, tzinfo=timezone.utc)).jd_ut1
        for hour in (6, 7)
    ]
    result = response.json()
    if mode == "TimeSpace":
        assert result["chart"]["chart_profile"]["julian_day_ut1"] == pytest.approx(
            (first + second) / 2, abs=1e-9, rel=0
        )
    else:
        for role, expected in [
            ("inner", (3 * first + second) / 4),
            ("outer", (first + 3 * second) / 4),
        ]:
            assert result["marks_charts"][role]["chart_profile"][
                "julian_day_ut1"
            ] == pytest.approx(expected, abs=1e-9, rel=0)


@pytest.mark.parametrize("mode", ["TimeSpace", "Marks"])
@pytest.mark.parametrize("month,day,hour", [(3, 10, 2), (11, 3, 1)])
def test_relationship_rejects_unqualified_dst_clock_before_derivation(
    mode, month, day, hour, rest, tmp_path, capsys
):
    """A missing fold choice or nonexistent clock must not become a derived chart."""
    nested, flat = payloads(mode, "uncorrected")
    updates = dict(
        birth_year=2024,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=30,
        birth_timezone="America/New_York",
    )
    nested["outer"] = {**nested["outer"], **updates}
    flat.update({f"outer_{name}": value for name, value in updates.items()})
    response = rest.post("/api/astro/relative", json=nested, params={"as_of": AS_OF})
    code, local = call_cli(SPECS["astro_relative_chart"], flat, tmp_path, capsys)
    protocol = asyncio.run(native(SPECS["astro_relative_chart"], flat))
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for result in (response.json(), local, protocol.structured_content):
        assert result["error_code"] == "validation_error"
        assert "chart" not in result and "marks_charts" not in result


@pytest.mark.parametrize("mode", ["TimeSpace", "Marks"])
@pytest.mark.parametrize("variant", ["uncorrected", "corrected", "spherical"])
def test_relationship_variants_and_full_precision_match_all_transports(
    mode, variant, rest, tmp_path, capsys
):
    nested, flat = payloads(mode, variant)
    spec = SPECS["astro_relative_chart"]
    response = rest.post(
        "/api/astro/relative", json=nested, params={"response_char_limit": 0}
    )
    code, cli = call_cli(
        spec, flat, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, flat))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in (response.json(), cli, mcp.structured_content):
        spec.output_model.model_validate(business(result))
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        replay(
            result["compatibility"],
            result["compatibility_evidence"],
            result["synastry_aspects"],
        )
        assert result["compatibility_evidence"]["source_paths"] == [
            "inner_chart.planets",
            "outer_chart.planets",
            "synastry_aspects",
        ]
        assert (
            result["relationship_profile"]["compatibility_policy"]["original_text_rule"]
            is False
        )
        assert any("自定义关系规则综合分" in line for line in result["summary"])
        assert "[自定义评分依据]" in result["snapshot_text"]
        assert "unclamped_score：" in result["snapshot_export"]["export_text"]
        assert result["relationship_profile"]["davison_variant"] == variant
        assert (
            result["chart"]["chart_profile"]["sidereal_position_method"]
            == "swisseph_calc_sidereal_lahiri"
        )
        if mode == "Marks":
            assert set(result["marks_charts"]) == {"inner", "outer"}
            assert result["chart"] == result["marks_charts"]["inner"]


def test_marks_person_specific_source_and_times_support_strict_projection(
    rest, tmp_path, capsys
):
    nested, flat = payloads("Marks", "corrected")
    fields = [
        "relationship_profile.primary_chart_role",
        "marks_charts.outer.chart_profile.julian_day_tt",
        "marks_charts.outer.chart_profile.derivation_policy.recipe",
        "marks_charts.inner.person_info.name",
    ]
    response = rest.post(
        "/api/astro/relative",
        json=nested,
        params=[("fields", path) for path in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, cli = call_cli(
        SPECS["astro_relative_chart"],
        flat,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    mcp = asyncio.run(
        native(
            SPECS["astro_relative_chart"],
            flat,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    for result in (response.json(), cli, mcp.structured_content):
        assert result["relationship_profile"]["primary_chart_role"] == "inner"
        assert isinstance(
            result["marks_charts"]["outer"]["chart_profile"]["julian_day_tt"], float
        )
        assert (
            "natal data"
            in result["marks_charts"]["outer"]["chart_profile"]["derivation_policy"][
                "recipe"
            ]
        )
        assert result["marks_charts"]["inner"]["person_info"]["name"].startswith("甲")
        assert not result.get("projection_warnings")


@pytest.mark.parametrize("variant", ["uncorrected", "corrected", "spherical"])
def test_published_marks_view_delivers_both_people_on_all_transports(
    variant, rest, tmp_path, capsys
):
    nested, flat = payloads("Marks", variant)
    spec = SPECS["astro_relative_chart"]
    card = evidence_views(spec)["marks"]
    fields = card["fields"]
    response = rest.post(
        "/api/astro/relative",
        json=nested,
        params=[("fields", path) for path in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    code, cli = call_cli(
        spec,
        flat,
        tmp_path,
        capsys,
        flags=[
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
    mcp = asyncio.run(
        native(
            spec, flat, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    values = [response.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        assert (
            value["relationship_profile"]["primary_layer"]
            == card["primary_layer"]
            == "marks_chart_pair"
        )
        assert value["relationship_profile"]["davison_variant"] == variant
        assert "chart" not in value and set(value["marks_charts"]) == {"inner", "outer"}
        pair = value["marks_charts"]
        assert pair["inner"]["planets"] != pair["outer"]["planets"]
        for role in ["inner", "outer"]:
            assert (
                pair[role]["chart_profile"]["derivation_policy"]["method_id"]
                == "marks_natal_davison_v1"
            )
            assert len(pair[role]["planets"]) >= 10 and len(pair[role]["houses"]) == 12
            assert pair[role]["angles"] and pair[role]["aspects"]
        spec.output_model.model_validate(value)


@pytest.mark.parametrize(
    "mode", ["Comp", "Composite", "Synastry", "TimeSpace", "Marks"]
)
def test_safe_union_includes_only_the_selected_marks_pair(mode, rest):
    nested, _ = payloads(mode, "uncorrected")
    response = rest.post(
        "/api/astro/relative",
        json=nested,
        params=[
            ("fields", path) for path in suggested_fields(SPECS["astro_relative_chart"])
        ]
        + [("strict_fields", "true"), ("response_char_limit", 0)],
    )
    assert response.status_code == 200, response.text
    pair = response.json()["marks_charts"]
    assert set(pair) == ({"inner", "outer"} if mode == "Marks" else set())


def test_invalid_davison_selector_is_rejected_on_all_transports(rest, tmp_path, capsys):
    nested, flat = payloads("TimeSpace", "unrecognised")
    response = rest.post("/api/astro/relative", json=nested)
    code, cli = call_cli(SPECS["astro_relative_chart"], flat, tmp_path, capsys)
    mcp = asyncio.run(native(SPECS["astro_relative_chart"], flat))
    assert response.status_code == 422 and code != 0 and mcp.is_error


def test_real_natal_inputs_keep_scores_when_participants_are_exchanged(rest):
    nested, _ = payloads("Synastry", "uncorrected")
    reverse = {**nested, "inner": nested["outer"], "outer": nested["inner"]}
    results = [
        rest.post("/api/astro/relative", json=inputs, params={"response_char_limit": 0})
        for inputs in (nested, reverse)
    ]
    assert all(result.status_code == 200 for result in results)
    left, right = [result.json() for result in results]
    assert left["compatibility"] == right["compatibility"]
    for result in (left, right):
        replay(
            result["compatibility"],
            result["compatibility_evidence"],
            result["synastry_aspects"],
        )


def test_scoring_arithmetic_supports_strict_projection_on_all_transports(
    rest, tmp_path, capsys
):
    nested, flat = payloads("Synastry", "uncorrected")
    fields = [
        "compatibility.overall_score",
        "compatibility_evidence.aspect_selection.selected_contacts",
        "compatibility_evidence.overall.numerator",
        "relationship_profile.compatibility_policy.rounding",
    ]
    flags = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    response = rest.post(
        "/api/astro/relative",
        json=nested,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, cli = call_cli(
        SPECS["astro_relative_chart"],
        flat,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    mcp = asyncio.run(native(SPECS["astro_relative_chart"], flat, **flags))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in (response.json(), cli, mcp.structured_content):
        assert not result.get("projection_warnings")
        assert result["compatibility"]["overall_score"] == round(
            result["compatibility_evidence"]["overall"]["numerator"] / 3
        )
        selected = result["compatibility_evidence"]["aspect_selection"][
            "selected_contacts"
        ]
        assert selected and {
            "delta",
            "synastry_aspect_index",
            "inner",
            "outer",
            "aspect",
            "orb",
        } == set(selected[0])

"""Davison variants and both Marks charts agree over actual public transports."""

import asyncio
import math

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views, suggested_fields
from fatebridge.core.astro.relationship_charts import _build_influence_chart_wrapper
from tests.support.relationship_inputs import payloads
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
    surface_calls,
)
from tests.western.test_western_relationship_scoring import replay


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


@pytest.mark.parametrize("mode", ["Composite", "Synastry"])
@pytest.mark.parametrize(
    "longitude_offset,hsys,reverse",
    [
        (None, 0, False),
        (None, 8, False),
        (0.0, 0, False),
        (0.0, 0, True),
        (0.0, 8, False),
        (0.0, 8, True),
        (-1e-7, 0, False),
        (1e-7, 0, False),
    ],
)
def test_derived_house_qualification_on_all_transports(
    mode, hsys, longitude_offset, reverse, surface_calls, rest
):
    # Synthetic J2000 geometry: ARMC=90 and phi=epsilon-90 make the
    # ecliptic coincide with the horizon. Either side remains resolvable.
    normal = dict(
        name="normal",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=30.0,
        use_true_solar_time=False,
    )
    candidate = {
        **normal,
        "name": "candidate",
        **(
            {
                "birth_longitude": 169.54144401512139 + longitude_offset,
                "birth_latitude": -66.5623231709126,
            }
            if longitude_offset is not None
            else {}
        ),
    }
    inner, outer = (normal, candidate) if reverse else (candidate, normal)
    nested = dict(inner=inner, outer=outer, relative_mode=mode, hsys=hsys, zodiacal=0)
    flat = {
        **{f"inner_{k}": v for k, v in inner.items()},
        **{f"outer_{k}": v for k, v in outer.items()},
        "relative_mode": mode,
        "hsys": hsys,
        "zodiacal": 0,
    }
    spec = SPECS["astro_relative_chart"]
    fields = [
        "inner.chart.angles",
        "inner.chart.houses",
        "inner.chart.planets",
        "outer.chart.angles",
        "outer.chart.houses",
        "outer.chart.planets",
    ]
    if mode == "Composite":
        fields += [
            "chart.angles.ascendant.longitude",
            "chart.angles.midheaven.longitude",
            "chart.houses",
            "chart.planets",
            "chart.aspects",
        ]
    # Read full source evidence once, then replay its exact derived facts
    # through strict point projection on all three production transports.
    controls = dict(
        strict_fields=True, include_snapshot_text=False, response_char_limit=0
    )
    response = rest.post(
        "/api/astro/relative", json=nested, params={**controls, "as_of": AS_OF}
    )
    assert response.status_code == 200, response.text
    full = response.json()
    http, protocol, code, cli = surface_calls(
        spec,
        flat,
        rest_payload=nested,
        projection={**controls, "fields": fields},
        rest_as_of=AS_OF,
    )
    assert http.status_code == 200, http.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    values = [http.json(), protocol.structured_content, cli]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in [full, *values]:
        spec.output_model.model_validate(business(value))
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        assert not value.get("projection_warnings")
    projected = values[0]
    unresolved = longitude_offset == 0.0
    role = "outer" if reverse else "inner"
    source = full[f"{role}_chart"]
    definition = source["chart_profile"].get("angle_definition", {})
    assert (definition.get("geometric_ascendant_resolved") is False) == unresolved
    if longitude_offset not in (None, 0.0):
        assert definition["geometric_ascendant_resolved"] is True

    # Independent spherical geometry control, using the frozen J2000 angle
    # model epsilon and local sidereal angle, rather than derived-chart code.
    eps = math.radians(23.4376768290874)
    for chart_role, person in (("inner", inner), ("outer", outer)):
        theta = math.radians((280.4585559848786 + person["birth_longitude"]) % 360)
        expected_mc = (
            math.degrees(math.atan2(math.sin(theta), math.cos(theta) * math.cos(eps)))
            % 360
        )
        natal = full[f"{chart_role}_chart"]
        assert natal["angles"]["midheaven"]["longitude"] == pytest.approx(
            expected_mc, abs=1e-6
        )
        if person["name"] == "normal" or longitude_offset is None:
            expected_asc = (
                math.degrees(
                    math.atan2(
                        -math.cos(theta),
                        math.sin(theta) * math.cos(eps)
                        + math.tan(math.radians(person["birth_latitude"]))
                        * math.sin(eps),
                    )
                )
                + 180
            ) % 360
            assert natal["angles"]["ascendant"]["longitude"] == pytest.approx(
                expected_asc, abs=1e-6
            )

    charts = [
        (key, full[key]["chart"], projected[key]["chart"]) for key in ("inner", "outer")
    ]
    if mode == "Composite":
        charts.append(("composite", full["chart"], projected["chart"]))
        left = full["inner_chart"]["angles"]["midheaven"]["longitude"]
        right = full["outer_chart"]["angles"]["midheaven"]["longitude"]
        expected_mid_mc = (left + ((right - left + 180) % 360 - 180) / 2) % 360
        assert full["chart"]["angles"]["midheaven"]["longitude"] == pytest.approx(
            expected_mid_mc, abs=1e-12
        )
        if definition:
            derived_definition = full["chart"]["chart_profile"]["angle_definition"]
            assert derived_definition["source_angle_definitions"][role] == definition
            assert derived_definition["geometric_ascendant_resolved"] is not unresolved
        if not unresolved:
            left = full["inner_chart"]["angles"]["ascendant"]["longitude"]
            right = full["outer_chart"]["angles"]["ascendant"]["longitude"]
            assert full["chart"]["angles"]["ascendant"]["longitude"] == pytest.approx(
                (left + ((right - left + 180) % 360 - 180) / 2) % 360, abs=1e-12
            )
        assert full["chart"]["aspects"]
    assert full["synastry_aspects"]
    if mode == "Synastry" and unresolved and hsys == 0 and not reverse:
        # A caller's generic selector cannot override this target's partition.
        target = _build_influence_chart_wrapper(
            role="inner",
            house_chart=full["inner_chart"],
            source_chart=full["outer_chart"],
            house_system="equal_mc",
            zodiacal_info={"value": 0, "label_zh": "回归黄道", "zodiac": "tropical"},
        )
        assert target["chart_profile"]["house_system"] == "whole_sign"
        assert target["chart"]["houses"] == []
    for chart_role, chart, projection in charts:
        limited = unresolved and chart_role in (role, "composite")
        assert (chart["angles"]["ascendant"]["longitude"] is None) == limited
        assert chart["angles"]["midheaven"]["longitude"] is not None
        assert len(chart["planets"]) >= 10
        assert (
            chart["angles"]["ascendant"]["longitude"]
            == projection["angles"]["ascendant"]["longitude"]
        )
        assert (
            chart["angles"]["midheaven"]["longitude"]
            == projection["angles"]["midheaven"]["longitude"]
        )
        assert chart["houses"] == projection["houses"]
        assert chart["planets"] == projection["planets"]
        if limited and hsys == 0:
            assert chart["houses"] == []
            assert all(p["house"] is None for p in chart["planets"])
        else:
            assert len(chart["houses"]) == 12
            assert all(1 <= p["house"] <= 12 for p in chart["planets"])
            if hsys == 8:
                assert chart["houses"][9]["cusp_longitude"] == pytest.approx(
                    chart["angles"]["midheaven"]["longitude"], abs=1e-12
                )
                anchor = chart["houses"][0]["cusp_longitude"]
            else:
                anchor = math.floor(chart["angles"]["ascendant"]["longitude"] / 30) * 30
            for planet in chart["planets"]:
                assert (
                    planet["house"]
                    == int((planet["longitude"] - anchor) % 360 // 30) + 1
                )

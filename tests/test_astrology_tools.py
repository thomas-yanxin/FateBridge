import asyncio

import pytest
from pydantic import ValidationError

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.ephemeris import (
    _swisseph_angles,
)
from fatebridge.core.astro.geometry import (
    _angles,
    _julian_day,
    _sign_name,
)
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.requests.astrology import (
    AstroChartRequest,
    AstroRelativePartyRequest,
    AstroRelativeRequest,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
    calculate_relative_chart_analysis,
)
from tests.fixtures.surface_payloads import astro_payload
from tests.fixtures.transports import mcp_parameters, rest_handler

calculate_relative_chart_endpoint = rest_handler("astro_relative")


def test_astro_request_models_accept_geo_fields():
    request = AstroChartRequest(**astro_payload(), hsys=0, zodiacal=1)
    place_only_request = AstroChartRequest(
        name="测试者",
        birth_year=1993,
        birth_month=12,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone=None,
        birth_place="北京",
    )
    default_relative_request = AstroRelativeRequest(
        inner=AstroRelativePartyRequest(**astro_payload()),
        outer=AstroRelativePartyRequest(
            **{
                **astro_payload(),
                "name": "对盘者",
                "birth_year": 1992,
                "birth_month": 3,
                "birth_day": 2,
                "birth_hour": 8,
                "birth_minute": 18,
            }
        ),
    )
    modern_relative_request = AstroRelativeRequest(
        inner=AstroRelativePartyRequest(**astro_payload()),
        outer=AstroRelativePartyRequest(
            **{
                **astro_payload(),
                "name": "对盘者",
                "birth_year": 1992,
                "birth_month": 3,
                "birth_day": 2,
                "birth_hour": 8,
                "birth_minute": 18,
            }
        ),
        relative_mode="Composite",
        hsys=1,
        zodiacal=1,
    )

    chart_payload = request.model_dump()
    place_only_payload = place_only_request.model_dump()
    default_relation_payload = default_relative_request.model_dump()
    modern_relation_payload = modern_relative_request.model_dump()

    assert chart_payload["birth_longitude"] == 121.4667
    assert chart_payload["birth_latitude"] == 31.2167
    assert chart_payload["hsys"] == 0
    assert chart_payload["zodiacal"] == 1
    assert place_only_payload["birth_longitude"] is None
    assert place_only_payload["birth_latitude"] is None
    assert default_relation_payload["relative_mode"] is None
    assert "relationship_mode" not in default_relation_payload
    assert modern_relation_payload["relative_mode"] == "Composite"
    assert modern_relation_payload["hsys"] == 1
    assert modern_relation_payload["zodiacal"] == 1


def test_core_chart_variants_expose_variant_specific_fields():
    chart = calculate_core_chart_analysis(chart_variant="chart", **astro_payload())
    chart13 = calculate_core_chart_analysis(
        chart_variant="chart13",
        **astro_payload(),
    )
    hellen = calculate_core_chart_analysis(
        chart_variant="hellen_chart",
        **astro_payload(),
    )
    guolao = calculate_core_chart_analysis(
        chart_variant="guolao_chart",
        **astro_payload(),
    )
    india = calculate_core_chart_analysis(
        chart_variant="india_chart",
        **astro_payload(),
    )

    assert chart["chart_profile"]["chart_type"] == "chart"
    assert len(chart["houses"]) == 12
    assert len(chart["planets"]) >= 10
    assert any(item["id"] == "Sun" for item in chart["planets"])
    assert any(item["id"] == "Moon" for item in chart["planets"])
    assert isinstance(chart["angles"]["ascendant"]["longitude"], float)

    assert chart13["chart_profile"]["chart_type"] == "chart13"
    assert len(chart13["thirteen_sectors"]) == 13
    assert "sector13" in next(
        item for item in chart13["planets"] if item["id"] == "Sun"
    )

    assert hellen["chart_profile"]["chart_type"] == "hellen_chart"
    assert hellen["chart_profile"]["house_system"] == "whole_sign"
    assert hellen["hellenistic"]["sect"] in {"day", "night"}
    assert "lot_of_fortune" in hellen["hellenistic"]

    assert guolao["chart_profile"]["chart_type"] == "guolao_chart"
    assert guolao["guolao"]["lunar_mansion_system"] == "su28"
    assert len(guolao["guolao"]["planetary_mansions"]) >= 7

    assert india["chart_profile"]["chart_type"] == "india_chart"
    assert india["chart_profile"]["zodiac"] == "sidereal"
    assert india["india"]["ayanamsha"] > 0
    assert "nakshatra" in next(
        item for item in india["planets"] if item["id"] == "Moon"
    )


def test_core_chart_includes_snapshot_text_and_export():
    chart = calculate_core_chart_analysis(chart_variant="chart", **astro_payload())

    assert "[起盘信息]" in chart["snapshot_text"]
    assert "[宫位宫头]" in chart["snapshot_text"]
    assert "[星与虚点]" in chart["snapshot_text"]
    assert "[相位]" in chart["snapshot_text"]
    assert "[行星]" in chart["snapshot_text"]
    assert "太阳：" in chart["snapshot_text"]
    assert "Asc：" in chart["snapshot_text"]
    assert "人格签名：" in chart["snapshot_text"]
    assert "核心人格：" in chart["snapshot_text"]
    assert "成长建议：" in chart["snapshot_text"]
    assert chart["snapshot_export"]["technique"]["key"] == "astrochart"
    assert "[起盘信息]" in chart["snapshot_export"]["export_text"]
    assert "[行星]" in chart["snapshot_export"]["export_text"]
    assert chart["interpretation"]["signature"].startswith("太阳")
    assert "核心驱动力" in chart["interpretation"]["core_identity"]
    assert "安全感" in chart["interpretation"]["emotional_style"]
    assert len(chart["summary"]) >= 7
    assert chart["summary"][1].startswith("核心签名：")


def test_core_chart_can_infer_coordinates_from_birth_place():
    chart = calculate_core_chart_analysis(
        chart_variant="chart",
        name="测试者",
        birth_year=1993,
        birth_month=12,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone=None,
        birth_longitude=None,
        birth_latitude=None,
        birth_place="北京",
    )

    assert chart["person_info"]["birth_place"] == "北京"
    assert chart["person_info"]["birth_timezone"] == "Asia/Shanghai"
    assert chart["person_info"]["birth_longitude"] == 116.4074
    assert chart["person_info"]["birth_latitude"] == 39.9042
    if swe is not None:
        birth_info = build_astro_birth_info(
            name="测试者",
            birth_year=1993,
            birth_month=12,
            birth_day=15,
            birth_hour=10,
            birth_minute=30,
            birth_timezone="Asia/Shanghai",
            birth_longitude=116.4074,
            birth_latitude=39.9042,
            birth_place="北京",
        )
        angle_state = _swisseph_angles(
            _julian_day(birth_info.utc_datetime),
            birth_info.longitude,
            birth_info.latitude,
        )
        assert angle_state is not None
        expected_asc_sign = _sign_name(angle_state["ascendant"])
    else:
        expected_asc_sign = "Leo"
    assert chart["angles"]["ascendant"]["sign"] == expected_asc_sign
    assert "[起盘信息]" in chart["snapshot_text"]


def test_core_chart_infers_coordinates_for_prefecture_city():
    # "南通" had longitude in the offline catalog but no latitude, so the core
    # chart used to reject a BaZi-resolvable place. Latitude now travels with it.
    chart = calculate_core_chart_analysis(
        chart_variant="chart",
        name="测试者",
        birth_year=1993,
        birth_month=12,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone=None,
        birth_longitude=None,
        birth_latitude=None,
        birth_place="南通",
    )
    assert chart["person_info"]["birth_longitude"] == pytest.approx(120.8943, abs=0.01)
    assert chart["person_info"]["birth_latitude"] is not None


def test_core_chart_accepts_but_ignores_gender():
    # astro endpoints accept gender for uniform batch calling across tools, but
    # gender never participates in the chart calculation.
    payload = dict(
        chart_variant="chart",
        name="测试者",
        birth_year=1993,
        birth_month=12,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4074,
        birth_latitude=39.9042,
        birth_place="北京",
    )
    male = calculate_core_chart_analysis(gender="男", **payload)
    female = calculate_core_chart_analysis(gender="女", **payload)
    assert male["angles"] == female["angles"]
    assert male["planets"] == female["planets"]


def test_core_chart_prefers_local_ephemeris_runtime_when_available():
    swe = pytest.importorskip("swisseph")
    birth_payload = astro_payload()

    chart = calculate_core_chart_analysis(chart_variant="chart", **birth_payload)
    # The core chart defaults to the civil (zone) clock per western convention;
    # build the reference birth info the same way so the expected Swiss-Ephemeris
    # positions line up.
    birth_info = build_astro_birth_info(**birth_payload, use_true_solar_time=False)
    julian_day = _julian_day(birth_info.utc_datetime)
    expected_sun, _ = swe.calc_ut(julian_day, swe.SUN, swe.FLG_SWIEPH)
    expected_moon, _ = swe.calc_ut(julian_day, swe.MOON, swe.FLG_SWIEPH)

    sun = next(item for item in chart["planets"] if item["id"] == "Sun")
    moon = next(item for item in chart["planets"] if item["id"] == "Moon")

    assert chart["chart_profile"]["engine_precision"] == "ephemeris_runtime_model"
    assert chart["chart_profile"]["engine_backend"] == "swisseph_api"
    # The runtime honestly reports which ephemeris model actually served the
    # positions. "swieph"/"jpl" when data files are installed; "moshier" when
    # swisseph silently downgraded to its built-in model because no .se1 files
    # are present; "mixed" when (as with no data files) the analytical lunar node
    # resolves via swieph while the planets fall back to moshier.
    assert chart["chart_profile"]["ephemeris_model"] in {
        "swieph",
        "moshier",
        "jpl",
        "mixed",
    }
    assert sun["longitude"] == pytest.approx(expected_sun[0], abs=0.001)
    assert sun["latitude"] == pytest.approx(expected_sun[1], abs=0.001)
    assert moon["longitude"] == pytest.approx(expected_moon[0], abs=0.001)
    assert moon["latitude"] == pytest.approx(expected_moon[1], abs=0.001)


def test_core_chart_offline_options_preserve_defaults_and_allow_overrides():
    default_chart = calculate_core_chart_analysis(
        chart_variant="chart",
        **astro_payload(),
    )
    whole_sign_chart = calculate_core_chart_analysis(
        chart_variant="chart",
        hsys=0,
        **astro_payload(),
    )
    equal_mc_sidereal_chart = calculate_core_chart_analysis(
        chart_variant="chart",
        hsys=8,
        zodiacal=1,
        **astro_payload(),
    )
    india_tropical_placidus = calculate_core_chart_analysis(
        chart_variant="india_chart",
        hsys=3,
        zodiacal=0,
        **astro_payload(),
    )

    assert default_chart["chart_profile"]["house_system"] == "placidus"
    assert default_chart["chart_profile"]["house_system_code"] == 3
    assert default_chart["chart_profile"]["house_system_source"] == "variant_default"
    assert default_chart["chart_profile"]["zodiac"] == "tropical"
    assert default_chart["chart_profile"]["zodiacal"] == 0

    assert whole_sign_chart["chart_profile"]["house_system"] == "whole_sign"
    assert whole_sign_chart["chart_profile"]["house_system_code"] == 0
    assert whole_sign_chart["chart_profile"]["house_system_label_zh"] == "整宫制"
    ascendant = whole_sign_chart["angles"]["ascendant"]["longitude"]
    assert whole_sign_chart["houses"][0]["cusp_longitude"] == float(
        int(ascendant // 30) * 30
    )

    assert equal_mc_sidereal_chart["chart_profile"]["house_system"] == "equal_mc"
    assert equal_mc_sidereal_chart["chart_profile"]["house_system_code"] == 8
    assert equal_mc_sidereal_chart["chart_profile"]["zodiac"] == "sidereal"
    assert (
        equal_mc_sidereal_chart["chart_profile"]["zodiac_label_zh"]
        == "恒星黄道，岁差:Lahiri"
    )
    assert equal_mc_sidereal_chart["chart_profile"]["ayanamsha"] > 0
    default_sun = next(item for item in default_chart["planets"] if item["id"] == "Sun")
    sidereal_sun = next(
        item for item in equal_mc_sidereal_chart["planets"] if item["id"] == "Sun"
    )
    assert default_sun["longitude"] != sidereal_sun["longitude"]

    assert india_tropical_placidus["chart_profile"]["zodiac"] == "tropical"
    assert india_tropical_placidus["chart_profile"]["zodiacal"] == 0
    assert india_tropical_placidus["chart_profile"]["house_system"] == "placidus"
    assert india_tropical_placidus["chart_profile"]["house_system_code"] == 3
    assert india_tropical_placidus["india"]["ayanamsha"] == 0.0


def test_germany_chart_returns_midpoint_payload():
    result = calculate_germany_chart_analysis(**astro_payload())

    assert result["chart_profile"]["chart_type"] == "germany"
    assert result["midpoints"]
    assert result["midpoint_aspects"]
    assert result["base_chart"]["planets"]


def test_germany_chart_respects_core_house_and_zodiac_overrides():
    result = calculate_germany_chart_analysis(
        **astro_payload(),
        hsys=0,
        zodiacal=1,
    )

    assert result["chart_profile"]["house_system"] == "whole_sign"
    assert result["chart_profile"]["zodiac"] == "sidereal"
    assert result["base_chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert result["base_chart"]["chart_profile"]["zodiac"] == "sidereal"
    assert result["midpoints"]


def test_germany_chart_inherits_runtime_precision_from_base_chart():
    result = calculate_germany_chart_analysis(**astro_payload())
    expected_precision = (
        "ephemeris_runtime_model" if swe is not None else "approximate_orbital_model"
    )
    expected_backend = (
        "swisseph_api" if swe is not None else "fatebridge_approximate_orbital_model"
    )

    assert result["chart_profile"]["engine_precision"] == expected_precision
    assert result["chart_profile"]["engine_backend"] == expected_backend
    assert (
        result["base_chart"]["chart_profile"]["engine_precision"] == expected_precision
    )
    assert result["base_chart"]["chart_profile"]["engine_backend"] == expected_backend


def test_hsys_int_family_defaults_are_consistent():
    # The Western tropical-quadrant charts (natal + relative/synastry) share one
    # default house system so a person's natal chart and its synastry chart agree
    # on houses. That default is Placidus (3), the de-facto Western convention.
    # The 宿曜 suzhan/otherbu charts are a separate lunar-mansion tradition and
    # keep their own neutral equal_mc (8) default — house system is incidental
    # there, so they are intentionally NOT migrated to Placidus.
    from fatebridge.core.requests.astrology import AstroRelativeFlatRequest
    from fatebridge.core.requests.divination import OtherBuRequest, SuZhanRequest

    assert SuZhanRequest(date="2000-12-10", time="09:55:00").hsys == 8
    assert OtherBuRequest(date="2000-12-10", time="09:55:00").hsys == 8
    flat = AstroRelativeFlatRequest(
        inner_birth_year=2000,
        inner_birth_month=12,
        inner_birth_day=10,
        inner_birth_hour=9,
        inner_birth_longitude=120.0,
        inner_birth_latitude=30.0,
        outer_birth_year=1992,
        outer_birth_month=3,
        outer_birth_day=2,
        outer_birth_hour=8,
        outer_birth_longitude=120.0,
        outer_birth_latitude=30.0,
    )
    assert flat.hsys == 3


def test_relative_chart_returns_canonical_layers_and_metadata():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="Composite",
        hsys=0,
        zodiacal=1,
    )

    assert result["relationship_profile"]["chart_type"] == "relative"
    assert result["relationship_profile"]["relative_mode_input"] == "Composite"
    assert result["relationship_profile"]["relative_mode_normalized"] == "composite"
    assert result["relationship_profile"]["relative_mode_label_zh"] == "组合盘"
    assert result["relationship_profile"]["primary_layer"] == "composite_chart"
    assert result["relationship_profile"]["mode_status"] == "implemented"
    assert result["relationship_profile"]["hsys"] == 0
    assert result["relationship_profile"]["zodiacal"] == 1
    assert result["synastry_aspects"]
    assert result["in_to_out_aspects"]
    assert result["out_to_in_aspects"]
    assert result["in_to_out_midpoint"]
    assert result["out_to_in_midpoint"]
    assert isinstance(result["in_to_out_antiscia"], list)
    assert isinstance(result["out_to_in_antiscia"], list)
    assert result["in_to_out_contra_antiscia"]
    assert result["out_to_in_contra_antiscia"]
    assert "composite_chart" not in result
    assert result["inner"]["chart"]["planets"]
    assert result["outer"]["chart"]["planets"]
    assert result["inner"]["chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert result["outer"]["chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert result["inner_chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert result["outer_chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert result["chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert result["compatibility"]["element_harmony_score"] >= 0
    assert result["compatibility"]["element_harmony_score"] <= 100


def test_relative_derived_layers_inherit_runtime_precision_from_sources():
    expected_precision = (
        "ephemeris_runtime_model" if swe is not None else "approximate_orbital_model"
    )
    expected_backend = (
        "swisseph_api" if swe is not None else "fatebridge_approximate_orbital_model"
    )
    outer_payload = {
        **astro_payload(),
        "name": "对盘者",
        "birth_year": 1992,
        "birth_month": 3,
        "birth_day": 2,
        "birth_hour": 8,
        "birth_minute": 18,
    }

    composite_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload=outer_payload,
        relative_mode="Composite",
        hsys=0,
    )
    timespace_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload=outer_payload,
        relative_mode="TimeSpace",
        hsys=0,
    )
    marks_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload=outer_payload,
        relative_mode="Marks",
        hsys=0,
    )

    assert (
        composite_result["relationship_profile"]["engine_precision"]
        == expected_precision
    )
    assert (
        composite_result["relationship_profile"]["engine_backend"] == expected_backend
    )
    assert (
        composite_result["chart"]["chart_profile"]["engine_precision"]
        == expected_precision
    )
    assert (
        composite_result["chart"]["chart_profile"]["engine_backend"] == expected_backend
    )
    assert (
        composite_result["inner"]["chart"]["chart_profile"]["engine_precision"]
        == expected_precision
    )
    assert (
        composite_result["inner"]["chart"]["chart_profile"]["engine_backend"]
        == expected_backend
    )

    assert (
        timespace_result["relationship_profile"]["engine_precision"]
        == expected_precision
    )
    assert (
        timespace_result["relationship_profile"]["engine_backend"] == expected_backend
    )
    assert (
        timespace_result["chart"]["chart_profile"]["engine_precision"]
        == expected_precision
    )
    assert (
        timespace_result["chart"]["chart_profile"]["engine_backend"] == expected_backend
    )

    assert (
        marks_result["relationship_profile"]["engine_precision"] == expected_precision
    )
    assert marks_result["relationship_profile"]["engine_backend"] == expected_backend
    assert (
        marks_result["chart"]["chart_profile"]["engine_precision"] == expected_precision
    )
    assert marks_result["chart"]["chart_profile"]["engine_backend"] == expected_backend


def test_relative_chart_rejects_retired_relationship_mode():
    parties = {
        "inner": AstroRelativePartyRequest(**astro_payload()),
        "outer": AstroRelativePartyRequest(**astro_payload()),
    }
    with pytest.raises(ValidationError) as caught:
        AstroRelativeRequest(**parties, relationship_mode="synastry")
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_relative_chart_modern_lowercase_synastry_maps_to_influence_mode():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="synastry",
    )

    assert (
        result["relationship_profile"]["relative_mode_resolution"] == "fallback_alias"
    )
    assert result["relationship_profile"]["relative_mode_normalized"] == "influence"
    assert result["relationship_profile"]["relative_mode_label_zh"] == "影响盘"
    assert result["relationship_profile"]["primary_layer"] == "influence_chart_pair"
    assert result["inner"]["chart"]["chart_profile"]["chart_type"] == "influence_inner"
    assert result["outer"]["chart"]["chart_profile"]["chart_type"] == "influence_outer"


def test_relative_chart_defaults_to_compare_mode_when_mode_omitted():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
    )

    assert result["relationship_profile"]["relative_mode_input"] == 0
    assert result["relationship_profile"]["relative_mode_resolution"] == "numeric"
    assert result["relationship_profile"]["relative_mode_normalized"] == "compare"
    assert result["relationship_profile"]["primary_layer"] == "directional_synastry"


def test_relative_compare_and_composite_modes_expose_different_primary_layers():
    compare_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode=0,
    )
    composite_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode=1,
    )

    assert (
        compare_result["relationship_profile"]["relative_mode_normalized"] == "compare"
    )
    assert (
        composite_result["relationship_profile"]["relative_mode_normalized"]
        == "composite"
    )
    assert (
        compare_result["relationship_profile"]["primary_layer"]
        == "directional_synastry"
    )
    assert (
        composite_result["relationship_profile"]["primary_layer"] == "composite_chart"
    )
    assert compare_result["chart"] == {}
    assert composite_result["chart"]["planets"]
    assert compare_result["inner"]["chart"]["planets"]
    assert composite_result["inner"]["chart"]["planets"]


def test_relative_influence_timespace_and_marks_modes_expose_distinct_primary_layers():
    influence_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="Synastry",
        hsys=0,
    )
    timespace_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=0,
    )
    marks_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="Marks",
        hsys=0,
    )

    assert (
        influence_result["relationship_profile"]["relative_mode_normalized"]
        == "influence"
    )
    assert (
        influence_result["relationship_profile"]["primary_layer"]
        == "influence_chart_pair"
    )
    assert (
        influence_result["inner"]["chart"]["chart_profile"]["chart_type"]
        == "influence_inner"
    )
    assert (
        influence_result["outer"]["chart"]["chart_profile"]["chart_type"]
        == "influence_outer"
    )
    assert influence_result["chart"] == {}

    assert (
        timespace_result["relationship_profile"]["relative_mode_normalized"]
        == "timespace"
    )
    assert (
        timespace_result["relationship_profile"]["primary_layer"] == "timespace_chart"
    )
    assert timespace_result["chart"]["chart_profile"]["chart_type"] == "timespace"
    assert timespace_result["chart"]["chart_profile"]["house_system"] == "whole_sign"

    assert marks_result["relationship_profile"]["relative_mode_normalized"] == "marks"
    assert marks_result["relationship_profile"]["primary_layer"] == "marks_chart"
    assert marks_result["chart"]["chart_profile"]["chart_type"] == "marks"
    assert marks_result["chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert (
        timespace_result["chart"]["angles"]["ascendant"]["longitude"]
        != marks_result["chart"]["angles"]["ascendant"]["longitude"]
    )


def test_relative_hsys_zero_and_eight_drive_supported_offline_house_systems():
    whole_sign_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=0,
    )
    equal_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=8,
    )

    assert (
        whole_sign_result["inner_chart"]["chart_profile"]["house_system"]
        == "whole_sign"
    )
    assert whole_sign_result["chart"]["chart_profile"]["house_system"] == "whole_sign"
    assert (
        whole_sign_result["relationship_profile"]["house_system_label_zh"] == "整宫制"
    )
    assert equal_result["inner_chart"]["chart_profile"]["house_system"] == "equal_mc"
    assert equal_result["chart"]["chart_profile"]["house_system"] == "equal_mc"
    assert (
        equal_result["relationship_profile"]["house_system_label_zh"]
        == "天顶为10宫中点等宫制"
    )


def test_relative_hsys_one_to_seven_are_available_offline():
    expected_house_systems = {
        1: "alcabitus",
        2: "regiomontanus",
        3: "placidus",
        4: "koch",
        5: "vehlow_equal",
        6: "polich_page",
        7: "sripati",
    }

    for hsys, expected_house_system in expected_house_systems.items():
        result = calculate_relative_chart_analysis(
            inner_payload=astro_payload(),
            outer_payload={
                **astro_payload(),
                "name": "对盘者",
                "birth_year": 1992,
                "birth_month": 3,
                "birth_day": 2,
                "birth_hour": 8,
                "birth_minute": 18,
            },
            relative_mode="TimeSpace",
            hsys=hsys,
        )

        assert (
            result["inner_chart"]["chart_profile"]["house_system"]
            == expected_house_system
        )
        assert result["chart"]["chart_profile"]["house_system"] == expected_house_system
        assert result["relationship_profile"]["house_system"] == expected_house_system
        assert result["chart"]["houses"]


def test_relative_unsupported_hsys_returns_error_payload():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=9,
    )

    assert result == {
        "error": "relative 关系盘离线模式暂仅支持 hsys=0..8（整宫制、Alcabitus、Regiomontanus、Placidus、Koch、Vehlow Equal、Polich Page、Sripati、天顶为10宫中点等宫制）。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_relative_zodiacal_one_switches_relative_layers_to_sidereal():
    tropical_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=0,
        zodiacal=0,
    )
    sidereal_result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=0,
        zodiacal=1,
    )

    assert tropical_result["inner_chart"]["chart_profile"]["zodiac"] == "tropical"
    assert tropical_result["chart"]["chart_profile"]["zodiac"] == "tropical"
    assert tropical_result["relationship_profile"]["zodiac_mode"] == "tropical"
    assert sidereal_result["inner_chart"]["chart_profile"]["zodiac"] == "sidereal"
    assert sidereal_result["chart"]["chart_profile"]["zodiac"] == "sidereal"
    assert sidereal_result["relationship_profile"]["zodiac_mode"] == "sidereal"
    assert (
        sidereal_result["relationship_profile"]["zodiac_label_zh"]
        == "恒星黄道，岁差:Lahiri"
    )
    assert sidereal_result["inner_chart"]["chart_profile"]["ayanamsha"] > 0
    assert sidereal_result["chart"]["chart_profile"]["ayanamsha"] > 0
    assert (
        tropical_result["inner_chart"]["angles"]["ascendant"]["longitude"]
        != sidereal_result["inner_chart"]["angles"]["ascendant"]["longitude"]
    )
    assert (
        tropical_result["chart"]["planets"][0]["longitude"]
        != sidereal_result["chart"]["planets"][0]["longitude"]
    )


def test_relative_unsupported_zodiacal_returns_error_payload():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="TimeSpace",
        hsys=0,
        zodiacal=2,
    )

    assert result == {
        "error": "relative 关系盘离线模式暂仅支持 zodiacal=0(回归黄道) 或 zodiacal=1(恒星黄道/Lahiri)。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_relative_invalid_mode_returns_structured_validation_error():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={
            **astro_payload(),
            "name": "对盘者",
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        relative_mode="banana",
        hsys=0,
        zodiacal=0,
    )

    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 400
    assert result["retryable"] is False
    assert "relative_mode" in result["error"]
    assert "Composite" in result["error"]


def test_fastmcp_astro_tools_expose_geo_parameters():
    chart_properties = mcp_parameters("astro_chart")["properties"]
    chart13_properties = mcp_parameters("astro_chart13")["properties"]
    hellen_properties = mcp_parameters("astro_hellen_chart")["properties"]
    india_properties = mcp_parameters("astro_india_chart")["properties"]
    germany_properties = mcp_parameters("astro_germany_chart")["properties"]
    relative_properties = mcp_parameters("astro_relative_chart")["properties"]

    assert "birth_longitude" in chart_properties
    assert "birth_latitude" in chart_properties
    assert "hsys" in chart_properties
    assert "zodiacal" in chart_properties
    assert "hsys" in chart13_properties
    assert "zodiacal" in chart13_properties
    assert "hsys" in hellen_properties
    assert "zodiacal" in hellen_properties
    assert "hsys" in india_properties
    assert "zodiacal" in india_properties
    assert "hsys" in germany_properties
    assert "zodiacal" in germany_properties
    assert "inner_birth_latitude" in relative_properties
    assert "outer_birth_longitude" in relative_properties
    assert "relative_mode" in relative_properties
    assert "hsys" in relative_properties
    assert "zodiacal" in relative_properties


def test_offline_angles_match_swisseph_across_charts():
    # The offline _angles fallback (used when swisseph is unavailable) must
    # agree with the swisseph-backed angles, not be 180° / several degrees off.
    from datetime import datetime, timezone

    pytest.importorskip("swisseph")
    cases = [
        (1990, 6, 15, 4, 116.4, 39.9),
        (1975, 1, 20, 22, -73.9, 40.7),
        (2003, 9, 1, 6, 151.2, -33.8),
        (1960, 12, 31, 12, 0.0, 51.5),
    ]
    for year, month, day, hour, lon, lat in cases:
        jd = _julian_day(datetime(year, month, day, hour, tzinfo=timezone.utc))
        offline = _angles(jd, lon, lat)
        truth = _swisseph_angles(jd, lon, lat)
        assert truth is not None
        for key in ("ascendant", "midheaven"):
            diff = abs((offline[key] - truth[key] + 180.0) % 360.0 - 180.0)
            assert diff < 0.05, (key, year, offline[key], truth[key], diff)


def test_julian_day_uses_julian_calendar_before_gregorian_cutover():
    from datetime import datetime, timezone

    swe = pytest.importorskip("swisseph")
    # Modern dates: proleptic Gregorian, unchanged.
    jd_modern = _julian_day(datetime(1990, 6, 15, 12, tzinfo=timezone.utc))
    assert jd_modern == pytest.approx(swe.julday(1990, 6, 15, 12.0, swe.GREG_CAL))
    # Before the 1582-10-15 cutover: the Julian calendar (historical convention).
    jd_old = _julian_day(datetime(1500, 1, 1, 12, tzinfo=timezone.utc))
    assert jd_old == pytest.approx(swe.julday(1500, 1, 1, 12.0, swe.JUL_CAL))


def test_astro_chart_request_accepts_use_true_solar_time_by_python_name():
    """Canonical snake_case flag controls the clock; retired spelling is rejected."""
    assert (
        AstroChartRequest(
            birth_year=1988, birth_month=8, birth_day=8, birth_hour=8
        ).use_true_solar_time
        is False
    )
    by_name = AstroChartRequest(
        birth_year=1988,
        birth_month=8,
        birth_day=8,
        birth_hour=8,
        use_true_solar_time=True,
    )
    assert by_name.use_true_solar_time is True
    with pytest.raises(ValidationError) as caught:
        AstroChartRequest(
            birth_year=1988,
            birth_month=8,
            birth_day=8,
            birth_hour=8,
            useTrueSolarTime=True,
        )
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_cli_no_true_solar_time_flag_actually_disables_correction():
    """End-to-end CLI dispatch: ``--no-use-true-solar-time`` must leave the
    birth clock untouched (no longitude/equation-of-time rebasing)."""
    pytest.importorskip("swisseph")
    from fatebridge.application.execution import execute_spec
    from fatebridge.cli import build_parser

    parser = build_parser()
    base = [
        "astro_chart",
        "--birth-year",
        "1988",
        "--birth-month",
        "8",
        "--birth-day",
        "8",
        "--birth-hour",
        "8",
        "--birth-minute",
        "8",
        "--birth-timezone",
        "Asia/Shanghai",
        "--birth-longitude",
        "120.0",
        "--birth-latitude",
        "30.0",
    ]

    def _run(extra):
        args = parser.parse_args(base + extra)
        spec = getattr(args, "_spec")
        provided = {
            k: v
            for k, v in vars(args).items()
            if k in set(spec.request_model.model_fields) and v is not None
        }
        return execute_spec(spec, spec.request_model(**provided))

    off = _run(["--no-use-true-solar-time"])
    on = _run(["--use-true-solar-time", "true"])
    default = _run([])
    assert off["person_info"]["true_solar"]["applied"] is False
    assert off["person_info"]["birth_datetime"].startswith("1988-08-08T08:08:00")
    assert on["person_info"]["true_solar"]["applied"] is True
    # Western default is the civil clock: no flag → no correction.
    assert default["person_info"]["true_solar"]["applied"] is False


def test_relative_requests_default_timezone_to_none_not_utc():
    """关系/合盘两条入口的 birth_timezone 默认必须是 None，而非硬编码 "UTC"。

    回归历史 bug：默认 "UTC" 会把东八区等墙钟时间当成 UTC，整盘旋转。改默认
    为 None 后，引擎走 birth_place 推断时区（与核心 AstroChartRequest 一致），
    仅在无法识别地名时回退 UTC。
    """
    from fatebridge.core.requests.astrology import (
        AstroRelativeFlatRequest,
        AstroRelativePartyRequest,
    )

    party = AstroRelativePartyRequest(
        birth_year=1990,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_longitude=121.4667,
        birth_latitude=31.2167,
    )
    assert party.birth_timezone is None

    flat = AstroRelativeFlatRequest(
        inner_birth_year=2000,
        inner_birth_month=12,
        inner_birth_day=10,
        inner_birth_hour=9,
        inner_birth_longitude=120.0,
        inner_birth_latitude=30.0,
        outer_birth_year=1992,
        outer_birth_month=3,
        outer_birth_day=2,
        outer_birth_hour=8,
        outer_birth_longitude=120.0,
        outer_birth_latitude=30.0,
    )
    assert flat.inner_birth_timezone is None
    assert flat.outer_birth_timezone is None


@pytest.mark.parametrize(
    "mode, expected_calls",
    [
        ("Comp", (0, 0, 0)),
        ("Synastry", (0, 0, 0)),
        ("Composite", (1, 0, 0)),
        ("TimeSpace", (0, 1, 0)),
        ("Marks", (1, 1, 1)),
    ],
)
def test_relative_chart_computes_only_selected_single_chart(
    mode, expected_calls, monkeypatch
):
    from fatebridge.core.astro import relationship

    calls = [0, 0, 0]
    for index, name in enumerate(
        ("_composite_chart", "_build_timespace_chart", "_build_marks_chart")
    ):
        original = getattr(relationship, name)

        def traced(*args, _original=original, _index=index, **kwargs):
            calls[_index] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(relationship, name, traced)
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(),
        outer_payload={**astro_payload(), "name": "对盘者", "birth_year": 1992},
        relative_mode=mode,
    )
    assert "error" not in result
    assert tuple(calls) == expected_calls
    assert "composite_chart" not in result
    assert not any(key.startswith(("inToOut", "outToIn")) for key in result)
    assert "relationship_mode" not in result["relationship_profile"]
    if mode in {"Comp", "Synastry"}:
        assert result["chart"] == {}
    else:
        assert result["chart"]["planets"]

"""Declared source-day endpoints, same-sky root brackets and native scopes."""

import copy
import gzip
import hashlib
import json
import shutil
from fractions import Fraction as F
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import ephemeris_runtime as native_runtime
from fatebridge.core import guolao_anchor_days as days
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.guolao import build_chart, reading
from fatebridge.core.guolao_classical import life_branch
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.support.ephemeris_context import empty_ephemeris_path

FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-anchor-days-v1"
FLINT_DATA = Path(__file__).parents[1] / "data/guolao/solar_day_flint_v1"
FLINT_BYTES = (FLINT_DATA / "reference.json.gz").read_bytes()
assert (
    hashlib.sha256(FLINT_BYTES).hexdigest()
    == json.loads((FLINT_DATA / "provenance.json").read_text())["reference_sha256"]
)
FLINT_REFERENCE = json.loads(gzip.decompress(FLINT_BYTES))
MODEL_DATA = Path(__file__).parents[1] / "data/guolao/selected_day_models_v1"
MODEL_BYTES = (MODEL_DATA / "reference.json.gz").read_bytes()
MODEL_PROVENANCE = json.loads((MODEL_DATA / "provenance.json").read_text())
assert hashlib.sha256(MODEL_BYTES).hexdigest() == MODEL_PROVENANCE["reference_sha256"]
MODEL_REFERENCE = json.loads(gzip.decompress(MODEL_BYTES))


@pytest.fixture
def selected_day_model(request, tmp_path, monkeypatch):
    model = request.param
    previous = native_runtime.configured_ephemeris_path()
    root = Path(__file__).resolve().parents[2]
    directory = root / "ephe" if model == "swieph" else tmp_path
    if model != "moshier":
        for source in MODEL_PROVENANCE["source_assets"].values():
            relative = Path(source["copy"])
            if relative.parts[1] != model:
                continue
            original = (
                root / "ephe" / relative.name
                if model == "swieph"
                else MODEL_DATA.parent / relative.name
            )
            assert hashlib.sha256(original.read_bytes()).hexdigest() == source["sha256"]
            if model == "jpl":
                shutil.copyfile(original, directory / relative.name)
    try:
        with monkeypatch.context() as change:
            change.setenv("SE_EPHE_PATH", str(directory))
            change.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
            if model == "jpl":
                change.setenv("FATEBRIDGE_JPL_FILE", "guolao-de441-j2000.eph")
            else:
                change.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            native_runtime.swe.close()
            native_runtime.configure_ephemeris_path(str(directory))
            yield model
    finally:
        native_runtime.swe.close()
        native_runtime.configure_ephemeris_path(previous or "")


@pytest.mark.parametrize(
    "row,selected_day_model",
    [
        pytest.param(
            row,
            row["case"]["model"],
            id=row["case"]["id"],
            marks=pytest.mark.local_data if row["case"]["model"] != "moshier" else [],
        )
        for row in MODEL_REFERENCE["rows"]
    ],
    indirect=["selected_day_model"],
)
def test_selected_sun_and_clock_models_match_independent_day_roots(
    row, selected_day_model
):
    case = row["case"]
    assert selected_day_model == case["model"]
    angular_gate = F(
        str(MODEL_REFERENCE["criteria"]["same_explicit_TT_UT1_coordinate_arcseconds"])
    )
    clock_gate = F(
        str(MODEL_REFERENCE["criteria"]["clock_and_independent_C04_conversion_seconds"])
    )
    physical = None
    with use_ut1_source(case["clock"]):
        for policy in days.POLICIES[1:]:
            result = calculate_core_chart_analysis(
                **case["birth"],
                birth_latitude=40,
                name="虚构选定时标与星历日界测试",
                use_true_solar_time=case["birth"]["birth_clock_basis"] == "civil",
                zodiacal=case["zodiacal"],
                chart_variant="guolao_chart",
                guolao_seasonal_anchor_policy=policy,
            )
            assert "error" not in result, result
            profile = result["guolao"]["profile"]
            assert profile["julian_day_tt"] == row["common_julian_day_tt"]
            assert profile["julian_day_ut1"] == row["common_julian_day_ut1"]
            assert (
                abs(
                    F(profile["julian_day_tt"])
                    - F(row["independent_birth_julian_day_tt_exact"])
                )
                * 86400
                <= clock_gate
            )
            assert (
                profile["ephemeris_provenance"]["by_body"]["Sun"]["ecliptic_model"]
                == case["model"]
            )
            clock = profile["apparent_solar_clock"]
            assert clock["earth_rotation_basis"] == "supplied_same_instant_ut1"
            for key, refkey in [
                ("sun_apparent_right_ascension", "sun_apparent_right_ascension_exact"),
                (
                    "greenwich_apparent_sidereal_degrees",
                    "greenwich_apparent_sidereal_degrees_exact",
                ),
            ]:
                error = (
                    abs(
                        (F(clock[key]) - F(row["birth_reference"][refkey]) + 180) % 360
                        - 180
                    )
                    * 3600
                )
                assert error <= angular_gate
            assert (
                abs(
                    F(clock["equation_of_time_seconds"])
                    - F(row["birth_reference"]["equation_of_time_seconds_exact"])
                )
                <= clock_gate
            )
            facts = {
                key: result[key]
                for key in ["planets", "angles", "houses", "person_info"]
            }
            if physical is None:
                physical = facts
            else:
                assert physical == facts
            evidence = result["guolao"]["life_palace"]["seasonal_anchor_evidence"]
            assert [evidence["anchor_branch"]] == row["expected_policy_candidates"][
                policy
            ]
            assert evidence["same_birth_source_cohort_checked"] is True
            assert evidence["actual_sun_model"] == case["model"]
            assert (
                F(evidence["full_search_UT1_window_exact"][1])
                - F(evidence["full_search_UT1_window_exact"][0])
                == 3
            )
            for actual, reference in zip(
                evidence["day_edge_brackets"], row["reference_day_edges"]
            ):
                lower, upper = [
                    F(actual[side]["julian_day_ut1_exact"])
                    for side in ["lower", "upper"]
                ]
                ref_lower, ref_upper = [
                    F(reference[side]["julian_day_ut1_exact"])
                    for side in ["lower", "upper"]
                ]
                assert max(lower, ref_lower) < min(upper, ref_upper)
                assert (upper - lower) * 86400 <= F(1, 1000)
                target = actual["target_solar_label_ordinal"]
                assert target == reference["target_solar_label_ordinal"]
                assert (
                    F(actual["lower"]["apparent_solar_label_serial_exact"])
                    < target
                    <= F(actual["upper"]["apparent_solar_label_serial_exact"])
                )
            assert evidence["physical_time_accuracy_certified"] is False
            assert evidence["winter_day_inclusion_adjudicated"] is False


@pytest.mark.parametrize(
    "case,selected_day_model",
    [
        pytest.param(
            case,
            case["model"],
            id=case["id"],
            marks=pytest.mark.local_data if case["model"] != "moshier" else [],
        )
        for case in MODEL_REFERENCE["negative_cases"]
    ],
    indirect=["selected_day_model"],
)
def test_actual_c04_day_window_never_extrapolates_or_shrinks(case, selected_day_model):
    assert selected_day_model == case["model"]
    with use_ut1_source(case["clock"]):
        for policy in days.POLICIES[1:]:
            result = calculate_core_chart_analysis(
                **case["birth"],
                birth_latitude=40,
                name="虚构固定日界窗越界测试",
                use_true_solar_time=True,
                chart_variant="guolao_chart",
                guolao_seasonal_anchor_policy=policy,
            )
            assert "error" in result, result
            assert "no prediction, extrapolation or Swiss fallback" in result["error"]


def test_declared_whole_day_policies_match_independent_event_day_relations():
    for row in FLINT_REFERENCE["day_rows"]:
        for include, key in [
            (False, "expected_exclusive"),
            (True, "expected_inclusive"),
        ]:
            assert (
                days.anchor_from_day_longitudes(
                    F(*row["start"]),
                    F(*row["end"]),
                    include_winter_day=include,
                )
                == row[key]
            ), (row["id"], key)


def test_root_brackets_contain_independent_flint_roots_and_keep_original_rejections():
    for row in FLINT_REFERENCE["root_rows"]:
        origin = float.fromhex(row["origin"])
        serial = F(row["ordinal"]) + F(*row["phase"])
        a, b, c = map(F, row["coefficients"])

        def evaluate(at):
            x = F(at) - F(origin)
            return dict(
                julian_day_ut1_exact=str(F(at)),
                apparent_solar_label_serial_exact=str(
                    serial + a * x + b * x * x + c * x * x * x
                ),
            )

        roots, grid = days._day_brackets(origin, serial, evaluate)
        assert len(grid) == 13 and F(grid[-1]) - F(grid[0]) == 3, row["id"]
        for actual, reference in zip(roots, row["reference_roots"]):
            lower = F(actual["lower"]["julian_day_ut1_exact"])
            upper = F(actual["upper"]["julian_day_ut1_exact"])
            assert (
                lower
                < F(reference["lower_ut1_exact"])
                <= F(reference["upper_ut1_exact"])
                <= upper
            ), row["id"]
            assert (upper - lower) * 86400 <= F(1, 1000), row["id"]
            assert actual["target_solar_label_ordinal"] == reference["target"]
        assert (
            F(roots[0]["upper"]["julian_day_ut1_exact"])
            < F(origin)
            < F(roots[1]["lower"]["julian_day_ut1_exact"])
        ), row["id"]
    for row in FLINT_REFERENCE["rejection_rows"]:
        origin = float.fromhex(row["origin"])
        serial = F(730120) + F(*row["phase"])
        a, b, c = map(F, row["coefficients"])

        def evaluate(at):
            x = F(at) - F(origin)
            return dict(
                julian_day_ut1_exact=str(F(at)),
                apparent_solar_label_serial_exact=str(
                    serial + a * x + b * x * x + c * x * x * x
                ),
            )

        with pytest.raises(ValueError, match=row["error"]):
            days._day_brackets(origin, serial, evaluate)


@pytest.mark.parametrize(
    "case", FLINT_REFERENCE["physical_rows"], ids=lambda case: case["input"]["id"]
)
def test_actual_solar_days_match_original_author_and_official_sofa_root_intervals(case):
    kwargs = {key: value for key, value in case["input"].items() if key != "id"}
    with empty_ephemeris_path():
        for policy in days.POLICIES[1:]:
            result = calculate_core_chart_analysis(
                **kwargs,
                birth_latitude=40,
                name="虚构太阳日数值边界测试",
                use_true_solar_time=kwargs["birth_clock_basis"] == "civil",
                chart_variant="guolao_chart",
                guolao_seasonal_anchor_policy=policy,
            )
            assert "error" not in result, result
            profile = result["guolao"]["profile"]
            assert profile["julian_day_ut1"] == case["julian_day_ut1"]
            assert profile["julian_day_tt"] == case["julian_day_tt"]
            clock = profile["apparent_solar_clock"]
            reference_clock = case["birth_clock_reference"]
            for key, reference_key in [
                ("sun_apparent_right_ascension", "sun_apparent_right_ascension_exact"),
                (
                    "greenwich_apparent_sidereal_degrees",
                    "greenwich_apparent_sidereal_degrees_exact",
                ),
            ]:
                error = (
                    abs(
                        (F(clock[key]) - F(reference_clock[reference_key]) + 180) % 360
                        - 180
                    )
                    * 3600
                )
                assert error <= F(str(FLINT_REFERENCE["physical_gate_arcseconds"]))
            assert abs(
                F(clock["equation_of_time_seconds"])
                - F(reference_clock["equation_of_time_seconds_exact"])
            ) <= F(str(FLINT_REFERENCE["physical_clock_gate_seconds"]))
            evidence = result["guolao"]["life_palace"]["seasonal_anchor_evidence"]
            assert [evidence["anchor_branch"]] == case["expected_policy_candidates"][
                policy
            ]
            assert evidence["same_birth_source_cohort_checked"] is True
            assert evidence["actual_sun_model"] == "moshier"
            assert (
                F(evidence["full_search_UT1_window_exact"][1])
                - F(evidence["full_search_UT1_window_exact"][0])
                == 3
            )
            for actual, reference in zip(
                evidence["day_edge_brackets"], case["reference_day_edges"]
            ):
                lower, upper = [
                    F(actual[side]["julian_day_ut1_exact"])
                    for side in ["lower", "upper"]
                ]
                ref_lower, ref_upper = [
                    F(reference[side]["julian_day_ut1_exact"])
                    for side in ["lower", "upper"]
                ]
                assert max(lower, ref_lower) < min(upper, ref_upper)
                assert (upper - lower) * 86400 <= F(1, 1000)
                assert (
                    actual["target_solar_label_ordinal"]
                    == reference["target_solar_label_ordinal"]
                )
                target = actual["target_solar_label_ordinal"]
                assert (
                    F(actual["lower"]["apparent_solar_label_serial_exact"])
                    < target
                    <= F(actual["upper"]["apparent_solar_label_serial_exact"])
                )
            for flag in [
                "UTC_day_edge_labels_assigned",
                "historical_local_day_boundary_accepted",
                "source_sunrise_geometry_adjudicated",
                "winter_day_inclusion_adjudicated",
                "physical_time_accuracy_certified",
            ]:
                assert evidence[flag] is False


def birth(**updates):
    args = dict(
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
        name="虚构安命日界测试",
        use_true_solar_time=True,
        preserve_instant=True,
        require_resolved_timezone=True,
    )
    args.update(updates)
    return build_astro_birth_info(**args)


@pytest.mark.parametrize(
    "start,end,exclusive,inclusive",
    [
        ("269", "270", "卯", "卯"),
        ("269.5", "270.5", "卯", "辰"),
        ("270", "271", "卯", "辰"),
        ("270.001", "271.001", "辰", "辰"),
        ("299.5", "300.5", "辰", "辰"),
        ("300", "301", "辰", "辰"),
        ("300.001", "301.001", "卯", "卯"),
        ("89", "90", "卯", "卯"),
        ("89.5", "90.5", "寅", "寅"),
        ("90", "91", "寅", "寅"),
        ("104.5", "105.5", "寅", "寅"),
        ("105", "106", "寅", "寅"),
        ("105.001", "106.001", "卯", "卯"),
        ("359.5", ".5", "卯", "卯"),
    ],
)
def test_printed_day_endpoints_and_explicit_winter_hypotheses(
    start, end, exclusive, inclusive
):
    assert (
        days.anchor_from_day_longitudes(F(start), F(end), include_winter_day=False)
        == exclusive
    )
    assert (
        days.anchor_from_day_longitudes(F(start), F(end), include_winter_day=True)
        == inclusive
    )


@pytest.mark.parametrize(
    "start,end,winter",
    [
        (F(1), F(1), True),
        (F(1), F(4), True),
        (F(360), F(1), True),
        (1.0, F(2), True),
        (F(1), F(2), 1),
    ],
)
def test_bad_or_implicit_day_edges_rejected(start, end, winter):
    with pytest.raises((TypeError, ValueError)):
        days.anchor_from_day_longitudes(start, end, include_winter_day=winter)


def _linear_evaluator(origin, serial):
    return lambda at: dict(
        julian_day_ut1_exact=str(F(at)),
        apparent_solar_label_serial_exact=str(serial + F(at) - F(origin)),
    )


def test_root_brackets_enclose_an_independent_linear_clock_oracle_without_rounding():
    at = 2451545.1
    serial = F("730120.25")
    roots, grid = days._day_brackets(at, serial, _linear_evaluator(at, serial))
    assert len(grid) == 13 and F(grid[-1]) - F(grid[0]) == 3
    for root, expected in zip(roots, [F(at) - F(1, 4), F(at) + F(3, 4)]):
        lo = F(root["lower"]["julian_day_ut1_exact"])
        hi = F(root["upper"]["julian_day_ut1_exact"])
        assert lo < expected <= hi
        assert F(root["bracket_width_UT1_seconds_exact"]) <= F(1, 1000)


def test_birth_inside_a_numerical_midnight_bracket_errors_instead_of_picking_a_day():
    at = 2451545.0
    serial = F(730120)
    with pytest.raises(ValueError, match="数值日界"):
        days._day_brackets(at, serial, _linear_evaluator(at, serial))


def test_nonmonotonic_full_search_scan_does_not_return_a_local_fitted_root():
    with pytest.raises(ValueError, match="单调"):
        days._day_brackets(
            2451545.0,
            F("730120.5"),
            lambda at: dict(apparent_solar_label_serial_exact=str(-F(at))),
        )


@pytest.mark.parametrize("policy", days.POLICIES[1:])
def test_real_native_day_policy_changes_only_symbolic_mapping_and_keeps_physical_planets(
    policy,
):
    b = birth()
    original = build_chart(b)
    updated = build_chart(b, seasonal_anchor_policy=policy)
    assert original["guolao"]["life_palace"]["branch"] == "辰"
    life = updated["guolao"]["life_palace"]
    evidence = life["seasonal_anchor_evidence"]
    assert life["branch"] == "卯"
    assert life["branch"] == life_branch(
        life["sun_palace_branch"], life["birth_hour_branch"], evidence["anchor_branch"]
    )
    assert updated["guolao"]["profile"]["ruleset_id"] == days.DAY_RULESET
    for key in ["planets", "angles", "houses", "person_info"]:
        assert updated[key] == original[key]
    for key in [
        "julian_day_tt",
        "julian_day_ut1",
        "utc_datetime",
        "apparent_solar_clock",
    ]:
        assert updated["guolao"]["profile"][key] == original["guolao"]["profile"][key]
    assert (
        evidence["actual_sun_model"]
        == updated["guolao"]["profile"]["ephemeris_provenance"]["by_body"]["Sun"][
            "ecliptic_model"
        ]
    )
    for root in evidence["day_edge_brackets"]:
        target = root["target_solar_label_ordinal"]
        assert (
            F(root["lower"]["apparent_solar_label_serial_exact"])
            < target
            <= F(root["upper"]["apparent_solar_label_serial_exact"])
        )
        assert F(root["bracket_width_UT1_seconds_exact"]) <= F(1, 1000)
    assert evidence["physical_time_accuracy_certified"] is False
    assert evidence["historical_local_day_boundary_accepted"] is False
    assert evidence["actual_sunrise_used_for_anchor"] is False
    text = reading(updated)
    assert "真太阳日" in text["interpretation"]["core_identity"]
    assert (
        text["interpretation_evidence"]["core_identity"]["policy_id"]
        == "guolao_calculation_reading_v3"
    )
    assert (
        "guolao.life_palace"
        in text["interpretation_evidence"]["core_identity"]["source_paths"]
    )


@pytest.mark.parametrize(
    "month,day", [(1, 20), (1, 21), (6, 21), (7, 7), (12, 21), (12, 22)]
)
@pytest.mark.parametrize("longitude", [-180.0, 0.0, 116.4, 180.0])
def test_same_physical_birth_and_both_zodiacs_keep_the_same_solar_day_anchor(
    month, day, longitude
):
    b = birth(birth_month=month, birth_day=day, birth_longitude=longitude)
    anchors = []
    for zodiac in [0, 1]:
        result = build_chart(
            b, zodiacal=zodiac, seasonal_anchor_policy=days.POLICIES[1]
        )
        anchors.append(result["guolao"]["life_palace"]["counting_anchor_branch"])
    assert anchors[0] == anchors[1]


def test_explicit_term_instants_keeps_complete_legacy_output():
    b = birth()
    assert build_chart(b) == build_chart(b, seasonal_anchor_policy="term_instants")


@pytest.mark.parametrize("policy", ["other", True, days.POLICIES[1]])
def test_core_scope_and_required_solar_clock_are_checked_before_calculation(policy):
    with pytest.raises(ValueError):
        build_chart(birth(use_true_solar_time=False), seasonal_anchor_policy=policy)


@pytest.mark.parametrize("model", [AstroGuolaoRequest, AstroChartPolyRequest])
def test_request_policy_requires_true_solar_and_alias_scope(model):
    args = dict(
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
        guolao_seasonal_anchor_policy=days.POLICIES[1],
    )
    if model is AstroChartPolyRequest:
        args["chart_variant"] = "guolao_chart"
    with pytest.raises(ValidationError):
        model(**args)
    assert (
        model(**args, use_true_solar_time=True).guolao_seasonal_anchor_policy
        == days.POLICIES[1]
    )
    if model is AstroChartPolyRequest:
        args["chart_variant"] = "chart"
        with pytest.raises(ValidationError):
            model(**args, use_true_solar_time=True)


def test_germany_alias_does_not_forward_guolao_only_policy_to_its_service():
    from fatebridge.services.catalog.astro_bindings import _astro_chart_bind

    request = AstroChartPolyRequest(
        chart_variant="germany",
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
    )
    _, _, kwargs = _astro_chart_bind(request)
    assert "guolao_seasonal_anchor_policy" not in kwargs


def test_backend_change_never_silently_falls_back_to_a_different_solar_day():
    b = birth()
    original = build_chart(b)
    g = original["guolao"]
    model = g["profile"]["ephemeris_provenance"]["by_body"]["Sun"]["ecliptic_model"]
    wrong = "moshier" if model != "moshier" else "jpl"
    with pytest.raises(Exception, match="model|coordinate|ephemeris"):
        days.apparent_solar_day_anchor(
            b,
            birth_clock=g["profile"]["apparent_solar_clock"],
            birth_ut1=g["profile"]["julian_day_ut1"],
            expected_sun_model=wrong,
            birth_sun_source=g["profile"]["longitude_motion"][
                "physical_ephemeris_source"
            ],
            policy=days.POLICIES[1],
        )


def test_birth_source_edition_change_is_not_conflated_with_a_day_policy():
    b = birth()
    original = build_chart(b)
    g = original["guolao"]
    source = copy.deepcopy(
        g["profile"]["longitude_motion"]["physical_ephemeris_source"]
    )
    if not source["files"]:
        source["files"] = [
            {
                "id": "synthetic-unknown",
                "slot": 0,
                "filename": "synthetic.se1",
                "sha256": "synthetic",
                "de_number": 431,
            }
        ]
        source["by_factor"]["Sun"]["file_ids"] = ["synthetic-unknown"]
    else:
        for f in source["files"]:
            f["de_number"] += 1
    with pytest.raises(Exception, match="edition|model|source|ephemeris"):
        days.apparent_solar_day_anchor(
            b,
            birth_clock=g["profile"]["apparent_solar_clock"],
            birth_ut1=g["profile"]["julian_day_ut1"],
            expected_sun_model=g["profile"]["ephemeris_provenance"]["by_body"]["Sun"][
                "ecliptic_model"
            ],
            birth_sun_source=source,
            policy=days.POLICIES[1],
        )

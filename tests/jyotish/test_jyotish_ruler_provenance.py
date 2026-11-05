"""Per-ruler source dependencies, not a global selected-model attribution."""

import copy

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india
from fatebridge.core.jyotish_evidence import cheshta_ruler_provenance
from fatebridge.core.jyotish_mean import MODEL, SOURCE, STAR_PLANETS
from fatebridge.core.jyotish_motion import cheshta_arc


def birth_payload(year=2000, hour=0):
    return dict(
        birth_year=year,
        birth_month=1,
        birth_day=1,
        birth_hour=hour,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
    )


def motion_factors(india):
    return [
        f
        for topic in india["topic_evidence"].values()
        for f in topic["factors"]
        if f.get("fact_path", "").startswith("india.strengths.cheshta_bala.summary.")
    ]


def resolve(body, path):
    for part in path.split("."):
        body = body[int(part)] if isinstance(body, list) else body[part]
    return body


def assert_attribution(india):
    computed = (
        india["strengths"]["cheshta_bala"]["model_context"]["status"]
        == "computed_declared_secular_model"
    )
    found = set()
    for factor in motion_factors(india):
        planet = factor["fact_path"].rsplit(".", 1)[1]
        found.add(planet)
        context = factor["calculation_context"]
        method = context["method_context"]
        luminary = planet in {"Sun", "Moon"}
        assert method["five_star_mean_model_applied"] is (computed and not luminary)
        expected_rule = (
            "jyotish.luminary_cheshta.v1"
            if luminary
            else (
                "jyotish.cheshta_simon1994.v1" if computed else "jyotish.cheshta_arc.v1"
            )
        )
        assert factor["rule_id"] == expected_rule
        assert method["reading_rule_id"] == "jyotish.cheshta_ruler_provenance.v1"
        if luminary:
            assert "supporting_source_id" not in factor
            assert factor["source_section"] == "27.18, printed284"
            assert method["value_origin"] == (
                "ayana_bala" if planet == "Sun" else "paksha_bala"
            )
            assert all(".model_context" not in p for p in context["context_paths"])
            assert all(
                ".model_context." not in row["fact_path"]
                for row in context["constraints"]
            )
        elif computed:
            assert factor["supporting_source_id"] == SOURCE["id"]
            assert "27.24-25" in factor["source_section"]
        else:
            assert "supporting_source_id" not in factor
            assert factor["fact"] is None
            assert "本五星宫主" in factor["traditional_interpretation"]
            assert "未计算" in factor["traditional_interpretation"]
        for claim in [
            *context["scenarios"],
            *context["constraints"],
            *method["input_claims"],
        ]:
            assert resolve({"india": india}, claim["fact_path"]) == claim["value"]
    return found


@pytest.mark.parametrize(
    "year,model", [(2000, "unadjudicated"), (2000, MODEL), (1800, MODEL), (2051, MODEL)]
)
def test_frozen_twelve_hour_grid_covers_every_ruler_without_global_model_leakage(
    year, model
):
    found = set()
    for hour in range(0, 24, 2):
        india = build_india(
            build_astro_birth_info(**birth_payload(year, hour), preserve_instant=True),
            divisions=[],
            cheshta_model=model,
        )
        found |= assert_attribution(india)
    assert found == {"Sun", "Moon", *STAR_PLANETS}


@pytest.fixture(scope="module")
def computed():
    return build_india(
        build_astro_birth_info(**birth_payload(), preserve_instant=True),
        divisions=[],
        cheshta_model=MODEL,
    )


@pytest.mark.parametrize("planet", ["Sun", "Moon", *STAR_PLANETS])
def test_contradictory_upstream_value_cannot_receive_a_faithful_source_receipt(
    computed, planet
):
    motion = copy.deepcopy(computed["strengths"]["cheshta_bala"])
    first = next(iter(motion["scenarios"].values()))
    first[planet] += 1
    with pytest.raises(ValueError, match="upstream inputs"):
        cheshta_ruler_provenance(planet, motion, computed["strengths"]["kala_bala"])


def test_computed_mean_with_unadjudicated_arc_keeps_applied_source_and_missing_value(
    computed,
):
    # Controlled opposed operands, not an independently observed birth case.
    # Editing only the status/value would fabricate a missing calculation.
    motion = copy.deepcopy(computed["strengths"]["cheshta_bala"])
    model = motion["model_context"]
    evidence = model["planet_evidence"]["Mars"]
    mean = evidence["mean_longitude"]
    assert 180 <= mean < 360
    true = mean - 180  # exact subtraction for these binary input operands
    point = model["true_position_provenance"]["Mars"]
    point.update(
        longitude=true, ephemeris_model="controlled_geometric_operand", retflag=0
    )
    evidence["true_longitude"] = true
    evidence["arc"] = cheshta_arc(
        mean,
        true,
        evidence["seeghrochcha"],
        mean_frame=model["frame"],
        true_frame=point["frame"],
        seeghrochcha_frame=model["frame"],
    )
    assert evidence["arc"]["status"] == "opposed_midpoint_not_adjudicated"
    assert evidence["arc"]["value"] is None
    motion["summary"]["Mars"] = None
    for row in motion["scenarios"].values():
        row["Mars"] = None
    motion["missing_planets"] = [
        planet for planet in STAR_PLANETS if motion["summary"][planet] is None
    ]
    evidence = cheshta_ruler_provenance(
        "Mars", motion, computed["strengths"]["kala_bala"]
    )
    assert evidence["supporting_source_id"] == SOURCE["id"]
    assert evidence["method_context"]["five_star_mean_model_applied"] is True
    assert (
        evidence["method_context"]["calculation_status"]
        == "opposed_midpoint_not_adjudicated"
    )


@pytest.mark.parametrize("hour,planet", [(2, "Moon"), (4, "Sun")])
def test_luminary_origin_is_unchanged_by_selecting_an_unrelated_five_star_model(
    hour, planet
):
    packets = []
    for model in ("unadjudicated", MODEL):
        india = build_india(
            build_astro_birth_info(**birth_payload(hour=hour), preserve_instant=True),
            divisions=[],
            cheshta_model=model,
        )
        packets.append(
            next(
                f
                for f in motion_factors(india)
                if f["fact_path"].endswith("." + planet)
            )
        )
    for key in (
        "fact",
        "rule_id",
        "source_id",
        "source_section",
        "traditional_interpretation",
    ):
        assert packets[0][key] == packets[1][key]
    assert (
        packets[0]["calculation_context"]["method_context"]
        == packets[1]["calculation_context"]["method_context"]
    )


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
@pytest.mark.parametrize(
    "year,hour,model",
    [
        (2000, 2, MODEL),
        (2000, 4, MODEL),
        (2000, 0, MODEL),
        (2000, 0, "unadjudicated"),
        (1800, 0, MODEL),
        (2051, 0, MODEL),
    ],
)
def test_per_ruler_dependencies_survive_rest_mcp_cli(
    monkeypatch, capsys, key, year, hour, model
):
    from tests.jyotish.test_jyotish_transports import call_surfaces

    payload = {**birth_payload(year, hour), "divisions": [], "cheshta_model": model}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    elif key == "astro_vimshottari":
        payload["analysis_year"] = 2100
    packet = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.topic_evidence",
            "india.strengths.cheshta_bala",
            "india.strengths.kala_bala",
            "india.rule_trace",
        ],
    )
    assert_attribution(packet["india"])
    assert "jyotish.cheshta_ruler_provenance.v1" in {
        row["rule_id"] for row in packet["india"]["rule_trace"]
    }


@pytest.mark.parametrize("hour", [0, 2, 4])
def test_upstream_input_claims_verify_against_the_same_original_run(hour):
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = next(s for s in CATALOG if s.key == "astro_india")
    body = execute_tool(
        spec,
        spec.request_model.model_validate(
            {**birth_payload(hour=hour), "cheshta_model": MODEL, "divisions": []}
        ),
        options=ExecutionOptions(as_of="2026-10-23T00:00:00Z"),
    )
    metadata = body["run_metadata"]
    claims = [
        CalculationClaim(
            path=row["fact_path"],
            value=row["value"],
            run_id=metadata["run_id"],
            business_output_sha256=metadata["business_output_sha256"],
        )
        for f in motion_factors(body["india"])
        for row in f["calculation_context"]["method_context"]["input_claims"]
    ]
    assert claims
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    wrong = copy.deepcopy(claims)
    wrong[0].value = "forged_source"
    assert verify_calculation_claims(body, wrong)["status"] == "rejected"
    stale = copy.deepcopy(claims)
    stale[0].run_id = "another_run"
    assert verify_calculation_claims(body, stale)["status"] == "rejected"

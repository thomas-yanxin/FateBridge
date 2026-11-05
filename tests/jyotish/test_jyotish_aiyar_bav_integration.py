"""Own-profile source/context on nominal vargas, sample groups and native text."""

import copy

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, topic_evidence
from fatebridge.core.jyotish_aiyar_ashtakavarga import RULE, SOURCE, calculate
from fatebridge.core.output_jyotish import JyotishIndia
from tests.fixtures.surface_payloads import astro_payload
from tests.jyotish.test_jyotish_ashtakavarga import resolve


@pytest.fixture(scope="module")
def india():
    return build_india(
        build_astro_birth_info(**astro_payload(), preserve_instant=True),
        divisions=[2, 3, 7, 9, 10, 12, 30],
        birth_time_uncertainty_minutes=1,
    )


def test_every_varga_and_own_sample_group_has_its_own_raw_source_chain(india):
    assert india["profile"]["ruleset_id"] == "parashari_lahiri_core_v29"
    assert RULE in {r["rule_id"] for r in india["rule_trace"]}
    assert SOURCE["id"] in {r["id"] for r in india["rulesets"]}
    typed = JyotishIndia.model_validate(india).model_dump(
        mode="json", exclude_unset=True
    )
    assert typed["ashtakavarga"] == india["ashtakavarga"]
    tables = india["ashtakavarga"]["charts"]
    assert len(tables) == 8
    for name, nominal in tables.items():
        groups = india["birth_time_sensitivity"]["ashtakavarga_variants"]["charts"][
            name
        ]
        for table in [nominal, *groups]:
            profile = table["source_profile_comparison"]["aiyar1905"]
            expected = calculate(table["input_sign_indices"])
            assert all(profile[k] == v for k, v in expected.items())
            delta = profile["comparison_to_default"]
            assert delta["same_input_sign_indices"] is True
            for planet, indices in delta["bhinna_different_sign_indices"].items():
                assert indices == [
                    i
                    for i in range(12)
                    if profile["bhinna"][planet][i] != table["bhinna"][planet][i]
                ]
        assert (
            nominal["source_profile_comparison"]["aiyar1905"]["input_claims"]
            == nominal["input_claims"]
        )
        assert all(
            "input_claims" not in g["source_profile_comparison"]["aiyar1905"]
            for g in groups
        )


def test_native_reading_and_every_author_claim_resolve_to_this_actual_result(india):
    found = []
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            context = factor.get("calculation_context", {}).get("method_context", {})
            other = context.get("source_profile_comparisons", {}).get("aiyar1905")
            if other is None:
                continue
            found.append(factor)
            assert other["source_id"] == SOURCE["id"]
            for claim in other["input_claims"]:
                assert resolve({"india": india}, claim["fact_path"]) == claim["value"]
            assert len(other["input_claims"]) == 10
            text = factor["traditional_interpretation"]
            assert "按Rao表" in text and "Aiyar1905自己的原始表" in text
            assert (
                f"{other['ruler_sign_count']}个有利点" in text
                and f"SAV为{other['house_sav']}" in text
            )
    assert len(found) == 5


@pytest.mark.parametrize(
    "field", ["bhinna", "source_id", "input_claims", "samudaya", "reduction"]
)
def test_another_authors_tampered_table_cannot_receive_faithful_reading(india, field):
    bad = copy.deepcopy(india["ashtakavarga"])
    other = bad["charts"]["D1"]["source_profile_comparison"]["aiyar1905"]
    if field == "bhinna":
        other[field]["Moon"][0] += 1
    elif field == "source_id":
        other[field] = "pretend-rao"
    elif field == "input_claims":
        other[field][0]["value"] = "invented"
    elif field == "samudaya":
        other[field][0] += 1
    else:
        other["reduction_analysis"]["targets"]["Moon"]["reduced_sum"] += 1
    with pytest.raises(ValueError, match="contradicts"):
        topic_evidence(india["charts"], ashtakavarga=bad)

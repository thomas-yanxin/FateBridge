"""Per-table source comparison without completing or replacing Rao fields."""

import json
from pathlib import Path

import pytest

from fatebridge.core import jyotish_aiyar_reductions as aiyar
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india
from fatebridge.core.jyotish_pinda import PLANETS, analyze
from fatebridge.core.output_jyotish import JyotishIndia
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parent / "fixtures"
OLD = json.loads((FIXTURES / "jyotish-pinda-full-bav-reference.json").read_text())
NEW = json.loads((FIXTURES / "jyotish-aiyar-reductions-reference.json").read_text())
EXPECTED = {r["case_id"]: r for r in NEW["full_rows"]}


@pytest.mark.parametrize("case", OLD, ids=lambda c: c["name"])
def test_all91_complete_inputs_keep_rao_values_and_add_separate637_rows(case):
    actual = analyze(case["bav"], {g: case["signs"][g] for g in PLANETS})
    profile = actual["source_profile_comparison"]["aiyar1905_commentary"]
    assert profile["source_id"] == aiyar.SOURCE["id"]
    assert profile["rao_default_replaced"] is False
    for planet in PLANETS:
        assert all(
            actual["targets"][planet][k] == case["targets"][planet][k]
            for k in ["trikona", "sodhita", "rasi_pinda", "graha_pinda", "sodhya_pinda"]
        )
        frozen = EXPECTED[case["name"] + ":" + planet]
        assert all(
            profile["targets"][planet][k] == frozen[k]
            for k in ["trikona", "sodhita", "reduced_sum"]
        )
        assert "sodhya_pinda" not in profile["targets"][planet]


def test_all_vargas_and_own_sample_tables_keep_typed_source_comparisons():
    india = build_india(
        build_astro_birth_info(**astro_payload(), preserve_instant=True),
        divisions=[2, 3, 7, 9, 10, 12, 30],
        birth_time_uncertainty_minutes=1,
    )
    assert india["profile"]["ruleset_id"] == "parashari_lahiri_core_v29"
    assert aiyar.RULE in {x["rule_id"] for x in india["rule_trace"]}
    assert (
        next(x for x in india["rulesets"] if x["id"] == aiyar.SOURCE["id"])[
            "source_kind"
        ]
        == "english_translation_commentary"
    )
    typed = JyotishIndia.model_validate(india).model_dump(
        mode="json", exclude_unset=True
    )
    assert typed["ashtakavarga"] == india["ashtakavarga"]
    nominal = india["ashtakavarga"]["charts"]
    samples = india["birth_time_sensitivity"]["ashtakavarga_variants"]["charts"]
    assert len(nominal) == 8 and set(nominal) == set(samples)
    for name, table in nominal.items():
        for current in [table, *samples[name]]:
            analysis = current["reduction_analysis"]
            profile = analysis["source_profile_comparison"]["aiyar1905_commentary"]
            assert profile["input_sign_indices"] == {
                p: current["input_sign_indices"][p] for p in PLANETS
            }
            assert set(profile["targets"]) == set(PLANETS)
            for p in PLANETS:
                assert profile["targets"][p] == aiyar.reduce_row(
                    current["bhinna"][p],
                    sorted(set(profile["input_sign_indices"].values())),
                )
            assert all(isinstance(x, int) for x in profile["targets"]["Sun"]["sodhita"])

"""Regression checks for strength evidence and independent useful-god layers."""

import json
from itertools import product

import pytest
from fastapi.testclient import TestClient

from fatebridge.core.classical import seasonal_climate_god
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.rules import BaZiRules
from fatebridge.utils.data import STEM_ELEMENTS, Element

PILLARS = {
    "year": ("庚", "辰"),
    "month": ("戊", "子"),
    "day": ("壬", "寅"),
    "hour": ("乙", "巳"),
}
BIRTH = {
    "gender": "男",
    "birth_year": 2000,
    "birth_month": 12,
    "birth_day": 10,
    "birth_hour": 9,
    "birth_minute": 55,
    "birth_place": "南通",
    "birth_timezone": "Asia/Shanghai",
}


def test_sensitive_strength_does_not_automatically_add_water():
    analysis = ElementAnalysis.comprehensive_analysis(PILLARS)
    assert analysis["day_master"]["strength_level"] == "强"
    assert analysis["favorable_elements"] == []
    evidence = analysis["day_master"]["assessment"]
    assert evidence["status"] == "boundary_sensitive"
    assert evidence["support_strength"] > 0
    assert evidence["weaken_strength"] > 0
    assert evidence["month_command"]["phase"] == "旺"
    assert {root["pillar"] for root in evidence["roots"]} == {"year", "month"}
    assert set(evidence["sensitivity"]["candidate_strengths"]) == {"强", "中和"}
    assert evidence["limitations"]


def test_original_case_preserves_wood_conflict_and_fire_reference():
    profile = BaZiRules.chart_useful_profile(PILLARS)
    assert set(profile["useful_elements"]) == {"土", "金"}
    assert profile["avoid_elements"] == []
    assert set(profile["conditional_elements"]) == {"木", "火"}
    assert profile["neutral_elements"] == ["水"]
    wood = next(item for item in profile["conflicts"] if item["element"] == "木")
    assert "shang_guan_pei_yin" in wood["supporting_sources"]
    assert "yang_ren_jia_sha" in wood["opposing_sources"]
    climate = next(
        layer for layer in profile["layers"] if layer["source"] == "调候简表"
    )
    fire = next(item for item in climate["stems"] if item["stem"] == "丙")
    assert fire["visible_in"] == []
    assert fire["hidden_in"] == ["day", "hour"]
    assert climate["status"] == "reference_only"


@pytest.mark.parametrize("strength", ["强", "中和", "弱"])
def test_strong_label_cannot_make_wood_both_useful_and_avoided(strength):
    # Sensitivity input, not a recalculation or a claim that this chart is strong.
    analysis = ElementAnalysis.comprehensive_analysis(PILLARS)
    analysis["day_master"]["strength_level"] = strength
    analysis["favorable_elements"] = [
        e.value for e in ElementAnalysis.get_favorable_elements(analysis["day_master"])
    ]
    profile = BaZiRules.build_structure_profile(PILLARS, analysis)
    assert not set(profile["useful_elements"]) & set(profile["avoid_elements"])
    assert "木" in profile["conditional_elements"]
    assert "木" not in profile["useful_elements"]
    assert "木" not in profile["avoid_elements"]


@pytest.mark.parametrize(
    "stem,branch", product("甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥")
)
def test_all_day_stem_month_pairs_partition_without_losing_climate(stem, branch):
    pillars = {**PILLARS, "day": (stem, "寅"), "month": ("戊", branch)}
    profile = BaZiRules.chart_useful_profile(pillars)
    groups = [
        set(profile[key])
        for key in [
            "useful_elements",
            "avoid_elements",
            "conditional_elements",
            "neutral_elements",
        ]
    ]
    assert set.union(*groups) == {e.value for e in Element}
    assert sum(map(len, groups)) == 5
    climate = seasonal_climate_god(stem, branch)
    for climate_stem in [climate["primary"], *climate["secondary"]]:
        assert STEM_ELEMENTS[climate_stem][0].value not in profile["avoid_elements"]


def test_specialties_share_resolver_without_complement_avoidance():
    from fatebridge.analysis.career import CareerAnalysis
    from fatebridge.analysis.education import EducationAnalysis

    career = CareerAnalysis._analyze_industries(PILLARS, "壬", Element.WATER)
    assert set(career["favorable_elements"]) == {"土", "金"}
    assert career["avoid_industries"] == []
    education = EducationAnalysis._analyze_subjects(
        PILLARS, "壬", {"seal_weight": 1, "food_hurt_weight": 1, "officer_weight": 1}
    )
    assert set(education["conditional_elements"]) == {"木", "火"}


def test_birth_evidence_and_layers_match_rest_mcp_cli(capsys, monkeypatch):
    import fatebridge.api as api
    from fatebridge.cli import run
    from tests.fixtures.transports import mcp_text

    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    controls = {
        "fields": ["bazi_birth.day_master", "bazi_birth.structure_profile"],
        "include_snapshot_text": False,
        "strict_fields": True,
    }
    response = TestClient(api.app).post(
        "/api/cn/bazi/birth", json=BIRTH, params=controls
    )
    assert response.status_code == 200, response.text
    mcp = json.loads(mcp_text("bazi_birth", **BIRTH, **controls))
    args = ["bazi_birth"]
    for key, value in BIRTH.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args += [
        "--no-include-snapshot-text",
        "--strict-fields",
        "--fields",
        *controls["fields"],
    ]
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    assert response.json()["bazi_birth"] == mcp["bazi_birth"] == cli["bazi_birth"]
    assert (
        cli["bazi_birth"]["day_master"]["assessment"]["status"] == "boundary_sensitive"
    )

"""Source conditions and current program observations remain separate."""

import json
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.analysis.children import ChildrenAnalysis
from fatebridge.analysis.education import EducationAnalysis
from fatebridge.analysis.relatives import RelativesAnalysis
from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_topic_knowledge_v2"
BEFORE = FIXTURE / "before"
REVIEWED_EDITION = ROOT / "tests/fixtures/bazi_current_collation_v1/before"
TARGETS = {
    "education": [
        "印星主学历",
        "官印相生",
        "食伤主才华",
        "文昌贵人",
        "财破印",
        "伤官见官",
    ],
    "children": ["子女星", "子女宫", "时柱十神看子女", "生育时机"],
    "relatives": ["六亲取象", "六亲宫位", "比劫论手足"],
    "shensha": ["文昌"],
}
PARTIAL = {
    "education/文昌贵人",
    "shensha/文昌",
    "children/子女星",
    "relatives/六亲取象",
}
CASES = [(c, k) for c, keys in TARGETS.items() for k in keys]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return json.loads(path.read_text())


def test_fourteen_declared_revisions_preserve_every_other_entry_and_all_old_gates():
    protocol, scope = frozen("protocol.json"), frozen("scope-addendum.json")
    review, notes = frozen("review.json"), frozen("source-review.json")
    assert protocol["targets"] == {k: v for k, v in TARGETS.items() if k != "shensha"}
    assert scope["targets"] == TARGETS and scope["all_targets"] == 14
    assert scope["original_protocol_sha256"] == digest(FIXTURE / "protocol.json")
    assert review["protocol_sha256"] == digest(FIXTURE / "protocol.json")
    assert review["source_review_sha256"] == digest(FIXTURE / "source-review.json")
    assert review["scope_addendum_sha256"] == digest(FIXTURE / "scope-addendum.json")
    assert notes["new_chart_cases"] == notes["new_body_strength_labels"] == 0
    assert not notes["source_adoption_gates_changed"]
    bundle = Path("src/fatebridge/data/knowledge/bazi.json")
    # This frozen fourteen-card review binds its exact 82-card after-edition.
    # A later functional-root revision has its own complete 81-card preservation
    # guard in test_bazi_current_collation_knowledge.py.
    path = REVIEWED_EDITION / bundle
    before_path = BEFORE / bundle
    assert digest(before_path) == review["previous_bundle_sha256"]
    assert digest(path) == review["current_bundle_sha256"]
    before, current = json.loads(before_path.read_text()), json.loads(path.read_text())
    changed = []
    preserved = []
    for category, entries in before["categories"].items():
        assert set(entries) == set(current["categories"][category])
        for key, value in entries.items():
            if value != current["categories"][category][key]:
                changed.append((category, key))
            else:
                preserved.append((category, key))
    assert set(changed) == set(CASES)
    assert len(preserved) == review["preexisting_entries_unchanged"] == 68
    prior = json.loads(
        (BEFORE / "tests/fixtures/bazi_knowledge_curation_v1/ledger.json").read_text()
    )
    assert sum(map(len, prior["curated_keys"].values())) == 38
    assert all(
        (c, k) in preserved for c, keys in prior["curated_keys"].items() for k in keys
    )
    assert review["accuracy_score"] is None
    assert review["new_model_executions"] == review["new_independent_chart_cases"] == 0
    assert not review["production_numerical_policy_changed"]
    assert not review["original_source_strength_labels_changed"]
    assert not review["adoption_gates_changed"]
    assert review["reality_prediction_efficacy"] == "not_tested"


def test_historical_pending_counts_follow_named_collations_without_certifying_the_72():
    old = json.loads(
        (BEFORE / "tests/fixtures/bazi_knowledge_curation_v1/ledger.json").read_text()
    )
    current = json.loads(
        (
            REVIEWED_EDITION / "tests/fixtures/bazi_knowledge_curation_v1/ledger.json"
        ).read_text()
    )
    review = frozen("review.json")
    assert len(review["selected_source_collated_from_original_pending"]) == 10
    assert set(review["partial_topic_attribution_still_pending"]) == PARTIAL
    assert (
        current["source_attribution_pending_original_entries"]
        == old["source_attribution_pending_original_entries"] - 10
        == 40
    )
    assert (
        current["remaining_legacy_entries"]
        == old["remaining_legacy_entries"] - 14
        == 30
    )
    assert (
        current["health_source_attribution_pending_entries"]
        == old["health_source_attribution_pending_entries"]
        == 6
    )
    assert current["topic_partial_attribution_pending_entries"] == 4
    assert (
        current["curated_total"]
        == sum(map(len, current["curated_keys"].values()))
        == 52
    )
    assert old["current_total"] == 82
    assert current["current_total"] == old["current_total"] == 82
    assert (
        current["independent_expert_acceptance"] == old["independent_expert_acceptance"]
    )
    assert current["independent_expert_acceptance"].startswith("not_completed_for_any")
    index = Path("src/fatebridge/data/knowledge/index.json")
    # The collation snapshot stores only its changed bundle and ledger. Its
    # unchanged index is retained in the next source-contrast preimage.
    index_edition = ROOT / "docs/validation/bazi-source-contrast-knowledge-v1/before"
    assert digest(index_edition / index) == digest(BEFORE / index)


@pytest.mark.parametrize("category,key", CASES)
def test_each_public_entry_attributes_only_its_declared_statements(category, key):
    result = calculate_knowledge_read(domain="bazi", category=category, key=key)
    entry = result["provenance"]["entry_curation"]
    assert (
        entry["validation_status"]
        == "topic_source_semantics_not_global_force_or_real_prediction"
    )
    assert entry["source_attribution_status"] == (
        "partial_still_pending"
        if f"{category}/{key}" in PARTIAL
        else "selected_source_conditions_collated"
    )
    indices = sum(
        [
            entry[k]
            for k in (
                "source_tip_indices",
                "implementation_tip_indices",
                "editorial_tip_indices",
                "source_pending_tip_indices",
            )
        ],
        [],
    )
    assert sorted(indices) == list(range(len(result["tips"])))
    assert bool(entry["source_pending_tip_indices"]) == (f"{category}/{key}" in PARTIAL)
    assert "非逐字引文" in result["citation"]
    for source in entry["source_refs"]:
        assert (
            source["source_sha256"]
            == "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
        )
        assert source["source_pdf_pages"]
        assert source["source_url"] in result["snapshot_text"]
    for implementation in entry["implementation_refs"]:
        assert (
            digest(ROOT / implementation["source_path"])
            == implementation["source_sha256"]
        )
        assert implementation["source_path"] in result["snapshot_text"]
    assert entry["independent_expert_review"] == "not_completed"
    assert entry["reality_prediction_efficacy"] == "not_tested"


def test_sealed_revisions_are_reproducible_without_current_services_or_calculation():
    # The standalone editorial script consumes only its declared old files and
    # the frozen review. No current calculator or network access supplies text.
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copytree(BEFORE, root, dirs_exist_ok=True)
        fixture = root / "tests/fixtures/bazi_topic_knowledge_v2"
        fixture.mkdir(parents=True, exist_ok=True)
        for name in (
            "protocol.json",
            "scope-addendum.json",
            "source-review.json",
            "curate.py.txt",
        ):
            shutil.copy2(FIXTURE / name, fixture / name)
        subprocess.run(
            [sys.executable, str(fixture / "curate.py.txt")],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        for name in (
            "src/fatebridge/data/knowledge/bazi.json",
            "tests/fixtures/bazi_knowledge_curation_v1/ledger.json",
            "tests/fixtures/bazi_topic_knowledge_v2/review.json",
        ):
            # The sealed generator reproduces its old 82-card edition. The
            # later one-card revision and ledger fingerprint are separately
            # checked against every entry of this exact retained edition.
            edition = (
                REVIEWED_EDITION
                if name
                in {
                    "src/fatebridge/data/knowledge/bazi.json",
                    "tests/fixtures/bazi_knowledge_curation_v1/ledger.json",
                }
                else ROOT
            )
            assert (root / name).read_bytes() == (edition / name).read_bytes()


def test_wenchang_cards_match_each_other_and_the_day_only_counterexample():
    first = calculate_knowledge_read(
        domain="bazi", category="education", key="文昌贵人"
    )
    duplicate = calculate_knowledge_read(domain="bazi", category="shensha", key="文昌")
    assert first["tips"] == duplicate["tips"]
    # All four pairs satisfy stem/branch parity and the month/hour formula.
    # A year-stem lookup would hit 巳, while actual 辛-day lookup has no 子.
    pillars = {
        "year": ("甲", "午"),
        "month": ("己", "巳"),
        "day": ("辛", "酉"),
        "hour": ("戊", "戌"),
    }
    result = EducationAnalysis.analyze_education(pillars)
    assert result["wenchang"]["wenchang_branch"] == "子"
    assert result["wenchang"]["hit_pillars"] == []
    assert result["wenchang"]["has_wenchang"] is False
    assert (
        "只按日干" in first["rendered_text"]
        and "不同时按年干另算" in first["rendered_text"]
    )
    assert "待校勘" in first["rendered_text"]


def test_repeated_wenchang_positions_are_retained_without_exam_prediction():
    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "子"),
        "day": ("辛", "酉"),
        "hour": ("戊", "子"),
    }
    result = EducationAnalysis.analyze_education(pillars)
    assert result["wenchang"]["hit_pillars"] == ["year", "month", "hour"]
    assert (
        result["education_level"]["assessment_status"]
        == "counts_only_not_education_prediction"
    )
    assert result["education_level"]["score_kind"] == "uncalibrated_rule_index"


@pytest.mark.parametrize(
    "gender,label,weight",
    [("男", "官杀", 2.5), ("女", "食伤", 1.5), (None, "性别未提供", 4.0)],
)
def test_actual_child_counts_gender_basis_and_missing_timing_match_card(
    gender, label, weight
):
    # Synthetic symbolic input; no birth record, source-body label or reality
    # result is assigned. Independent occurrences: 辛+酉辛+酉辛+申庚=2.5;
    # 丁+午丁=1.5. Day stem is never another count.
    pillars = {
        "year": ("辛", "酉"),
        "month": ("丁", "酉"),
        "day": ("甲", "午"),
        "hour": ("壬", "申"),
    }
    result = ChildrenAnalysis.analyze_children(pillars, gender=gender)
    assert label in result["gender_basis"]
    assert result["child_star"]["weight"] == weight
    assert result["relationship"]["hour_ten_god"] == "偏印"
    assert result["children_timing"]["timing_signals"] == [
        "本轮未取得子女星／宫的时间关系，不据此判断生育时机"
    ]
    assert "不是孩子本人测算" in result["interpretation_scope"]
    relatives = RelativesAnalysis.analyze_relatives(pillars, gender=gender)
    assert relatives["parents"]["father_star_weight"] == 0.5
    assert relatives["parents"]["mother_star_weight"] == 0
    assert "未见对应星也不表示亲人缺席" in "".join(relatives["parents"]["notes"])


def test_current_child_timing_is_a_supplied_relation_not_a_fertility_window():
    pillars = {
        "year": ("辛", "酉"),
        "month": ("丁", "酉"),
        "day": ("甲", "午"),
        "hour": ("壬", "申"),
    }
    result = ChildrenAnalysis.analyze_children(
        pillars, gender="男", liunian_pillar=("辛", "巳")
    )
    signals = result["children_timing"]["timing_signals"]
    assert len(signals) == 2
    assert any("引动子女星" in line for line in signals)
    assert any("合子女宫申" in line for line in signals)
    card = calculate_knowledge_read(domain="bazi", category="children", key="生育时机")
    assert "已提供的大运、流年柱" in card["rendered_text"]
    assert "没有计算日级受孕概率" in card["rendered_text"]


def test_source_palace_order_is_disclosed_separately_from_current_module():
    card = calculate_knowledge_read(domain="bazi", category="relatives", key="六亲宫位")
    assert "年、月、日、时分别配祖、父、妻、子" in card["rendered_text"]
    assert "范围不等于上述原典宫分" in card["rendered_text"]
    assert card["provenance"]["entry_curation"]["source_refs"][0][
        "source_pdf_pages"
    ] == [52, 53, 54, 55]

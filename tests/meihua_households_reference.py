"""Preimplementation source decisions and reused independent geometry rows."""

import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_households_v1"
PROFILE = json.loads((FOLDER / "profile.json").read_bytes())
CASES = json.loads((FOLDER / "cases768.json").read_bytes())
EXPECTED = {(r["topic"], r["code"], r["line"]): r for r in CASES}


def resolve(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def assert_candidate_chapter_summary(row):
    clause = row["topic_clause"]
    text = row["traditional_judgement"]
    assert clause["section"] in text
    assert clause["quote"] in text
    assert clause["reading"] in text
    assert row["internal_countercontrol"]["summary"] in text
    assert row["seasonal_qualification"]["summary"] in text
    qualification = clause.get("chapter_qualifications")
    if qualification:
        assert qualification["summary"] in text
    if clause["topic"] == "wealth":
        assert row["wealth_components"]["summary"] in text


def validate(result, topic):
    interpretation = result["interpretation"]
    assert interpretation["interpretation_topic"] == topic
    assert interpretation["topic_ruleset"] == PROFILE
    layers = [
        (
            result["meihua"],
            interpretation,
            interpretation["topic_reading"],
            "meihua",
            result["meihua"]["seed"]["moving_line"],
        )
    ]
    for index, row in enumerate(interpretation["casting_readings"]):
        cast = result["meihua"]["counting_variants"][index]
        layers.append(
            (
                cast,
                row,
                row["topic_clause"],
                f"meihua.counting_variants.{index}",
                cast["moving_line"],
            )
        )
        assert_candidate_chapter_summary(row)
    for cast, layer, clause, prefix, line in layers:
        code = cast["base_hexagram"]["binary_code"]
        expected = EXPECTED[topic, code, line]
        for key in ("body", "use", "relation", "clause_id", "quote"):
            assert clause[key] == expected[key]
        assert clause["comparison_reading"]["quote"] == expected["comparison_quote"]
        assert not clause["comparison_reading"]["used_to_override_selected_edition"]
        assert (
            clause["source_relation_condition"] is expected["source_relation_condition"]
        )
        assert resolve(result, clause["body_fact_path"])["name"] == expected["body"]
        assert resolve(result, clause["use_fact_path"])["name"] == expected["use"]
        assert resolve(result, clause["relation_fact_path"]) == expected["relation"]
        assert clause["quote"] in layer["traditional_judgement"]
        assert clause["reading"] in layer["traditional_judgement"]
        qualification = clause["chapter_qualifications"]
        assert (
            qualification["source_relation_condition"]
            is expected["source_relation_condition"]
        )
        if expected["source_relation_condition"] is None:
            assert (
                clause["source_relation_selection_status"]
                == "unadjudicated_original_relation_term"
            )
            assert "比利" in clause["quote"] and "不能" in clause["reading"]
            assert (
                "same_element_not_automatic_favorable_clause" in clause["semantic_tags"]
            )
        reference = qualification["household_support_reference"]
        if topic == "household":
            assert reference["quote"] == "如有生體之卦即以前章人事占斷之"
            roles = reference["actual_generation_roles"]
            assert [r["role"] for r in roles] == expected["generation_roles"]
            assert reference["raw_generation_condition_in_selected_scope"] is bool(
                roles
            )
            assert reference["full_source_generation_condition"] is None
            assert reference["complete_cross_chapter_synthesis"] is None
            assert reference["net_result"] is None
            for role in roles:
                assert role["trigram_fact_path"].startswith(prefix + ".")
                assert resolve(result, role["trigram_fact_path"]) == role["trigram"]
                assert resolve(result, role["relation_fact_path"]) == "用生体"
        else:
            assert reference is None
        assert not qualification["is_field_fengshui_assessment"]
        for key in (
            "physical_home_inspection",
            "real_residential_safety_verdict",
            "real_financial_outcome",
            "event_time",
            "real_outcome",
        ):
            assert qualification[key] is None
        assert (
            clause["event_time"]
            is clause["success_probability"]
            is clause["real_outcome_verdict"]
            is None
        )

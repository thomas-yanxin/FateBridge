"""Validate current source components before a narrow historical projection.

The original time fixtures remain immutable. This helper is a test adapter,
not an oracle for new calendar or real-world prediction accuracy.
"""

import gzip
import json
from pathlib import Path

from tests.meihua_condition_reference import restore_historical_undetermined_flags
from tests.meihua_strength_reference import strip_volume3_strength_view
from tests.meihua_summary_reference import restore_pre_v44_strength_summaries

FIXTURES = Path(__file__).parent / "fixtures"


def read(relative):
    return json.loads((FIXTURES / relative).read_bytes())


GEOMETRY = {
    (r["code"], r["line"]): r
    for r in read("meihua_trigram_symbols_v1/geometry384.json")
}
TRUTH = read("meihua_condition_logic_v2/truth-table.json")["rows"]
STRENGTH = {
    (r["code"], r["line"], r["month"]): r
    for r in json.loads(
        gzip.decompress(
            (FIXTURES / "meihua_strength_exceptions_v1/expected.json.gz").read_bytes()
        )
    )["cases"]
}
STRENGTH_PROFILE = read("meihua_strength_exceptions_v1/profile.json")
ROLE_TRUTH = read("meihua_strength_exceptions_v1/role-prerequisites.json")["rows"]
SYMBOL_PROFILE = read("meihua_trigram_symbols_v1/profile.json")
VERSES = {
    r["raw_text"]: r for r in read("meihua_text_variants_v1/reference.json")["rows"]
}
TEMPLATE = read("meihua_text_variants_v1/template-source.json")


def resolve(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def assert_current_components(result):
    cast, interpretation = result["meihua"], result["interpretation"]
    assert not interpretation.get("casting_readings")
    code, line = cast["base_hexagram"]["binary_code"], cast["seed"]["moving_line"]
    geometry = GEOMETRY[code, line]
    assert cast["body_trigram"]["name"] == geometry["body"]
    stages = cast["stage_relations"]
    assert [{k: r[k] for k in ["role", "trigram", "relation"]} for r in stages] == [
        {k: r[k] for k in ["role", "trigram", "relation"]} for r in geometry["rows"]
    ]
    assert all(resolve(result, r["fact_path"])["name"] == r["trigram"] for r in stages)
    relations = {r["role"]: r["relation"] for r in geometry["rows"]}
    support = [r for r, relation in relations.items() if relation == "用生体"]
    attack = [r for r, relation in relations.items() if relation == "用克体"]
    structural = [
        relations["use"] == "用生体",
        any(relations[r] == "用生体" for r in ["body_mutual", "use_mutual"]),
        relations["changed_use"] == "用生体",
        bool(support and attack),
        bool(not support and attack),
        bool(support),
        not bool(support),
    ]
    stage = interpretation["stage_emphasis"]
    assert stage["generation_roles"] == support and stage["control_roles"] == attack
    assert stage["scenario_declaration"] is None
    clauses = [
        *stage["relative_generation_clauses"],
        stage["mixed_generation_control"],
        *stage["scenario_clauses"],
    ]
    for clause, condition in zip(clauses, structural, strict=True):
        expected = next(
            r["expected"]
            for r in TRUTH
            if r["structural"] is condition
            and r["scenario_match"] is None
            and r["unresolved"] is False
        )
        assert clause["structural_condition_met"] is condition
        assert clause["scenario_condition_met"] is None
        assert clause["full_clause_applies"] is expected
    timing = stage["obstruction_timing"]
    assert timing["structural_condition_met"] is structural[3]
    assert timing["selected_clause_applies"] is clauses[3]["full_clause_applies"]
    assert timing["scenario_condition_met"] is None
    assert timing["original_body"]["trigram"] == geometry["body"]
    assert [r["role"] for r in timing["attacker_records"]] == attack
    assert timing["activated_day_candidates"] == []
    for r in timing["attacker_records"]:
        assert r["selected_clause_applies"] is timing["selected_clause_applies"]
        assert r["applied_source_day_count"] is None
    assert timing["event_time"] is timing["real_outcome"] is None
    qualification = interpretation["seasonal_qualification"]
    expected = STRENGTH[code, line, qualification["month_branch"]]
    assert [r["strength"] for r in qualification["roles"]] == expected["strengths"]
    volume3 = qualification["volume3_qualification"]
    assert volume3["ruleset"] == STRENGTH_PROFILE
    assert volume3["original_body"] == qualification["roles"][0]
    assert [r["status"] for r in volume3["condition_checks"]] == expected[
        "body_condition_statuses"
    ]
    assert [r["status"] for r in volume3["auxiliary_checks"]] == expected[
        "auxiliary_statuses"
    ]
    rules = {r["id"]: r for r in STRENGTH_PROFILE["rules"]}
    for r in volume3["condition_checks"]:
        assert r["quote"] == rules[r["rule_id"]]["quote"]
        assert resolve(result, r["body_fact_path"])["name"] == geometry["body"]
        assert (
            resolve(result, r["body_strength_fact_path"])
            == qualification["roles"][0]["strength"]
        )
    for r, frozen in zip(volume3["auxiliary_checks"], geometry["rows"], strict=True):
        assert (r["role"], r["trigram"], r["relation_to_body"]) == (
            frozen["role"],
            frozen["trigram"],
            frozen["relation"],
        )
        assert resolve(result, r["fact_path"])["name"] == r["trigram"]
        assert resolve(result, r["strength_fact_path"]) == r["strength"]
        assert r["quote"] == rules[r["rule_id"]]["quote"]
        truth = next(
            t
            for t in ROLE_TRUTH
            if t["strength"] == r["strength"]
            and t["attacking"] is (frozen["relation"] == "用克体")
        )
        for key in ["favorable_clause_applies", "attacker_wang_exception_applies"]:
            assert r[key] is truth[key]
        assert r["effect_after_all_controls"] is None
    for key in ["net_verdict", "event_time", "real_outcome", "success_probability"]:
        assert volume3[key] is None
    symbols = interpretation["trigram_relation_symbols"]
    assert symbols["ruleset"] == SYMBOL_PROFILE
    assert symbols["ruleset_id"] == SYMBOL_PROFILE["id"]
    assert symbols["version"] == SYMBOL_PROFILE["version"]
    assert symbols["counting_candidates"] == []
    selected = symbols["selected"]
    assert selected["body"] == geometry["body"]
    assert resolve(result, selected["body_fact_path"]) == geometry["body"]
    symbol_rules = {r["id"]: r for r in SYMBOL_PROFILE["rules"]}
    for actual, frozen in zip(
        selected["role_evaluations"], geometry["rows"], strict=True
    ):
        assert {k: actual[k] for k in ["role", "trigram", "relation"]} == {
            k: frozen[k] for k in ["role", "trigram", "relation"]
        }
        clause_id = frozen["expected_clause_id"]
        assert actual["clause_id"] == clause_id
        assert actual["quote"] == (
            symbol_rules[clause_id]["quote"] if clause_id else None
        )
        for path, value in [
            ("body_fact_path", geometry["body"]),
            ("trigram_fact_path", frozen["trigram"]),
            ("relation_fact_path", frozen["relation"]),
        ]:
            assert resolve(result, actual[path]) == value
        assert actual["internal_control_qualification"] == resolve(
            result, actual["control_fact_path"]
        )
        assert actual["strength"] == resolve(result, actual["strength_fact_path"])
    assert selected["matched_clause_ids"] == [
        r["expected_clause_id"] for r in geometry["rows"] if r["expected_clause_id"]
    ]
    for key in ["net_verdict", "event_time", "success_probability"]:
        assert selected[key] is None

    def check_verse(value):
        if isinstance(value, list):
            for item in value:
                check_verse(item)
        elif isinstance(value, dict):
            for key, original in [
                ("classical_yaoci_rendering", "classical_yaoci"),
                ("moving_yaoci_rendering", "moving_yaoci"),
            ]:
                if key not in value:
                    continue
                rendering, raw = value[key], value[original]["text"]
                assert raw in VERSES
                assert rendering["raw_text"] == raw
                assert rendering["display_text"] == VERSES[raw]["expected_display_text"]
                assert rendering["ruleset_id"] == "meihua_wikisource_variant_inline_v1"
                assert rendering["version"] == "1.0.0"
                assert (
                    rendering["template_wikitext_sha256"] == TEMPLATE["wikitext_sha256"]
                )
                assert rendering["status"] == "rendered_literal_transcription"
                assert rendering["critical_edition_adjudicated"] is False
            for item in value.values():
                check_verse(item)

    check_verse(interpretation)


def restore_old_time_fixture_view(result):
    from tests.meihua_clock_evolution_reference import restore_clock_before_partial

    try:
        result = restore_clock_before_partial(result)
    except ValueError as error:
        raise AssertionError(str(error)) from error
    assert_current_components(result)
    result = restore_historical_undetermined_flags(
        strip_volume3_strength_view(restore_pre_v44_strength_summaries(result))
    )
    result["interpretation"].pop("trigram_relation_symbols")
    return result

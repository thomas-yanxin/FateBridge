"""Frozen selected wording and independent role/control arithmetic, before code."""

import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_dining_v1"
PROFILE = json.loads((FOLDER / "profile.json").read_bytes())
GEOMETRY = json.loads((FOLDER / "geometry384-expected.json").read_bytes())
EXPECTED = {(r["code"], r["line"]): r for r in GEOMETRY}
CASES = json.loads((FOLDER / "cases4992.json").read_bytes())


def resolve(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def validate_layer(result, cast, layer, clause, prefix, line):
    expected = EXPECTED[cast["base_hexagram"]["binary_code"], line]
    for key in ["body", "use", "relation", "clause_id", "quote"]:
        assert clause[key] == expected[key]
    for key, field in [("body", "body_fact_path"), ("use", "use_fact_path")]:
        assert resolve(result, clause[field])["name"] == expected[key]
    assert resolve(result, clause["relation_fact_path"]) == expected["relation"]
    assert (
        clause["quote"] in layer["traditional_judgement"]
        and clause["reading"] in layer["traditional_judgement"]
    )
    q = clause["chapter_qualifications"]
    assert q["summary"] in layer["traditional_judgement"]
    assert [(r["role"], r["trigram"]) for r in q["actual_five_roles"]] == [
        (r["role"], r["trigram"]) for r in expected["roles"]
    ]
    for row in q["actual_five_roles"]:
        assert (
            row["fact_path"].startswith(prefix + ".")
            and resolve(result, row["fact_path"])["name"] == row["trigram"]
        )
    assert [
        {k: r[k] for k in ["hexagram", "position", "trigram"]}
        for r in q["actual_six_positions"]
    ] == expected["six_positions"]
    for row in q["actual_six_positions"]:
        assert resolve(result, row["fact_path"]) == row["trigram"]
    assert (
        q["presence_equal_under_five_roles_and_six_positions"] is True
        and q["role_occurrences_used_as_outcome_votes"] is False
    )
    for symbol in q["symbols"]:
        ref = expected["symbols"][symbol["symbol"]]
        assert symbol["symbol_present_in_selected_scope"] is ref["present"]
        assert symbol["qualified_symbol_status"] == ref["status"]
        assert (
            symbol["direct_control_condition_in_selected_scope"]
            is ref["direct_control_condition"]
        )
        assert [r["role"] for r in symbol["actual_matching_roles"]] == ref[
            "matching_roles"
        ]
        pairs = symbol["actual_direct_controller_pairs"]
        actual = [
            (
                r["target_role"],
                r["controller_role"],
                tuple(r["controller_itself_controlled_by_roles"]),
            )
            for r in pairs
        ]
        want = [
            (
                r["target_role"],
                r["controller_role"],
                tuple(r["controller_itself_controlled_by_roles"]),
            )
            for r in ref["controller_pairs"]
        ]
        assert len(actual) == len(set(actual)) == len(want) and set(actual) == set(want)
        for row in symbol["actual_matching_roles"]:
            assert resolve(result, row["trigram_fact_path"]) == symbol["trigram"]
        for row in pairs:
            assert row["target_fact_path"].startswith(prefix + ".") and row[
                "controller_fact_path"
            ].startswith(prefix + ".")
            assert (
                resolve(result, row["target_fact_path"])
                == row["target_trigram"]
                == symbol["trigram"]
            )
            assert (
                resolve(result, row["controller_fact_path"])
                == row["controller_trigram"]
            )
            edge = resolve(result, row["control_edge_fact_path"])
            assert (
                edge["controller_role"] == row["controller_role"]
                and edge["target_role"] == row["target_role"]
            )
            assert (
                edge["controller_itself_controlled_by_roles"]
                == row["controller_itself_controlled_by_roles"]
            )
        assert symbol["many_threshold_required_by_selected_control_sentence"] is False
        assert (
            symbol["seasonal_strength_used_to_disable_direct_control"] is False
            and symbol["recursive_cancellation_applied"] is False
        )
        assert (
            symbol["complete_internal_external_control_assessment"]
            is symbol["real_food_or_drink_available"]
            is None
        )
        rule = next(
            r for r in PROFILE["symbol_clauses"] if r["symbol"] == symbol["symbol"]
        )
        for key in [
            "quote",
            "control_quote",
            "controller_trigrams",
            "control_section",
            "control_pdf_index",
        ]:
            assert symbol[key] == rule[key]
    assert (
        q["absence_reference"]["neither_symbol_present_in_selected_scope"]
        is expected["neither_symbol_present"]
    )
    assert q["absence_reference"]["real_food_and_drink_absence"] is None
    generation = q["generation_reference"]
    assert generation["quote"] == "兌坎生身酒肉醉飽"
    assert generation["comparison_quote"] == "兌、坎生體，酒肉醉飽"
    assert generation["source_target_as_original_body_adjudicated"] is False
    assert (
        generation["source_target_binding"]
        is generation["full_source_clause_applies"]
        is generation["real_satiety_or_intoxication"]
        is None
    )
    assert generation["both_named_elements_generate_one_same_body_element"] is False
    assert generation["junction_semantics"] == "not_adjudicated"
    for atom in generation["named_generation_atoms"]:
        assert [
            r["role"] for r in atom["actual_generating_auxiliary_roles"]
        ] == expected["generation_roles"][atom["trigram"]]
        for row in atom["actual_generating_auxiliary_roles"]:
            assert (
                resolve(result, row["trigram_fact_path"]) == atom["trigram"]
                and resolve(result, row["relation_fact_path"]) == "用生体"
            )
    food = q["food_and_people_references"]
    assert (
        food["source_note"] == "飲食八事類者即前八卦內萬物屬類是也"
        and not food["source_note_term_emended"]
    )
    assert [r["role"] for r in food["actual_mutual_roles"]] == [
        "body_mutual",
        "use_mutual",
    ]
    for row in food["actual_mutual_roles"]:
        assert resolve(result, row["fact_path"])["name"] == row["trigram"]
    for name in [
        "selected_food_role",
        "selected_attendee_mutual_side",
        "actual_menu",
        "actual_attendees",
    ]:
        assert food[name] is None
    for name in [
        "net_result",
        "alcohol_consumption_or_dietary_advice",
        "event_time",
        "real_outcome",
    ]:
        assert q[name] is None
    assert (
        clause["event_time"]
        is clause["success_probability"]
        is clause["real_outcome_verdict"]
        is None
    )


def validate(result):
    i = result["interpretation"]
    assert i["interpretation_topic"] == "dining" and i["topic_ruleset"] == PROFILE
    cast = result["meihua"]
    validate_layer(
        result, cast, i, i["topic_reading"], "meihua", cast["seed"]["moving_line"]
    )
    for index, row in enumerate(i["casting_readings"]):
        variant = cast["counting_variants"][index]
        validate_layer(
            result,
            variant,
            row,
            row["topic_clause"],
            f"meihua.counting_variants.{index}",
            variant["moving_line"],
        )

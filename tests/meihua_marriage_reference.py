"""Preimplementation selected text and independent arithmetic on reused geometry."""

import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_marriage_v1"
PROFILE = json.loads((FOLDER / "profile.json").read_bytes())
CASES = json.loads((FOLDER / "cases4992.json").read_bytes())
EXPECTED = {(r["code"], r["line"], r["month"]): r for r in CASES}


def resolve(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def check_layer(result, cast, layer, clause, prefix, line, month):
    expected = EXPECTED[cast["base_hexagram"]["binary_code"], line, month]
    for k in ["body", "use", "relation", "clause_id", "quote"]:
        assert clause[k] == expected[k]
    for k, field in [("body", "body_fact_path"), ("use", "use_fact_path")]:
        assert resolve(result, clause[field])["name"] == expected[k]
    assert resolve(result, clause["relation_fact_path"]) == expected["relation"]
    assert (
        clause["quote"] in layer["traditional_judgement"]
        and clause["reading"] in layer["traditional_judgement"]
    )
    q = clause["chapter_qualifications"]
    assert q["summary"] in layer["traditional_judgement"]
    frame = q["family_frame"]
    assert [x["role"] for x in frame["actual_roles"]] == ["body", "use"]
    assert [x["source_family_role"] for x in frame["actual_roles"]] == [
        "所占之家",
        "所婚之家",
    ]
    for row in frame["actual_roles"]:
        assert row["trigram"] == expected[row["role"]]
        assert resolve(result, row["fact_path"])["name"] == row["trigram"]
        assert row["actual_person_or_gender_assignment"] is None
    for row in q["strength_clauses"]:
        role = row["role"]
        assert row["actual_strength"] == expected[role + "_strength"]
        assert row["wang_condition"] is expected[role + "_wang_condition"]
        status = (
            "condition_met"
            if row["wang_condition"] is True
            else (
                "condition_not_met"
                if row["wang_condition"] is False
                else "pending_known_strength"
            )
        )
        assert row["status"] == status
        assert row["trigram"] == expected[role] and row["trigram_fact_path"].startswith(
            prefix + "."
        )
        if row["strength_fact_path"] is not None:
            assert resolve(result, row["strength_fact_path"]) == row["actual_strength"]
        assert row["actual_household_wealth_or_status"] is None
    for atom in q["generation_relation_atoms"]:
        relation = atom["relation_atom"]
        assert atom["initial_pair_relation"] == expected["relation"]
        assert atom["initial_pair_atom_present"] is (expected["relation"] == relation)
        assert (
            resolve(result, atom["initial_pair_relation_fact_path"])
            == expected["relation"]
        )
        roles = atom["actual_matching_auxiliary_roles"]
        assert [x["role"] for x in roles] == expected["generation_roles"][relation]
        assert atom["atom_present_in_four_auxiliary_roles"] is bool(roles)
        assert (
            atom["full_source_clause_applies"]
            is atom["real_wealth_dowry_or_proposal_intent"]
            is None
        )
        assert (
            not atom["alternatives_combined_as_conjunction"]
            and atom["junction"] == "或"
        )
        for row in roles:
            assert row["trigram_fact_path"].startswith(prefix + ".")
            assert resolve(result, row["trigram_fact_path"]) == row["trigram"]
            assert resolve(result, row["relation_fact_path"]) == relation
    bili = q["bili_supplement"]
    assert bili["quote"] == "若體用比利則彼此相就良配無疑"
    assert bili["comparison_quote"] == "若體用比和，則彼此相就，良配無疑"
    assert bili["initial_same_element"] is (expected["relation"] == "体用比和")
    assert (
        bili["source_relation_condition"] is bili["full_source_clause_applies"] is None
    )
    assert not bili["automatic_same_element_supplement"]
    traits = q["unapplied_historical_person_descriptions"]
    assert traits == PROFILE["unapplied_historical_person_descriptions"]
    assert (
        len(traits["entries"]) == 8
        and not traits["automatic_appearance_character_or_ethnicity_inference"]
    )
    for name in [
        "full_stage_strength_synthesis",
        "net_result",
        "actual_partner_traits",
        "actual_family_wealth",
        "real_marriage_or_consent_verdict",
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


def validate(result, month=None):
    interpretation = result["interpretation"]
    assert interpretation["topic_ruleset"] == PROFILE
    assert interpretation["interpretation_topic"] == "marriage"
    cast = result["meihua"]
    check_layer(
        result,
        cast,
        interpretation,
        interpretation["topic_reading"],
        "meihua",
        cast["seed"]["moving_line"],
        month,
    )
    for index, row in enumerate(interpretation["casting_readings"]):
        variant = cast["counting_variants"][index]
        check_layer(
            result,
            variant,
            row,
            row["topic_clause"],
            f"meihua.counting_variants.{index}",
            variant["moving_line"],
            month,
        )

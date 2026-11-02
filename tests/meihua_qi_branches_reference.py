"""Frozen literal unit atoms and a narrow additive-view history adapter."""

import json
from copy import deepcopy
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_qi_branches_v1"
PROFILE = json.loads((FOLDER / "profile.json").read_bytes())
GEOMETRY = {
    (r["code"], r["line"]): r
    for r in json.loads((FOLDER / "geometry384.json").read_bytes())
}
TRUTH = {
    (r["trigram"], r["unit"], r["branch"]): r["literal_named_unit_branch_atom_met"]
    for r in json.loads((FOLDER / "unit-atoms384.json").read_bytes())
}
UNITS = ("year", "month", "day", "hour")


def resolve(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def validate_branch_node(
    result, layer, node, *, prefix="meihua", layer_path="interpretation"
):
    cast = resolve(result, prefix)
    code = cast["base_hexagram"]["binary_code"]
    line = cast["seed"]["moving_line"] if prefix == "meihua" else cast["moving_line"]
    geometry = GEOMETRY[code, line]
    assert node["ruleset"] == PROFILE
    assert (node["ruleset_id"], node["version"]) == (PROFILE["id"], PROFILE["version"])
    assert node["topic"] in {"wealth", "reputation"}
    labels = node["input_unit_labels"]
    assert list(labels) == list(UNITS)
    seed = result["meihua"]["seed"]
    params = seed.get("parameters", {})
    lunar_added = params.get("method") == "lunar_time_added_count"
    year = params["year_branch"] if lunar_added else seed.get("year_branch")
    month = params["lunar_month"] if lunar_added else seed.get("lunar_month")
    hour = seed.get("hour_branch")
    seasonal = result["meihua"].get("seasonal_strength")
    expected = {
        "year": [("original_lunar_year", year)] if year else [],
        "month": [],
        "day": [],
        "hour": [("original_hour", hour)] if hour else [],
    }
    if seasonal is not None:
        expected["month"].append(("seasonal_jie_month", seasonal["month_branch"]))
    if month is not None:
        expected["month"].append(
            ("nominal_lunar_month", PROFILE["nominal_month_labels"][str(month)])
        )
    day = layer.get("day_qi")
    if day is not None:
        expected["day"] = [
            (r["calendar"]["id"], r["calendar"]["day_branch"])
            for r in day["calendar_candidates"]
        ]
    for unit in UNITS:
        assert [(r["id"], r["branch"]) for r in labels[unit]] == expected[unit]
        for label in labels[unit]:
            assert resolve(result, label["branch_fact_path"]) == label["branch"]
            if label["id"] == "nominal_lunar_month":
                assert (
                    label["nominal_lunar_month"]
                    == resolve(result, label["nominal_lunar_month_fact_path"])
                    == month
                )
                assert label["mapping_source"] == PROFILE["nominal_month_label_source"]
                assert not label["uniquely_selected_for_source_timing"]
                assert label["is_leap_month"] is result["meihua"][
                    "calendar_policy"
                ].get("is_leap_month")
        assert node["input_label_branch_disagreement"][unit] is (
            len({r[1] for r in expected[unit]}) > 1
        )
        assert node["input_unit_status"][unit] == (
            "labels_available_separate_bases" if expected[unit] else "not_collected"
        )
    targets = []
    for selector, relation in (
        [("wealth_gain", "用生体"), ("wealth_loss", "用克体")]
        if node["topic"] == "wealth"
        else [("reputation_completion", "用生体"), ("reputation_office", "用克体")]
    ):
        targets += [
            (selector, r["role"], r["trigram"], relation)
            for r in geometry["rows"]
            if r["relation"] == relation
        ]
    if node["topic"] == "reputation" and not any(
        r["relation"] == "用克体" for r in geometry["rows"]
    ):
        targets.append(
            ("reputation_body_without_attacker", "body", geometry["body"], "body_self")
        )
    actual = node["source_selected_role_references"]
    assert [
        (r["selector_id"], r["role"], r["trigram"], r["relation_to_original_body"])
        for r in actual
    ] == targets
    context = (
        (result.get("input_normalized") or result.get("analysis_context"))[
            "reputation_context"
        ]
        if "reputation_context"
        in (result.get("input_normalized") or result.get("analysis_context"))
        else None
    )
    for row in actual:
        assert row["source_rule"] == PROFILE["chapter_selectors"][row["selector_id"]]
        assert (
            row["literal_unit_branch_atom"]
            == PROFILE["unit_branch_atoms"][row["trigram"]]
        )
        assert resolve(result, row["trigram_fact_path"]) == row["trigram"]
        condition = (
            (context or {}).get("currently_in_office")
            if row["selector_id"] == "reputation_office"
            else (
                None
                if row["selector_id"] == "reputation_body_without_attacker"
                else True
            )
        )
        assert row["selected_source_context_condition"] is condition
        assert not row["full_source_context_authenticated"]
        for unit in UNITS:
            matches = row["input_unit_matches"][unit]
            assert [(m["input_label_id"], m["branch"]) for m in matches] == expected[
                unit
            ]
            for match in matches:
                assert resolve(result, match["branch_fact_path"]) == match["branch"]
                assert (
                    match["literal_named_unit_branch_atom_met"]
                    is TRUTH[row["trigram"], unit, match["branch"]]
                )
                assert (
                    match["full_source_timing_condition"]
                    is match["real_outcome"]
                    is None
                )
            assert row["label_disagreement_changes_literal_match"][unit] is (
                len({m["literal_named_unit_branch_atom_met"] for m in matches}) > 1
            )
        assert row["unknown_units"] == [unit for unit in UNITS if not expected[unit]]
        assert (
            row["combined_units_membership"]
            is row["full_source_timing_condition"]
            is row["event_time"]
            is None
        )
    clause = layer.get("topic_reading") or layer.get("topic_clause")
    day_summary = (clause.get("qi_day_timing_reference") or {}).get("summary", "")
    assert layer["traditional_judgement"].endswith(day_summary + node["summary"])
    assert node["summary"] in result["summary"]
    assert not node["input_year_recast_from_day_alternative"]
    assert not node["source_timing_month_basis_uniquely_adjudicated"]
    assert not node["unit_matches_combined_or_voted"]
    assert not node["nonmembership_negates_full_source_condition"]
    assert (
        node["event_time"]
        is node["real_outcome"]
        is node["candidate_event_dates"]
        is node["real_world_observation_window"]
        is None
    )


def restore_pre_v57_qi_branch_view(result):
    if result["interpretation"]["interpretation_topic"] not in {"wealth", "reputation"}:
        return result
    result = deepcopy(result)
    ir = result["interpretation"]
    main = ir["topic_reading"]["qi_branch_timing_reference"]
    validate_branch_node(result, ir, main)
    suffix = main["summary"]
    for i, row in enumerate(ir.get("casting_readings") or []):
        child = row["topic_clause"]["qi_branch_timing_reference"]
        validate_branch_node(
            result,
            row,
            child,
            prefix=f"meihua.counting_variants.{i}",
            layer_path=f"interpretation.casting_readings.{i}",
        )
        text = child["summary"]
        assert row["traditional_judgement"].endswith(text)
        row["traditional_judgement"] = row["traditional_judgement"][: -len(text)]
        suffix += (
            ("原数" if row["line_sum_basis"] == "raw_counts" else "卦序数")
            + "候选卦气年月日时分列："
            + text
        )
        row["topic_clause"].pop("qi_branch_timing_reference")
    ir["topic_reading"].pop("qi_branch_timing_reference")
    for parent, key, text in [
        (ir, "traditional_judgement", main["summary"]),
        (ir, "comprehensive_judgement", suffix),
        (result, "summary", suffix),
    ]:
        assert parent[key].endswith(text)
        parent[key] = parent[key][: -len(text)]
    return result

"""Compare printed premises and frozen neighbor lists with actual natal facts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.ziwei_conditions import structural_condition_evidence

if TYPE_CHECKING or __package__:
    from .audit_ziwei_limits import _seed
else:
    from audit_ziwei_limits import _seed

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ziwei_independent"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _strict(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def revised_condition_source(
    fixtures: Path = FIXTURES,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a separate erratum to the immutable first collation, never rewrite it."""
    folder = fixtures / "naj_ming_conditions_r25_v2"
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    prior_folder = fixtures / "naj_ming_conditions_r25_v1"
    prior_manifest_path = prior_folder / "manifest.json"
    prior_manifest = json.loads(prior_manifest_path.read_text())
    if (
        manifest["prior_evidence_manifest_sha256"]
        != hashlib.sha256(prior_manifest_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Ming condition evidence predecessor changed")
    for name, digest in prior_manifest["files"].items():
        if hashlib.sha256((prior_folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Ming condition frozen predecessor checksum mismatch")
    image_names = {
        f"naj_{region}_native_region.jpg"
        for region in (
            "0045_left_upper",
            "0045_left_lower",
            "0059_left_upper",
            "0059_left_lower",
            "0059_kuiyue_upper",
            "0059_kuiyue_lower",
        )
    }
    required = image_names | {
        "first_blind_read_frozen.json",
        "naj_native_regions.json",
        "corrections.json",
        "ziwei-r25-conditions-independent-review.json",
        "ziwei-r25-conditions-glyph-peer-review.json",
        "prior-compiled.json",
    }
    if set(manifest["files"]) != required:
        raise ValueError("Ming condition evidence membership changed")
    if _strict(
        {
            k: manifest.get(k)
            for k in (
                "first_reading_frozen_before_peer_or_implementation_feedback",
                "new_target_witnesses",
                "external_human_experts",
                "isolated_model_readers",
            )
        }
    ) != _strict(
        dict(
            first_reading_frozen_before_peer_or_implementation_feedback=True,
            new_target_witnesses=0,
            external_human_experts=0,
            isolated_model_readers=2,
        )
    ):
        raise ValueError(
            "Ming condition independence metadata contradicts frozen scope"
        )
    for name, expected in manifest["files"].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Ming condition rereading checksum mismatch: " + name)
    original = fixtures / "naj_ming_conditions_v1/collation.json"
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    changes = json.loads((folder / "corrections.json").read_text())
    if _strict(changes) != _strict(
        json.loads((prior_folder / "corrections.json").read_text())
    ):
        raise ValueError(
            "Ming condition correction differs from preserved first revision"
        )
    prior_compiled = json.loads((folder / "prior-compiled.json").read_text())
    if (
        changes["prior_compiled_sha256"]
        != hashlib.sha256((folder / "prior-compiled.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Ming condition prior compiled bytes changed")
    if _strict(
        {
            k: changes.get(k)
            for k in (
                "numeric_or_geometric_rule_changes",
                "new_witnesses_for_target_clauses",
                "external_human_experts",
                "isolated_model_readers",
                "whole_book_acceptance_passed",
            )
        }
    ) != _strict(
        dict(
            numeric_or_geometric_rule_changes=False,
            new_witnesses_for_target_clauses=0,
            external_human_experts=0,
            isolated_model_readers=2,
            whole_book_acceptance_passed=False,
        )
    ):
        raise ValueError("Ming condition correction scope contradicts frozen review")
    if not (
        original_hash
        == changes["prior_collation_sha256"]
        == manifest["prior_collation_sha256"]
    ):
        raise ValueError("Ming condition prior collation changed")
    source = json.loads(original.read_text())
    if _strict(prior_compiled["clauses"]) != _strict(source["clauses"]):
        raise ValueError(
            "Ming condition prior compiled clauses differ from original collation"
        )
    first = json.loads((folder / "first_blind_read_frozen.json").read_text())
    peer = json.loads(
        (folder / "ziwei-r25-conditions-glyph-peer-review.json").read_text()
    )
    primary = json.loads(
        (folder / "ziwei-r25-conditions-independent-review.json").read_text()
    )
    regions = json.loads((folder / "naj_native_regions.json").read_text())
    freeze = primary["independence"]["freeze"]
    if (
        freeze["sha256"] != manifest["files"]["first_blind_read_frozen.json"]
        or freeze["preserved_unchanged"] is not True
        or freeze["second_witness_opened_after_freeze"] is not True
        or freeze["frozen_at_utc"] != first["frozen_at_utc"]
    ):
        raise ValueError(
            "Ming condition primary report freeze disagrees with actual bytes"
        )
    if _strict(primary["primary_witness"]["native_evidence"]) != _strict(regions):
        raise ValueError(
            "Ming condition primary report native evidence disagrees with region inventory"
        )
    if len(regions) != 6 or {Path(r["path"]).name for r in regions} != image_names:
        raise ValueError("Ming condition native region membership changed")
    region_by_name = {Path(r["path"]).name: r for r in regions}
    if (
        len(peer["source_images"]) != 6
        or {r["file"] for r in peer["source_images"]} != image_names
    ):
        raise ValueError("Ming condition peer image membership changed")
    for row in peer["source_images"]:
        region = region_by_name[row["file"]]
        if not (
            row["sha256"] == region["sha256"] == manifest["files"][row["file"]]
            and row["bytes"] == region["bytes"] == (folder / row["file"]).stat().st_size
            and row["source_url"] == region["url"]
            and row["source_native_region_xywh"] == region["native_region_xywh"]
            and Path(row["path"]).name == row["file"]
        ):
            raise ValueError("Ming condition peer/native image evidence changed")
    first_rows = {r["id"]: r for r in first["readings"]}
    primary_rows = {r["id"]: r for r in primary["primary_witness"]["readings"]}
    if (
        len(first["readings"]) != 5
        or len(primary["primary_witness"]["readings"]) != 5
        or set(first_rows) != set(primary_rows)
    ):
        raise ValueError("Ming condition first/primary reading targets changed")
    for key, reading in first_rows.items():
        if _strict(reading) != _strict({k: primary_rows[key].get(k) for k in reading}):
            raise ValueError(
                "Ming condition primary text contradicts frozen first reading"
            )
        columns = reading["small_print_columns_right_to_left"]
        if reading["joined_small_print"] != ("".join(columns) if columns else None):
            raise ValueError("Ming condition first reading columns disagree")
    peer_rows = {r["target_id"]: r for r in peer["targets"]}
    for target in peer["targets"]:
        for entry in target.get("entries_in_reading_order", [target]):
            columns = entry["small_note_columns"]
            if [r["read_order"] for r in columns] != list(
                range(1, len(columns) + 1)
            ) or entry["small_note_joined_raw"] != "".join(r["raw"] for r in columns):
                raise ValueError("Ming condition peer reading columns disagree")
            if any(
                row.get("belongs_to_large_text") != entry["large_text_raw"]
                for row in columns
                if "entries_in_reading_order" not in target
                or "belongs_to_large_text" in row
            ):
                raise ValueError(
                    "Ming condition peer annotation ownership contradicts its entry"
                )
    if not (
        peer_rows["ziwei_fubi_same_palace"]["large_text_raw"]
        == first_rows["ziwei_fubi_same_palace"]["main"]
        and peer_rows["zuoyou_flank_ming"]["large_text_raw"]
        == first_rows["zuoyou_flanking"]["main"]
        and peer_rows["kuiyue_flank_ming_and_immediate_next_entry"][
            "entries_in_reading_order"
        ][0]["large_text_raw"]
        == first_rows["kuiyue_flanking"]["main"]
        and peer_rows["kuiyue_flank_ming_and_immediate_next_entry"][
            "entries_in_reading_order"
        ][1]["large_text_raw"]
        == primary["primary_witness"]["adjacent_scope_controls"][-1]["main"]
        and first["source_item"]
        == manifest["source_url"]
        == primary["primary_witness"]["item_url"]
        and changes["id"] == manifest["id"]
    ):
        raise ValueError(
            "Ming condition reading ownership or source identity disagrees"
        )
    independent_readings = {
        "ziwei_fubi_conjunction": [
            first_rows["ziwei_fubi_same_palace"]["joined_small_print"],
            peer_rows["ziwei_fubi_same_palace"]["small_note_joined_raw"],
        ],
        "kuiyue_flank_ming": [
            first_rows["kuiyue_flanking"]["joined_small_print"],
            peer_rows["kuiyue_flank_ming_and_immediate_next_entry"][
                "entries_in_reading_order"
            ][0]["small_note_joined_raw"],
        ],
        "fubi_flank_ming": [
            first_rows["zuoyou_flanking"]["joined_small_print"],
            peer_rows["zuoyou_flank_ming"]["small_note_joined_raw"],
        ],
    }
    if len(changes["changes"]) != 3 or {r["id"] for r in changes["changes"]} != set(
        independent_readings
    ):
        raise ValueError("Ming condition correction targets changed")
    for delta in changes["changes"]:
        clause = next(c for c in source["clauses"] if c["id"] == delta["id"])
        readings = independent_readings[delta["id"]]
        disputed = delta["id"] == "ziwei_fubi_conjunction"
        if not (
            clause["annotation"] == delta["prior_annotation"]
            and clause["unresolved_conditions"] == delta["prior_unresolved_conditions"]
            and delta["reader_annotations"] == readings
            and (readings[0] != readings[1] if disputed else readings[0] == readings[1])
            and delta["annotation"] == (None if disputed else readings[0])
            and delta["status"]
            == (
                "unresolved_after_independent_rereading"
                if disputed
                else "corrected_after_independent_rereading"
            )
        ):
            raise ValueError("Ming condition correction disagrees with frozen readings")
        clause["annotation"] = delta["annotation"]
        clause["unresolved_conditions"] = deepcopy(delta["unresolved_conditions"])
        clause["annotation_revision"] = {
            k: deepcopy(delta[k])
            for k in ("prior_annotation", "reader_annotations", "status", "reason")
        }
    hashes = manifest["files"]
    metadata = dict(
        id=changes["id"],
        source_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        first_reading_sha256=hashes["first_blind_read_frozen.json"],
        primary_review_sha256=hashes["ziwei-r25-conditions-independent-review.json"],
        peer_review_sha256=hashes["ziwei-r25-conditions-glyph-peer-review.json"],
        prior_collation_sha256=original_hash,
        prior_compiled_sha256=changes["prior_compiled_sha256"],
        changed_clause_ids=[c["id"] for c in changes["changes"]],
        isolated_model_readers=2,
        external_human_experts=0,
        new_witnesses=0,
        numeric_or_geometric_rules_modified=False,
        whole_book_acceptance_passed=False,
    )
    source["prior_compiled"] = prior_compiled
    return source, metadata


def audit_conditions(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "naj_ming_conditions_v1"
    for name, expected in json.loads((folder / "checksums.json").read_text()).items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Ming condition source checksum mismatch: " + name)
    source, revision = revised_condition_source(fixtures)
    extension = json.loads((folder / "coverage_extension.json").read_text())
    if (
        extension["original_collation_sha256"]
        != hashlib.sha256((folder / "collation.json").read_bytes()).hexdigest()
        or extension["additional_days"] != list(range(2, 31))
        or not extension["declared_after_implementation"]
    ):
        raise ValueError("Ming condition postimplementation coverage policy mismatch")
    compiled = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-conditions.json"
        ).read_text()
    )
    differences = []
    strict = _strict
    expected_compiled = deepcopy(source["prior_compiled"])
    expected_compiled.update(
        clauses=source["clauses"], version="1.1.0", source_revision=revision
    )
    if strict(compiled) != strict(expected_compiled):
        differences.append(dict(case="production_source_clauses"))
    if (
        strict(compiled.get("source_revision")) != strict(revision)
        or compiled["version"] != "1.1.0"
    ):
        differences.append(dict(case="production_source_revision"))
    examples = 0
    for clause in source["clauses"]:
        example = clause["literal_example"]
        if example is None:
            continue
        positions = example["positions"]
        palaces = [
            dict(
                name="命宫" if b == example["ming"] else "原文条件测试宫",
                ganzhi="甲" + b,
                stars_detail=[
                    dict(name=n, mutagen=None) for n, v in positions.items() if v == b
                ],
            )
            for b in BRANCHES
        ]
        r = next(
            r
            for r in structural_condition_evidence(
                palaces, ming_branch=example["ming"], year_stem="甲"
            )["records"]
            if r["id"] == clause["id"]
        )
        if not (
            r["geometry_match"] is True and r["source_literal_example_matches"] is True
        ):
            differences.append(dict(case="literal_example", id=clause["id"]))
        examples += 1
    charts = checks = joins = 0
    hits: Counter[str] = Counter()
    grid = source["conditional_grid"]
    outcomes: dict[str, set[bool]] = {c["id"]: set() for c in source["clauses"]}
    for day in [grid["day"], *extension["additional_days"]]:
        for profile in ["iztro_2_5_8", "quanshu_v2_excerpt"]:
            for year in grid["years"]:
                for month in grid["months"]:
                    for hour in grid["hours"]:
                        c = build_ziwei_chart(
                            _seed(year, month, day, BRANCHES[hour]),
                            grid["gender"],
                            rule_profile=profile,
                        )
                        e = c["ming_structural_conditions"]
                        ming = c["ming_gong"]["branch"]
                        actual = {
                            s["name"]: (
                                p,
                                s,
                                f"ziwei_birth.palaces.{i}.stars_detail.{j}",
                            )
                            for i, p in enumerate(c["palaces"])
                            for j, s in enumerate(p["stars_detail"])
                        }
                        records = {r["id"]: r for r in e["records"]}
                        index = {r["id"]: r for r in e["index"]}
                        prior = source["prior_compiled"]
                        expected_top = dict(
                            method_id=prior["id"],
                            version="1.1.0",
                            source=prior["source_url"],
                            source_title=prior["title"],
                            source_section=prior["source_section"],
                            source_section_is_editorial_label=True,
                            source_status="independent_rereading_partial_clause_collation",
                            manual_reader_count=prior["manual_reader_count"],
                            source_revision=revision,
                            ming_branch=ming,
                            year_stem=c["year_stem"],
                            adjacent_branches=source["neighbors"][ming],
                            flanking_reading=prior["flanking_reading"],
                            scope=prior["scope"],
                            actual_assignments_modified=False,
                            whole_book_acceptance_passed=False,
                            real_world_efficacy="not_tested",
                        )
                        if strict(
                            {
                                k: v
                                for k, v in e.items()
                                if k not in {"records", "index"}
                            }
                        ) != strict(expected_top):
                            differences.append(
                                dict(
                                    case="runtime_source_metadata",
                                    year=year,
                                    month=month,
                                    hour=hour,
                                    profile=profile,
                                )
                            )
                        expected_ids = [r["id"] for r in source["clauses"]]
                        if [r["id"] for r in e["records"]] != expected_ids or [
                            r["id"] for r in e["index"]
                        ] != expected_ids:
                            differences.append(
                                dict(
                                    case="runtime_record_membership",
                                    year=year,
                                    month=month,
                                    hour=hour,
                                    profile=profile,
                                )
                            )
                        for clause in source["clauses"]:
                            r = records[clause["id"]]
                            branches = [
                                actual[n][0]["ganzhi"][1] for n in clause["stars"]
                            ]
                            if clause["geometry"] == "flank_ming":
                                expected = sorted(branches) == sorted(
                                    source["neighbors"][ming]
                                )
                            elif clause["geometry"] == "same_ming_palace":
                                expected = all(b == ming for b in branches)
                            else:
                                expected = all(b == branches[0] for b in branches)
                            branch_ok = (
                                not clause["branches"] or ming in clause["branches"]
                            )
                            stem_ok = (
                                not clause["year_stems"]
                                or c["year_stem"] in clause["year_stems"]
                            )
                            witnesses = {}
                            for name in clause["stars"]:
                                p, star, path = actual[name]
                                witnesses[name] = [
                                    dict(
                                        star=name,
                                        natal_palace_name=p["name"],
                                        natal_branch=p["ganzhi"][1],
                                        natal_mutagen=star["mutagen"],
                                        calculation_path=path,
                                    )
                                ]
                                joins += 1
                            example = clause["literal_example"]
                            example_match = (
                                None
                                if example is None
                                else (
                                    ming == example["ming"]
                                    and all(
                                        actual[n][0]["ganzhi"][1] == b
                                        for n, b in example["positions"].items()
                                    )
                                )
                            )
                            expected_record = dict(
                                id=clause["id"],
                                source_frame=clause["frame"],
                                source_quote=clause["quote"],
                                source_annotation=clause["annotation"],
                                annotation_revision=clause.get("annotation_revision"),
                                geometry_rule=clause["geometry"],
                                actual_occurrences=witnesses,
                                geometry_match=expected,
                                ming_branch_requirement_met=branch_ok,
                                year_stem_requirement_met=stem_ok,
                                evaluated_necessary_premises_match=bool(
                                    expected and branch_ok and stem_ok
                                ),
                                source_literal_example_matches=example_match,
                                literal_example=example,
                                source_qualifications_not_evaluated=clause[
                                    "unresolved_conditions"
                                ],
                                full_traditional_judgment=None,
                                source_outcome_claim_adopted=False,
                                missing_or_duplicated_stars=[],
                            )
                            expected_index = {
                                k: expected_record[k]
                                for k in (
                                    "id",
                                    "source_frame",
                                    "source_quote",
                                    "geometry_match",
                                    "evaluated_necessary_premises_match",
                                    "source_literal_example_matches",
                                    "source_qualifications_not_evaluated",
                                    "full_traditional_judgment",
                                    "source_outcome_claim_adopted",
                                )
                            }
                            ok = strict(r) == strict(expected_record) and strict(
                                index[clause["id"]]
                            ) == strict(expected_index)
                            if not ok:
                                differences.append(
                                    dict(
                                        case="conditional_chart",
                                        year=year,
                                        month=month,
                                        hour=hour,
                                        profile=profile,
                                        id=clause["id"],
                                    )
                                )
                            hits[clause["id"]] += int(expected)
                            outcomes[clause["id"]].add(
                                bool(expected and branch_ok and stem_ok)
                            )
                            checks += 1
                        charts += 1
    return dict(
        method_id=source["id"],
        source_clauses=len(source["clauses"]),
        literal_placement_examples=examples,
        conditional_chart_inputs=charts,
        premises_checked=checks,
        actual_star_joins_checked=joins,
        derived_geometry_matches=dict(hits),
        evaluated_premise_outcomes={k: sorted(v) for k, v in outcomes.items()},
        original_preimplementation_chart_inputs=1152,
        postimplementation_chart_inputs=charts - 1152,
        postimplementation_coverage_declared=True,
        differences=differences,
        source_manual_readers=source["manual_readers"],
        independent_rereading=revision,
        corrected_annotations=2,
        disputed_annotations=1,
        source_frames=[r["frame"] for r in source["images"]],
        new_independent_editions=0,
        independent_placement_or_calendar_oracle=False,
        full_traditional_judgments_evaluated=0,
        flanking_generalization_independently_adjudicated=False,
        live_model_blind_evaluation="not_run",
        whole_book_acceptance_passed=False,
        scope=source["scope"],
    )

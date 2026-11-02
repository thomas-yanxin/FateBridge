"""Audit selected thematic source clauses and actual candidate fact paths."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _normalized(text: str) -> str:
    return re.sub(r"[\s，。；：、！？「」“”]", "", text)


def _resolve(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def _fact_checks(result: dict[str, Any], clause: dict[str, Any]) -> bool:
    return (
        _resolve(result, clause["body_fact_path"])["name"] == clause["body"]
        and _resolve(result, clause["use_fact_path"])["name"] == clause["use"]
        and _resolve(result, clause["relation_fact_path"]) == clause["relation"]
        and clause["success_probability"]
        is clause["event_time"]
        is clause["real_outcome_verdict"]
        is None
    )


def audit_topic_clauses(directory: Path) -> dict[str, Any]:
    from fatebridge.core.meihua_topics import topic_ruleset
    from fatebridge.services.meihua import calculate_meihua_cast

    manifest = json.loads((directory / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Topic reference escapes frozen bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen topic reference changed")
    source = json.loads((directory / "sources.json").read_text())
    for record in [source["selected_pdf"], source["fixed_transcription"]]:
        path = (directory / record["file"]).resolve()
        if not path.is_relative_to(directory.parent.resolve()):
            raise ValueError("Topic source escapes reference parent")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Frozen topic primary source changed")
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_countercontrol.py",
        "core/meihua_seasonal_reading.py",
        "data/meihua/seasonal-reading-nlc1925-v1.json",
        "data/meihua/internal-control-nlc1925-v1.json",
        "core/meihua_casting.py",
        "core/meihua_topics.py",
        "core/meihua_general_variants.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "services/divination.py",
        "data/meihua/topics-nlc1925-v1.json",
        "validation/meihua_topics.py",
    ]
    hashes = {n: hashlib.sha256((package / n).read_bytes()).hexdigest() for n in names}
    readings = json.loads((directory / "readings.json").read_text())["topics"]
    runtime = topic_ruleset()
    rules = {r["id"]: r for r in runtime["rules"]}
    text = (directory / source["fixed_transcription"]["file"]).read_text()
    chapter_checks = [
        {
            "topic": topic,
            "metadata_matches_selected_reading": all(
                runtime["topics"][topic][key] == chapter[key]
                for key in ["label", "section", "use_role", "pdf_index", "header"]
            ),
        }
        for topic, chapter in readings.items()
    ]
    source_checks = []
    source_metadata_matches = (
        runtime["selected_edition_id"] == "nlc_1925"
        and runtime["source"]["raw_sha256"] == source["selected_pdf"]["sha256"]
        and runtime["comparison_source"]["raw_sha256"]
        == source["fixed_transcription"]["sha256"]
        and runtime["comparison_source"]["revision"] == 1441921
    )
    following_sections = {
        "planning": "求名占第九",
        "reputation": "求財占第十",
        "wealth": "交易占第十一",
        "transaction": "出行占第十二",
    }
    for topic, chapter in readings.items():
        chapter_start = text.index(chapter["section"] + "\n")
        chapter_end = text.index(following_sections[topic] + "\n", chapter_start)
        comparison_chapter = text[chapter_start:chapter_end]
        for expected in chapter["clauses"]:
            row = rules[expected["id"]]
            source_checks.append(
                {
                    "clause_id": expected["id"],
                    "selected_assistant_span_matches": row["quote"]
                    == expected["selected_quote"],
                    "relation_matches": row["relation"] == expected["relation"],
                    "semantic_tags_match": row["semantic_tags"]
                    == expected["semantic_tags"],
                    "delay_scope_matches": row["delay_scope"]
                    == expected["delay_scope"],
                    "comparison_quote_matches": row["comparison_reading"]["quote"]
                    == expected["transcription_quote"],
                    "comparison_quote_found_in_own_transcription": _normalized(
                        expected["transcription_quote"]
                    )
                    in _normalized(comparison_chapter),
                    "edition_contrast_status_matches": row["comparison_reading"][
                        "semantic_status"
                    ]
                    == (
                        "explicit_difference_in_selected_reading"
                        if expected["semantics_differ_from_transcription"]
                        else "not_adjudicated"
                    ),
                }
            )
    cases = []
    for case in json.loads((directory / "cases.json").read_text())["cases"]:
        result = calculate_meihua_cast(
            casting=case["casting"], interpretation_topic=case["topic"]
        )
        cast = result["meihua"]
        clause = result["interpretation"]["topic_reading"]
        expected = {k: case[k] for k in ["body", "use", "relation"]}
        actual = {k: clause[k] for k in expected}
        passed = (
            actual == expected
            and clause["clause_id"] == case["expected_clause_id"]
            and cast["changed_hexagram"]["binary_code"] == case["changed_code"]
            and cast["mutual_hexagram"]["binary_code"] == case["mutual_code"]
            and _fact_checks(result, clause)
        )
        cases.append(
            {
                "id": case["id"],
                "topic": case["topic"],
                "passed": passed,
                "expected": expected,
                "actual": actual,
                "clause_id": clause["clause_id"],
            }
        )
    candidates = []
    for case in json.loads((directory / "variant-cases.json").read_text())["cases"]:
        for topic in readings:
            for selected_basis in ["raw_counts", "trigram_numbers"]:
                result = calculate_meihua_cast(
                    casting={**case["casting"], "line_sum_basis": selected_basis},
                    season_month_branch=case["season_month_branch"],
                    interpretation_topic=topic,
                )
                rows = {
                    r["line_sum_basis"]: r
                    for r in result["interpretation"]["casting_readings"]
                }
                passed = (
                    result["meihua"]["base_hexagram"]["binary_code"]
                    == case["base_code"]
                )
                for expected in case["variants"]:
                    row = rows[expected["basis"]]
                    clause = row["topic_clause"]
                    passed = (
                        passed
                        and all(
                            row[k] == expected[k]
                            for k in ["moving_line", "body", "use", "relation"]
                            if k != "relation"
                        )
                        and clause["relation"] == expected["relation"]
                        and clause["clause_id"]
                        == topic + "_" + expected["clause_suffix"]
                        and _fact_checks(result, clause)
                    )
                    if "changed_use_relation" in expected:
                        passed = (
                            passed
                            and next(
                                s["relation"]
                                for s in row["stage_relations"]
                                if s["role"] == "changed_use"
                            )
                            == expected["changed_use_relation"]
                        )
                    if "body_strength" in expected:
                        passed = (
                            passed
                            and next(
                                s["strength"]
                                for s in row["seasonal_strength"]["trigrams"]
                                if s["role"] == "body"
                            )
                            == expected["body_strength"]
                        )
                    else:
                        passed = passed and row["seasonal_strength"] is None
                selected = next(r for r in rows.values() if r["selected"])
                passed = (
                    passed
                    and result["interpretation"]["topic_reading"]["clause_id"]
                    == selected["topic_clause"]["clause_id"]
                )
                candidates.append(
                    {
                        "id": case["id"],
                        "topic": topic,
                        "selected_basis": selected_basis,
                        "passed": passed,
                        "candidate_clauses": {
                            basis: row["topic_clause"]["clause_id"]
                            for basis, row in rows.items()
                        },
                    }
                )
    if any(
        hashlib.sha256((package / n).read_bytes()).hexdigest() != v
        for n, v in hashes.items()
    ):
        raise ValueError("Source changed during topic audit")
    return {
        "audit_id": "meihua_topics_nlc1925_v1",
        "implementation_sha256": hashes,
        "reference_manifest_sha256": hashlib.sha256(
            (directory / "manifest.json").read_bytes()
        ).hexdigest(),
        "selected_edition_id": "nlc_1925",
        "source_metadata_matches": source_metadata_matches,
        "runtime_clause_count": len(rules),
        "chapter_checks": chapter_checks,
        "source_checks": source_checks,
        "mathematical_cases": cases,
        "retained_cast_checks": candidates,
        "selected_checks_passed": len(rules) == 20
        and source_metadata_matches
        and all(row["metadata_matches_selected_reading"] for row in chapter_checks)
        and all(
            all(v for k, v in row.items() if k != "clause_id") for row in source_checks
        )
        and all(r["passed"] for r in cases + candidates),
        "independent_human_expert_source_review": False,
        "full_chapter_conformance_established": False,
        "exact_event_timing_computed": False,
        "actual_model_runs": 0,
        "real_model_semantic_acceptance": "not_run",
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }

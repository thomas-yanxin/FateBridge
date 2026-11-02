"""Bind complete input files and whole answers without assigning a score."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from fatebridge.validation.sukuyo_engineering import Artifact, _ArtifactReader


def _rows(value: Any, key: str, id_field: str) -> list[dict[str, Any]]:
    rows = value.get(key) if isinstance(value, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"A nonempty {key} list is required")
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"Each {key} entry must be an object")
        identifier = row.get(id_field)
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
            or identifier in ids
        ):
            raise ValueError(f"Distinct nonempty {id_field} values are required")
        ids.add(identifier)
    return rows


def build_whole_answer_review_packet(
    request: Artifact,
    answers: Artifact,
    *,
    id_field: Literal["id", "case_id"] = "id",
) -> dict[str, Any]:
    """Retain all metadata, exact whole input bytes and the complete case set.

    This verifies file and question identity at the time of this read. It does
    not prove when an earlier generator read the files, establish independent
    evidence, verify claims in the files or grade an answer's meaning.
    """
    if id_field not in {"id", "case_id"}:
        raise ValueError("id_field must be id or case_id")
    if request.sha256 == answers.sha256:
        raise ValueError("Request and answers must be separate byte identities")
    reader = _ArtifactReader()
    bound_request = reader.bind_utf8_file(request)
    bound_answers = reader.bind_utf8_file(answers)
    questions = _rows(bound_request["value"], "cases", id_field)
    outputs = _rows(bound_answers["value"], "answers", id_field)
    by_id = {row[id_field]: row for row in outputs}
    if {row[id_field] for row in questions} != set(by_id):
        raise ValueError("Whole request and answer case sets must match exactly")
    items = []
    for row in questions:
        question = row.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Every case requires its exact nonempty whole question")
        output = by_id[row[id_field]]
        if "question" in output and output["question"] != question:
            raise ValueError("An answer's question differs from the exact request")
        text = output.get("answer")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Every case requires a nonempty whole answer")
        items.append(
            {
                id_field: row[id_field],
                "question": question,
                "answer": text,
                "answer_utf8_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        )
    return {
        "format": "sukuyo_whole_answer_review_packet_v1",
        "request": bound_request,
        "answers": bound_answers,
        "id_field": id_field,
        "case_count": len(items),
        "unique_question_count": len({item["question"] for item in items}),
        "request_case_order": [row[id_field] for row in questions],
        "items": items,
        "artifacts": reader.artifacts(),
        "binding_verified": True,
        "whole_request_case_set_retained": True,
        "whole_question_and_answer_texts_retained": True,
        "semantic_verdict": "not_assessed",
        "source_support_of_answer": "not_assessed",
        "source_independence": "not_assessed",
        "original_gate_verdict": "not_assessed",
        "real_world_efficacy": "not_assessed",
        "earlier_reader_behaviour_independently_verified": False,
    }

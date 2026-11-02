"""Bind explicit engineering questions to whole, fingerprinted evidence subtrees.

Offline evidence and whole-answer assembly. Neither file binding nor literal
answer spans grade semantics, authenticate a version, or execute calculations.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str
    source_version: str


@dataclass(frozen=True)
class Selection:
    artifact: Artifact
    pointer: str = ""


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    selections: tuple[Selection, ...] = ()
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class AnswerSpan:
    start: int
    end: int
    quote: str


@dataclass(frozen=True)
class AnswerCoverage:
    requirement_id: str
    spans: tuple[AnswerSpan, ...]


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key in evidence")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite JSON number: {value}")
    return parsed


def _select(value: Any, pointer: str) -> Any:
    if pointer == "":
        return deepcopy(value)
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or start with /")
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise ValueError("Invalid JSON pointer escape")
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[key]
        elif isinstance(value, list):
            if re.fullmatch(r"0|[1-9][0-9]*", key) is None:
                raise ValueError("Invalid JSON array index")
            if int(key) >= len(value):
                raise KeyError(pointer)
            value = value[int(key)]
        else:
            raise KeyError(pointer)
    return deepcopy(value)


class _ArtifactReader:
    def __init__(self) -> None:
        self.cache: dict[Path, tuple[Artifact, Any, int]] = {}
        self.raw_cache: dict[Path, bytes] = {}

    def bind(self, artifact: Artifact, pointer: str = "") -> dict[str, Any]:
        if (
            re.fullmatch(r"[0-9a-f]{64}", artifact.sha256) is None
            or not artifact.source_version.strip()
        ):
            raise ValueError("Artifact SHA and declared source version required")
        path = artifact.path.resolve()
        if path not in self.cache:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != artifact.sha256:
                raise ValueError(f"Artifact SHA mismatch: {path}")
            value = json.loads(
                raw,
                object_pairs_hook=_object,
                parse_constant=_nonfinite,
                parse_float=_finite_float,
            )
            self.cache[path] = (artifact, value, len(raw))
            self.raw_cache[path] = raw
        previous, value, _ = self.cache[path]
        if (previous.sha256, previous.source_version) != (
            artifact.sha256,
            artifact.source_version,
        ):
            raise ValueError("Conflicting artifact identity for one path")
        return {
            "path": str(path),
            "sha256": artifact.sha256,
            "source_version": artifact.source_version,
            "pointer": pointer,
            "value": _select(value, pointer),
        }

    def bind_utf8_file(self, artifact: Artifact) -> dict[str, Any]:
        """Keep the exact parsed bytes alongside their value and identity."""
        bound = self.bind(artifact)
        raw = self.raw_cache[Path(bound["path"])]
        return {**bound, "bytes": len(raw), "raw_utf8_file_text": raw.decode("utf-8")}

    def artifacts(self) -> list[dict[str, Any]]:
        return [
            {
                "path": str(path),
                "sha256": artifact.sha256,
                "source_version": artifact.source_version,
                "bytes": size,
            }
            for path, (artifact, _, size) in self.cache.items()
        ]


def _build_annex(
    question: str,
    calculation: Artifact,
    requirements: Sequence[Requirement],
    request_kind: str,
    reader: _ArtifactReader,
) -> dict[str, Any]:
    if (
        request_kind != "engineering"
        or not isinstance(question, str)
        or not question.strip()
        or not requirements
    ):
        raise ValueError("Explicit engineering question and requirements required")
    bound_calculation = reader.bind(calculation)
    rows = []
    ids = set()
    for row in requirements:
        if not row.id.strip() or not row.text.strip() or row.id in ids:
            raise ValueError("Requirements need distinct ids and nonempty text")
        ids.add(row.id)
        missing = row.unavailable_reason is not None
        if (bool(row.selections) == missing) or (
            row.unavailable_reason is not None and not row.unavailable_reason.strip()
        ):
            raise ValueError("Supply evidence or an explicit unavailable reason")
        rows.append(
            {
                "id": row.id,
                "text": row.text,
                "status": "unavailable" if missing else "available",
                "unavailable_reason": row.unavailable_reason,
                "evidence": [
                    reader.bind(s.artifact, s.pointer) for s in row.selections
                ],
            }
        )
    return {
        "question": question,
        "request_kind": request_kind,
        "calculation": bound_calculation,
        "requirements": rows,
        "artifacts": reader.artifacts(),
        "binding_verified": True,
        "evidence_complete": all(r["status"] == "available" for r in rows),
        "completeness_scope": "supplied_requirements_only",
        "semantic_verdict": "not_assessed",
        "real_world_efficacy": "not_assessed",
    }


def build_engineering_annex(
    question: str,
    calculation: Artifact,
    requirements: Sequence[Requirement],
    *,
    request_kind: str = "engineering",
) -> dict[str, Any]:
    """Bind full evidence for supplied requirements; do not grade an answer."""
    return _build_annex(
        question, calculation, requirements, request_kind, _ArtifactReader()
    )


def _assemble_response(
    question: str,
    calculation: Artifact,
    requirements: Sequence[Requirement],
    answer: Artifact,
    coverage: Sequence[AnswerCoverage],
    request_kind: str,
    reader: _ArtifactReader,
) -> dict[str, Any]:
    annex = _build_annex(question, calculation, requirements, request_kind, reader)
    if any(row["sha256"] == answer.sha256 for row in annex["artifacts"]):
        raise ValueError("Whole answer cannot serve as its own calculation or evidence")
    bound_answer = reader.bind(answer)
    value = bound_answer["value"]
    if not isinstance(value, dict) or value.get("question") != question:
        raise ValueError("Whole answer must preserve the exact original question")
    text = value.get("answer")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("A complete answer text is required")
    source_values = [reader.cache[Path(row["path"])][1] for row in annex["artifacts"]]
    selected_values = [annex["calculation"]["value"]] + [
        evidence["value"]
        for requirement in annex["requirements"]
        for evidence in requirement["evidence"]
    ]
    if any(evidence == value for evidence in source_values + selected_values):
        raise ValueError("Whole answer cannot serve as its own calculation or evidence")
    expected = {row.id for row in requirements}
    seen = set()
    mappings = []
    for row in coverage:
        if row.requirement_id not in expected or row.requirement_id in seen:
            raise ValueError("Unknown or duplicate answer requirement mapping")
        seen.add(row.requirement_id)
        if not row.spans:
            raise ValueError("Every supplied requirement needs an answer passage")
        spans = []
        intervals = set()
        for span in row.spans:
            if (
                type(span.start) is not int
                or type(span.end) is not int
                or not 0 <= span.start < span.end <= len(text)
                or not isinstance(span.quote, str)
                or not span.quote.strip()
                or text[span.start : span.end] != span.quote
                or (span.start, span.end) in intervals
            ):
                raise ValueError("Answer span must match a nonempty literal passage")
            intervals.add((span.start, span.end))
            spans.append({"start": span.start, "end": span.end, "quote": span.quote})
        mappings.append({"requirement_id": row.requirement_id, "spans": spans})
    if seen != expected:
        raise ValueError("Missing answer requirement mappings")
    return {
        "question": question,
        "request_kind": request_kind,
        "answer": text,
        "answer_artifact": bound_answer,
        "annex": annex,
        "coverage": mappings,
        "span_unit": "unicode_codepoints_zero_based_half_open",
        "artifacts": reader.artifacts(),
        "binding_verified": True,
        "literal_span_alignment_verified": True,
        "declared_requirement_mapping_complete": True,
        "question_requirement_completeness": "not_assessed",
        "source_support_of_answer": "not_assessed",
        "semantic_verdict": "not_assessed",
        "real_world_efficacy": "not_assessed",
    }


def build_engineering_response(
    question: str,
    calculation: Artifact,
    requirements: Sequence[Requirement],
    answer: Artifact,
    coverage: Sequence[AnswerCoverage],
    *,
    request_kind: str = "engineering",
) -> dict[str, Any]:
    """Bind a whole authored answer and literal passages to an evidence annex.

    Callers supply the answer and requirements. A passage may be substantively
    wrong even when its literal mapping is valid; semantic review is separate.
    """
    return _assemble_response(
        question,
        calculation,
        requirements,
        answer,
        coverage,
        request_kind,
        _ArtifactReader(),
    )


def _fields(value: Any, required: set[str], optional: set[str]) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - optional
    ):
        raise ValueError("Missing or unknown engineering request fields")
    return value


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("Engineering request collection must be a JSON array")
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Nonempty engineering request text required")
    return value


def build_engineering_response_request(request: Artifact) -> dict[str, Any]:
    """Read a fingerprinted JSON request for the offline delivery entry point."""
    reader = _ArtifactReader()
    bound_request = reader.bind(request)
    data = _fields(
        bound_request["value"],
        {
            "request_kind",
            "question",
            "calculation",
            "requirements",
            "answer",
            "coverage",
        },
        set(),
    )
    base = request.path.resolve().parent

    def artifact(value: Any) -> Artifact:
        row = _fields(value, {"path", "sha256", "source_version"}, set())
        return Artifact(
            base / _text(row["path"]),
            _text(row["sha256"]),
            _text(row["source_version"]),
        )

    requirements = []
    for value in _sequence(data["requirements"]):
        row = _fields(value, {"id", "text"}, {"selections", "unavailable_reason"})
        selections = []
        for value in _sequence(row.get("selections", [])):
            selection = _fields(value, {"artifact"}, {"pointer"})
            pointer = selection.get("pointer", "")
            if not isinstance(pointer, str):
                raise ValueError("Selection pointer must be text")
            selections.append(Selection(artifact(selection["artifact"]), pointer))
        reason = row.get("unavailable_reason")
        if reason is not None:
            reason = _text(reason)
        requirements.append(
            Requirement(_text(row["id"]), _text(row["text"]), tuple(selections), reason)
        )
    coverage = []
    for value in _sequence(data["coverage"]):
        row = _fields(value, {"requirement_id", "spans"}, set())
        spans = []
        for value in _sequence(row["spans"]):
            span = _fields(value, {"start", "end", "quote"}, set())
            spans.append(AnswerSpan(span["start"], span["end"], span["quote"]))
        coverage.append(AnswerCoverage(_text(row["requirement_id"]), tuple(spans)))
    result = _assemble_response(
        data["question"],
        artifact(data["calculation"]),
        requirements,
        artifact(data["answer"]),
        coverage,
        data["request_kind"],
        reader,
    )
    result["request_artifact"] = bound_request
    return result

"""Bind preparation and observed answer evidence; never award semantic grades.

Commitments must be supplied from a separately preserved receipt. Local hashes
check consistency, not execution authenticity or a reviewer's qualifications.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.utils.json_digest import digest
from fatebridge.validation.agent_capture import read_capture

POLICY = "meihua_observed_evidence_binding_v1"
CALCULATIONS = {"meihua_cast", "meihua_analysis"}
PROMPT_BUILDER_AST_SHA256 = (
    "dae635025428a509ba4d9b0ff797e11b6fbafbbf7a79d315229437733c66241c"
)
LEGACY_RAW_PROMPT_EVALUATOR_SHA256 = (
    "b155dcffaf768cc42bc36d873e46f807d2c1593e003f561794356e8f53e93135"
)


def file_sha(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def portable_ast_sha(node: ast.AST) -> str:
    """Use Python 3.14's default omission of empty lists on older interpreters.

    All nonempty fields, including executable type parameters, remain hashed.
    This only normalizes ast.dump formatting, not the source or grader logic.
    """
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        object.__setattr__(
            child,
            "_fields",
            tuple(name for name in child._fields if getattr(child, name, None) != []),
        )
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def _same(a: Any, b: Any) -> bool:
    return digest(a) == digest(b)


def _path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Evidence path escapes its frozen directory")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("Evidence link escapes its frozen directory")
    return result


def lookup(value: Any, path: str) -> Any:
    if not isinstance(path, str) or not path:
        raise ValueError("A nonempty observed field path is required")
    for key in path.split("."):
        if isinstance(value, list):
            if not key.isdecimal() or str(int(key)) != key:
                raise ValueError("Array paths require canonical nonnegative indexes")
            value = value[int(key)]
        else:
            value = value[key]
    return value


def _packet(record: dict[str, Any]) -> dict[str, Any]:
    result = record["result"]
    packet = result.get("structured_content", result.get("structuredContent"))
    if packet is None:
        for block in result.get("content") or []:
            if isinstance(block.get("text"), str):
                try:
                    packet = json.loads(block["text"])
                except ValueError:
                    continue
                if isinstance(packet, dict):
                    break
    if not isinstance(packet, dict):
        raise ValueError("Captured call has no structured packet")
    if result.get("is_error") or result.get("isError") or packet.get("error_code"):
        raise ValueError(
            "An actual server error cannot supply successful calculation evidence"
        )
    return packet


def _expected_prompt(case: dict[str, Any], version: str) -> str:
    prompt = case["prompt"]
    if not isinstance(prompt, str):
        raise ValueError("Prepared prompt must be text")
    if version == "raw_prompt_legacy":
        return prompt
    allowed = case.get("allowed_tools")
    if allowed is None:
        return prompt
    if allowed == []:
        return (
            "本次运行的工具合同：不调用任何 FateBridge 工具。请按适用技能核对已确认资料并直接回应当前请求。\n\n"
            + prompt
        )
    return (
        "本次运行的工具合同：只允许调用以下FateBridge工具："
        + "、".join(allowed)
        + "。即使技能给出其他通用入口，也须遵守本次限定；不以别的计算工具替代。仍按适用技能核对输入、读取实际回执和同run分页。\n\n"
        + prompt
    )


def preparation_commitment(directory: Path) -> dict[str, Any]:
    """Seal reference-only files; create this before any model execution."""
    document = json.loads((directory / "preparation.json").read_bytes())
    names = {
        "case-dataset.json",
        "preparation.json",
        "source-manifest.json",
        "reference-mcp.jsonl",
        "review-worksheet.json",
        "proposed-execution.json",
    }
    for row in document["references"]:
        names.add("model-prompts/" + row["case"] + ".txt")
        if row.get("payload_file"):
            names.add(row["payload_file"])
    return {
        "policy": POLICY,
        "role": "preparation_reference_only",
        "files": {name: file_sha(_path(directory, name)) for name in sorted(names)},
    }


def audit_preparation(
    directory: Path, commitment: dict[str, Any], *, expected_commitment_sha256: str
) -> dict[str, Any]:
    """Read sealed reference runs only; no producer calls or model invocation."""
    if (
        digest(commitment) != expected_commitment_sha256
        or commitment["role"] != "preparation_reference_only"
        or commitment["policy"] != POLICY
    ):
        raise ValueError("Preparation differs from its separately pinned commitment")
    for name, expected in commitment["files"].items():
        if file_sha(_path(directory, name)) != expected:
            raise ValueError("Committed preparation file changed: " + name)
    if not _same(commitment, preparation_commitment(directory)):
        raise ValueError("Preparation commitment does not cover its full reference set")
    report = json.loads((directory / "preparation.json").read_bytes())
    dataset = json.loads((directory / "case-dataset.json").read_bytes())
    if report["model_invocations"] != 0 or report["semantic_acceptance"] != "not_run":
        raise ValueError("Preparation cannot be promoted to model execution")
    if report["dataset_sha256"] != file_sha(directory / "case-dataset.json") or report[
        "source_manifest_sha256"
    ] != file_sha(directory / "source-manifest.json"):
        raise ValueError("Preparation dataset or source-manifest binding changed")
    sources = json.loads((directory / "source-manifest.json").read_bytes())
    for name, expected in sources.items():
        if file_sha(_path(directory / "source", name)) != expected:
            raise ValueError("Frozen preparation source changed: " + name)
    evaluator = directory / "source/scripts/evaluate_agent.py"
    builders = [
        n
        for n in ast.parse(evaluator.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "model_prompt"
    ]
    if (
        len(builders) == 1
        and portable_ast_sha(builders[0]) == PROMPT_BUILDER_AST_SHA256
    ):
        prompt_version = "allowed_tools_prefix_v1"
    elif not builders and file_sha(evaluator) == LEGACY_RAW_PROMPT_EVALUATOR_SHA256:
        prompt_version = "raw_prompt_legacy"
    else:
        raise ValueError("Unknown frozen prompt builder requires separate review")
    worksheet = json.loads((directory / "review-worksheet.json").read_bytes())
    cases = {c["id"]: c for c in dataset["cases"]}
    ids = [r["case"] for r in report["references"]]
    if (
        len(set(ids)) != len(ids)
        or [c["id"] for c in dataset["cases"] if c["id"] in ids] != ids
        or [c["case"] for c in worksheet["cases"]] != ids
        or len(ids) != report["selected_case_count"]
    ):
        raise ValueError("Prepared case set or order changed")
    if worksheet["model_invocations"] != 0:
        raise ValueError("Reference worksheet is not a model result")
    records = read_capture(directory / "reference-mcp.jsonl")
    calls = [(i, r) for i, r in enumerate(records) if r["event"] == "tool_call"]
    used = set()
    run_ids = []
    criteria = assertions = 0
    versions = set()
    for reference, row in zip(report["references"], worksheet["cases"], strict=True):
        case = cases[reference["case"]]
        if (
            directory / "model-prompts" / (case["id"] + ".txt")
        ).read_text() != _expected_prompt(case, prompt_version):
            raise ValueError(
                "Prepared model prompt differs from its sealed case contract"
            )
        if (
            row["model_status"] != "not_run"
            or row["semantic_status"] != "pending"
            or len(row["checks"]) != len(case["manual_review"])
        ):
            raise ValueError("Unrun semantic criteria were changed or promoted")
        for check, text in zip(row["checks"], case["manual_review"], strict=True):
            if (
                check["criterion"] != text
                or check["status"] != "pending"
                or any(
                    check[k] is not None
                    for k in ["answer_quote", "actual_model_run_id", "reviewer"]
                )
                or check["evidence_paths"]
            ):
                raise ValueError("Prepared criterion is not a pending unreviewed item")
            criteria += 1
        request = case.get("reference_request")
        if request is None:
            if reference[
                "reference_status"
            ] != "no_calculation_required" or not case.get("no_calculation"):
                raise ValueError("Missing planned reference call")
            continue
        wrapped = json.loads(_path(directory, reference["payload_file"]).read_bytes())
        if (
            file_sha(_path(directory, reference["payload_file"]))
            != reference["payload_sha256"]
        ):
            raise ValueError("Prepared reference payload changed")
        expected_arguments = {
            **request["arguments"],
            "fields": None,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        }
        if (
            wrapped["tool"] != request["tool"]
            or not _same(wrapped["arguments"], expected_arguments)
            or wrapped["is_error"]
        ):
            raise ValueError("Reference request or error status differs from its case")
        matches = [
            (i, r)
            for i, r in calls
            if r["tool"] == wrapped["tool"]
            and _same(r["arguments"], wrapped["arguments"])
            and _packet(r)["run_metadata"]["run_id"] == reference["run_id"]
        ]
        if len(matches) != 1 or matches[0][0] in used:
            raise ValueError("Reference call is missing, duplicated or cross-bound")
        index, record = matches[0]
        used.add(index)
        if record["outcome"] != "returned":
            raise ValueError("Reference server did not return a packet")
        packet = _packet(record)
        audit_observed_inputs(case, [record])
        if not _same(packet, wrapped["structured_content"]):
            raise ValueError("Reference file differs from actual recorded server reply")
        metadata = packet["run_metadata"]
        if (
            not isinstance(metadata["run_id"], str)
            or not metadata["run_id"]
            or metadata["run_id"] != reference["run_id"]
            or digest({k: v for k, v in packet.items() if k != "run_metadata"})
            != metadata["business_output_sha256"]
        ):
            raise ValueError("Reference run or complete business result changed")
        run_ids.append(metadata["run_id"])
        weather = packet.get("interpretation", {}).get("weather")
        if weather:
            version = weather["ruleset_id"] + "@" + weather["version"]
            versions.add(version)
            if dataset.get("target_weather_profile") not in {None, version}:
                raise ValueError(
                    "Reference weather version differs from the batch target"
                )
        for assertion in case.get("reference_assertions", []):
            if not _same(lookup(packet, assertion["path"]), assertion["value"]):
                raise ValueError(
                    "Predeclared reference assertion failed: "
                    + case["id"]
                    + ":"
                    + assertion["path"]
                )
            assertions += 1
    if len(used) != len(calls) or len(run_ids) != len(set(run_ids)):
        raise ValueError("Unexpected reference calls or reused run identity")
    return {
        "policy": POLICY,
        "reference_binding_passed": True,
        "cases": len(ids),
        "criteria_pending": criteria,
        "actual_reference_calls": len(used),
        "source_files_verified": len(sources),
        "reference_assertions_verified": assertions,
        "reference_run_ids": run_ids,
        "weather_profiles": sorted(versions),
        "model_invocations": 0,
        "semantic_acceptance": "not_run",
        "independent_review_performed": False,
        "prompt_contract_version": prompt_version,
        "model_execution_contract_ready": prompt_version == "allowed_tools_prefix_v1",
    }


def _stitch(pages: list[dict[str, Any]], expected_sha: str) -> str | None:
    indexed: dict[int, dict[str, Any]] = {}
    for page in pages:
        page_offset = page["offset"]
        if (
            type(page_offset) is not int
            or page_offset < 0
            or page["sha256"] != expected_sha
            or not isinstance(page["text"], str)
        ):
            raise ValueError("Observed page identity changed")
        if page_offset in indexed and not _same(indexed[page_offset], page):
            raise ValueError("Conflicting observed page bodies")
        indexed[page_offset] = page
    offset: int | None = 0
    parts = []
    while offset is not None and offset in indexed:
        page = indexed[offset]
        parts.append(page["text"])
        following = page["next_offset"]
        if following is not None and (
            type(following) is not int
            or following != offset + len(page["text"])
            or following <= offset
        ):
            raise ValueError("Observed page chain changed")
        offset = following
    if offset is not None:
        return None
    text = "".join(parts)
    if hashlib.sha256(text.encode()).hexdigest() != expected_sha:
        raise ValueError("Complete observed page text differs from its checksum")
    return text


def observed_sources(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Use only recorded packets/resources; never open an advertised result file."""
    sources = {}
    for index, record in enumerate(records):
        if (
            record["event"] != "tool_call"
            or record.get("outcome") != "returned"
            or record.get("tool") not in CALCULATIONS
        ):
            continue
        packet = _packet(record)
        run = packet["run_metadata"]["run_id"]
        source = {"packet": packet, "run_id": run, "fields": {}}
        sources[index] = source
        delivery = packet.get("result_delivery")
        if not delivery:
            continue
        prefix = f"fatebridge://results/{delivery['result_id']}/"
        whole: list[dict[str, Any]] = []
        fields: dict[str, list[dict[str, Any]]] = {}
        for item in records[index + 1 :]:
            if (
                item["event"] != "resource_read"
                or item.get("outcome") != "returned"
                or not item.get("uri", "").startswith(prefix)
            ):
                continue
            tail = item["uri"][len(prefix) :]
            verified = tail.startswith("verified/")
            if verified:
                parts = tail.split("/", 3)
                if len(parts) != 4 or parts[1] != run or parts[2] != delivery["sha256"]:
                    raise ValueError("Verified URI differs from the original receipt")
                tail = parts[3]
                if not tail.startswith("fields/"):
                    tail = "pages/" + tail
            if not (tail.startswith("pages/") or tail.startswith("fields/")):
                continue
            contents = item["result"]["contents"]
            if len(contents) != 1:
                raise ValueError("Malformed observed resource page")
            # FastMCP's server middleware serializes ReadResourceContents.content;
            # protocol-shaped captures use TextResourceContents.text instead.
            texts = [contents[0][k] for k in ("content", "text") if k in contents[0]]
            if (
                not texts
                or not all(isinstance(t, str) for t in texts)
                or any(t != texts[0] for t in texts)
            ):
                raise ValueError("Observed resource body is missing or contradictory")
            page = json.loads(texts[0])
            if verified:
                verification = page["verification"]
                if (
                    verification["method"] != "retained_payload_sha256_v1"
                    or verification["scope"] != "entire_retained_payload"
                    or verification["run_id"] != run
                    or verification["payload_sha256"] != delivery["sha256"]
                    or verification["calculation_repeated"] is not False
                    or page["result_id"] != delivery["result_id"]
                ):
                    raise ValueError("Observed verification differs from the receipt")
            if tail.startswith("pages/"):
                offset = tail.removeprefix("pages/")
                if (
                    page.get("result_id", delivery["result_id"])
                    != delivery["result_id"]
                    or page.get("path") is not None
                ):
                    raise ValueError("Observed whole page substituted another result")
                destination = whole
            else:
                path, offset = tail.removeprefix("fields/").rsplit("/", 1)
                if page["path"] != path or page["result_id"] != delivery["result_id"]:
                    raise ValueError("Observed field page substituted another result")
                destination = fields.setdefault(path, [])
            if not offset.isdecimal() or int(offset) != page["offset"]:
                raise ValueError("Observed resource URI and offset disagree")
            destination.append(page)
        text = _stitch(whole, delivery["sha256"])
        if text is not None:
            if (
                len(text) != delivery["total_chars"]
                or len(text.encode()) != delivery["total_bytes"]
            ):
                raise ValueError("Observed complete delivery length changed")
            complete = json.loads(text)
            # A budgeted first receipt can defer runtime/provenance metadata.
            # Its delivery checksum commits to the complete original receipt;
            # these two mandatory identities must still match the first reply.
            if any(
                not _same(complete["run_metadata"][key], packet["run_metadata"][key])
                for key in ("run_id", "business_output_sha256")
            ):
                raise ValueError("Observed complete delivery substituted another run")
            source["delivered"] = complete
            if (
                digest({k: v for k, v in complete.items() if k != "run_metadata"})
                == complete["run_metadata"]["business_output_sha256"]
            ):
                source["complete"] = complete
        for path, pages in fields.items():
            text = _stitch(pages, pages[0]["sha256"])
            if text is not None:
                source["fields"][path] = json.loads(text)
    return sources


def audit_observed_inputs(case: dict[str, Any], records: list[dict[str, Any]]) -> int:
    """Additional v40 absence constraints, outside the unchanged legacy grader."""
    constraints = case.get("argument_absent_or_null", {})
    checked = 0
    for tool, paths in constraints.items():
        calls = [
            r for r in records if r["event"] == "tool_call" and r.get("tool") == tool
        ]
        if not calls:
            raise ValueError("Required observed input constraint has no actual call")
        for record in calls:
            for path in paths:
                try:
                    value = lookup(record["arguments"], path)
                except KeyError:
                    value = None
                if value is not None:
                    raise ValueError(
                        "Unconfirmed input was supplied: " + tool + ":" + path
                    )
                checked += 1
    return checked


def bind_answer_fields(
    answer_path: Path,
    capture_path: Path,
    claims: list[dict[str, Any]],
    *,
    expected_answer_sha256: str,
    expected_capture_sha256: str,
    reference_run_ids: list[str],
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check literal answer/evidence binding, not Chinese entailment or a grade."""
    if (
        file_sha(answer_path) != expected_answer_sha256
        or file_sha(capture_path) != expected_capture_sha256
    ):
        raise ValueError("Answer or observed capture differs from its pinned receipt")
    answer = answer_path.read_text()
    records = read_capture(capture_path)
    input_checks = audit_observed_inputs(case, records) if case is not None else 0
    sources = observed_sources(records)
    for claim in claims:
        start, end = claim["start"], claim["end"]
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(answer)
            or answer[start:end] != claim["quote"]
        ):
            raise ValueError("Claim quote differs from the preserved answer")
        index = claim["journal_index"]
        if type(index) is not int or index not in sources:
            raise ValueError("Claim has no observed calculation packet")
        source = sources[index]
        if source["run_id"] in reference_run_ids or source["run_id"] != claim["run_id"]:
            raise ValueError(
                "Prepared reference or another run cannot replace model evidence"
            )
        values = []
        for name in ("packet", "delivered", "complete"):
            if name in source:
                try:
                    values.append(lookup(source[name], claim["path"]))
                except (KeyError, IndexError, TypeError):
                    pass
        for path, value in source["fields"].items():
            if claim["path"] == path:
                values.append(value)
            elif claim["path"].startswith(path + "."):
                values.append(lookup(value, claim["path"][len(path) + 1 :]))
        if not values or any(not _same(v, claim["value"]) for v in values):
            raise ValueError(
                "Claim value/type is absent, contradictory or differs from observed data"
            )
    return {
        "policy": POLICY,
        "literal_claims_bound": len(claims),
        "additional_input_constraints_checked": input_checks,
        "semantic_acceptance": "not_assessed",
        "model_execution_authenticity_independently_verified": False,
        "scope": "captured returned data and logged resource reads only; no reference recalculation or current result-file reading; not proof of internal model context",
    }

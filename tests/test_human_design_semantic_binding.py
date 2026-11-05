"""Adversarial checks for first-answer/evidence binding, never semantic scoring."""

import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from fatebridge.services.replay_metadata import digest
from scripts.audit_human_design_semantics import (
    DATASET_SHA256,
    audit_review,
    file_digest,
    observed_sources,
    verify_evidence,
)

ROOT = Path(__file__).resolve().parents[1]


def test_autocrlf_keeps_sealed_case_original_answer_and_capture_bytes(tmp_path):
    git = shutil.which("git")
    if not git:
        pytest.skip("Git is required for the checkout-byte control")
    repository = tmp_path / "repo"
    repository.mkdir()
    checkout = tmp_path / "checkout"
    dataset = "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json"
    samples = {
        dataset: (ROOT / dataset).read_bytes(),
        "answer.txt": "Current synthetic answer.\n中文行。\n".encode(),
        "events.jsonl": b'{"type":"synthetic.current.event"}\n',
        "mcp-calls.jsonl": b'{"event":"synthetic.current.call"}\n',
    }
    paths = list(samples)
    (repository / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    for name in paths:
        p = repository / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(samples[name])
    command = [
        git,
        "-c",
        "core.autocrlf=true",
        "-c",
        "core.attributesFile=" + os.devnull,
    ]
    for args in [
        ["init", "-q"],
        ["add", "--", ".gitattributes", *paths],
        ["checkout-index", "--all", "--force", "--prefix=" + checkout.as_posix() + "/"],
    ]:
        subprocess.run(command + args, cwd=repository, check=True, capture_output=True)
    for name in paths:
        assert (checkout / name).read_bytes() == samples[name], name


def records():
    full = {"profile": "1/3", "sample_count": 1}
    full["run_metadata"] = {
        "run_id": "same-run",
        "business_output_sha256": digest(full),
    }
    text = json.dumps(full, ensure_ascii=False, separators=(",", ":"))
    sha = hashlib.sha256(text.encode()).hexdigest()
    packet = {
        "profile": "1/3",
        "run_metadata": full["run_metadata"],
        "result_delivery": {
            "result_id": "observed-result",
            "sha256": sha,
            "total_chars": len(text),
            "total_bytes": len(text.encode()),
        },
    }
    rows = [
        {
            "event": "tool_call",
            "outcome": "returned",
            "result": {"structured_content": packet},
        }
    ]
    for start, end in [(0, 20), (20, len(text))]:
        page = {
            "offset": start,
            "text": text[start:end],
            "next_offset": end if end < len(text) else None,
            "sha256": sha,
        }
        rows.append(
            {
                "event": "resource_read",
                "outcome": "returned",
                "uri": f"fatebridge://results/observed-result/pages/{start}",
                "result": {"contents": [{"text": json.dumps(page)}]},
            }
        )
    return rows, full


def test_only_complete_observed_same_run_pages_provide_full_business_fields():
    rows, full = records()
    assert observed_sources(rows)[0]["complete"] == full
    assert "complete" not in observed_sources(rows[:2])[0]
    altered = copy.deepcopy(rows)
    altered[2]["uri"] = "fatebridge://results/different-result/pages/20"
    assert "complete" not in observed_sources(altered)[0]


@pytest.mark.parametrize(
    "mutation", ["bad_hash", "bad_offset", "bad_next", "different_page", "changed_body"]
)
def test_changed_observed_pages_are_rejected_without_recalculation(mutation):
    rows, _ = records()
    page = json.loads(rows[1]["result"]["contents"][0]["text"])
    if mutation == "bad_hash":
        page["sha256"] = "0" * 64
    elif mutation == "bad_offset":
        page["offset"] = 1
    elif mutation == "bad_next":
        page["next_offset"] = 19
    elif mutation == "changed_body":
        page["text"] = page["text"].replace('"1/3"', '"2/4"')
    elif mutation == "different_page":
        duplicate = copy.deepcopy(rows[1])
        other = {**page, "text": "changed"}
        duplicate["result"]["contents"][0]["text"] = json.dumps(other)
        rows.append(duplicate)
    rows[1]["result"]["contents"][0]["text"] = json.dumps(page)
    with pytest.raises(ValueError):
        observed_sources(rows)


def test_typed_field_quotes_cannot_substitute_bool_or_another_run():
    rows, _ = records()
    sources = observed_sources(rows)
    claim = dict(
        kind="field",
        journal_index=0,
        run_id="same-run",
        source="complete",
        path="sample_count",
        value=1,
    )
    verify_evidence(claim, sources)
    for changed in [
        dict(claim, value=True),
        dict(claim, run_id="different"),
        dict(claim, source="pages"),
    ]:
        with pytest.raises(ValueError):
            verify_evidence(changed, sources)
    with pytest.raises(KeyError):
        verify_evidence(claim, observed_sources(rows[:2]))


def test_fragment_quotes_stay_bound_to_the_observed_origin_packet():
    rows, _ = records()
    sources = observed_sources(rows[:2])
    page = sources[0]["pages"][1]
    claim = dict(
        kind="page_text",
        journal_index=0,
        run_id="same-run",
        page_journal_index=1,
        start=0,
        end=5,
        quote=page["text"][:5],
    )
    verify_evidence(claim, sources)
    with pytest.raises(ValueError):
        verify_evidence(dict(claim, quote="made-up"), sources)
    with pytest.raises(KeyError):
        verify_evidence(dict(claim, page_journal_index=2), sources)


def test_actual_file_stdout_and_projected_deliveries_do_not_become_full_business_proofs():
    rows, full = records()
    projected = {"profile": full["profile"], "run_metadata": full["run_metadata"]}
    text = json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
    packet = rows[0]["result"]["structured_content"]
    packet["result_delivery"].update(
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        total_chars=len(text),
        total_bytes=len(text.encode()),
        file_path="/actual-delivery.json",
    )
    rows[0]["arguments"] = {"fields": ["profile"]}
    event = {
        "type": "item.completed",
        "item": {
            "id": "observed",
            "type": "command_execution",
            "exit_code": 0,
            "command": "read /actual-delivery.json",
            "aggregated_output": json.dumps({"payload": projected}),
        },
    }
    sources = observed_sources(rows[:1], [event])
    assert sources[0]["delivered"] == projected
    assert "complete" not in sources[0]
    assert "delivered" not in observed_sources(rows[:1], [])[0]
    rows[0]["arguments"] = {"fields": None}
    with pytest.raises(ValueError):
        observed_sources(rows[:1], [event])


def test_changed_or_wrong_file_stdout_is_never_used_as_evidence():
    rows, full = records()
    rows[0]["result"]["structured_content"]["result_delivery"][
        "file_path"
    ] = "/original.json"
    event = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "exit_code": 0,
            "command": "read /original.json",
            "aggregated_output": json.dumps({"payload": {**full, "profile": "2/4"}}),
        },
    }
    with pytest.raises(ValueError):
        observed_sources(rows[:1], [event])
    event["item"]["command"] = "read /other.json"
    assert "delivered" not in observed_sources(rows[:1], [event])[0]


def test_rehashing_forged_answer_and_review_cannot_replace_original_agent_message(
    review_files,
):
    root, path, review = review_files
    case = review["cases"][0]
    answer = root / case["id"] / "answer.txt"
    answer.write_text(answer.read_text().replace("First line.", "Wrong line."))
    case["answer_sha256"] = file_digest(answer)
    case["units"][0]["quote"] = "Wrong line."
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="original final agent message"):
        audit_review(root, path)


def test_rehashed_journal_still_has_to_match_original_mechanical_capture_receipt(
    review_files,
):
    root, path, review = review_files
    case = review["cases"][0]
    capture = root / case["id"] / "mcp-calls.jsonl"
    capture.write_text("\n")
    case["capture_sha256"] = file_digest(capture)
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="original mechanical report"):
        audit_review(root, path)


@pytest.fixture
def review_files(tmp_path):
    data = (
        ROOT / "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json"
    ).read_bytes()
    assert hashlib.sha256(data).hexdigest() == DATASET_SHA256
    (tmp_path / "case-dataset.json").write_bytes(data)
    cases = json.loads(data)["cases"]
    folder = tmp_path / cases[0]["id"]
    folder.mkdir()
    (folder / "answer.txt").write_text("First line.\nSecond line.\n")
    (folder / "mcp-calls.jsonl").write_text("")
    (folder / "events.jsonl").write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": (folder / "answer.txt").read_text(),
                },
            }
        )
        + "\n"
    )
    from scripts.evaluate_agent import model_prompt

    (folder / "model-prompt.txt").write_text(model_prompt(cases[0]))
    original = dict(
        case=cases[0]["id"],
        mechanical_checks_passed=False,
        failures=["original_failure"],
        exit_code=0,
        prompt_sha256=file_digest(folder / "model-prompt.txt"),
        tool_calls=[],
        commands=[],
        capture={"journal_sha256": file_digest(folder / "mcp-calls.jsonl")},
    )
    (tmp_path / "source").mkdir()
    (tmp_path / "source/runtime.txt").write_text("original model runtime")
    manifest = {"runtime.txt": file_digest(tmp_path / "source/runtime.txt")}
    (tmp_path / "source-manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "report.json").write_text(
        json.dumps(
            {
                "cases": [original],
                "unrun_case_ids": [c["id"] for c in cases[1:]],
                "source_sha256": digest(manifest),
            }
        )
    )
    units = [
        dict(
            start=0, end=11, quote="First line.", assessment="unverified", evidence=[]
        ),
        dict(
            start=12,
            end=24,
            quote="Second line.",
            assessment="non_factual",
            evidence=[],
        ),
    ]
    first = dict(
        id=cases[0]["id"],
        status="reviewed",
        original_mechanical_failures=["original_failure"],
        mechanical_checks_passed=False,
        answer_sha256=file_digest(folder / "answer.txt"),
        capture_sha256=file_digest(folder / "mcp-calls.jsonl"),
        events_sha256=file_digest(folder / "events.jsonl"),
        units=units,
        criteria=[
            dict(
                criterion=c,
                status="indeterminate",
                rationale="No asserted semantic truth",
                unit_indices=[0, 1],
            )
            for c in cases[0]["manual_review"]
        ],
    )
    review = dict(
        dataset_sha256=DATASET_SHA256,
        original_report_sha256=file_digest(tmp_path / "report.json"),
        cases=[first] + [dict(id=c["id"], status="not_run") for c in cases[1:]],
    )
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    return tmp_path, path, review


def test_bound_review_preserves_failed_mechanical_outcome_without_claiming_semantic_truth(
    review_files,
):
    root, path, _ = review_files
    r = audit_review(root, path)
    assert r["status"] == "verified_first_answer_review_binding"
    assert r["executed_cases"] == 1 and r["cohort_cases"] == 8
    assert r["reviewer_criterion_decisions"] == {"indeterminate": 3}
    assert r["semantic_judgment_independently_certified"] is False
    assert r["all_live_model_answers_certified"] is False
    assert "native_environment_binding" not in r


@pytest.mark.parametrize(
    "fault",
    [None, "review_sha", "changed_bytes", "different_stage", "missing_execution_sha"],
)
def test_new_review_binds_native_selection_and_rejects_stage_downgrade(
    review_files, fault
):
    from fatebridge.validation.evaluation_environment import (
        capture_selection,
        selection_bytes,
    )

    root, path, review = review_files
    # Keep preparation artifacts inside this test's directory. Its parent is
    # shared by other pytest cases and must never acquire fake stage metadata.
    preparation = root / "native-preparation"
    run = preparation / "model-run"
    run.mkdir(parents=True)
    original_root = root
    for item in original_root.iterdir():
        if item != preparation:
            shutil.move(str(item), run / item.name)
    path = run / path.name
    root = run
    raw = selection_bytes(capture_selection({"SE_EPHE_PATH": "/prepared/ephe"}))
    sha = hashlib.sha256(raw).hexdigest()
    (root / "native-environment.json").write_bytes(raw)
    report_path = root / "report.json"
    report = json.loads(report_path.read_text())
    report["native_environment_sha256"] = sha
    review["native_environment_sha256"] = sha
    if fault == "review_sha":
        review["native_environment_sha256"] = "0" * 64
    elif fault == "changed_bytes":
        (root / "native-environment.json").write_bytes(raw + b" ")
    elif fault in {"different_stage", "missing_execution_sha"}:
        other = selection_bytes(capture_selection({"SE_EPHE_PATH": "/other/ephe"}))
        (root.parent / "native-environment.json").write_bytes(other)
        (root.parent / "preparation.json").write_text(
            json.dumps({"native_environment_sha256": hashlib.sha256(other).hexdigest()})
        )
        if fault == "missing_execution_sha":
            report.pop("native_environment_sha256")
            review.pop("native_environment_sha256")
    report_path.write_text(json.dumps(report))
    review["original_report_sha256"] = file_digest(report_path)
    path.write_text(json.dumps(review))
    if fault:
        with pytest.raises(ValueError):
            audit_review(root, path)
    else:
        binding = audit_review(root, path)["native_environment_binding"]
        assert binding["status"] == "verified_execution_selection_only"
        assert binding["stage_equivalence_verified"] is False
        (root.parent / "native-environment.json").write_bytes(raw)
        (root.parent / "preparation.json").write_text(
            json.dumps({"native_environment_sha256": sha})
        )
        binding = audit_review(root, path)["native_environment_binding"]
        assert binding["status"] == "verified_exact_declared_native_selection"
        assert binding["stage_equivalence_verified"] is True
        assert binding["actual_file_read_set_authenticated"] is False


def test_same_model_source_archive_is_verified_without_extracting_files(review_files):
    root, path, _ = review_files
    archive = root / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        raw = (root / "source/runtime.txt").read_bytes()
        member = tarfile.TarInfo("source/runtime.txt")
        member.size = len(raw)
        tar.addfile(member, io.BytesIO(raw))
    assert audit_review(root, path, source_archive=archive)["reviewed_answers"] == 1
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("source/runtime.txt")
        member.size = 7
        tar.addfile(member, io.BytesIO(b"changed"))
    with pytest.raises(ValueError):
        audit_review(root, path, source_archive=archive)


def test_no_answer_infrastructure_failure_stays_distinct_from_an_answer_review(
    review_files,
):
    root, path, review = review_files
    folder = root / review["cases"][0]["id"]
    original = json.loads((root / "report.json").read_text())
    original["cases"][0]["exit_code"] = 1
    (root / "report.json").write_text(json.dumps(original))
    review["original_report_sha256"] = file_digest(root / "report.json")
    case = review["cases"][0]
    case.update(
        status="execution_failed_without_answer",
        units=[],
        criteria=[],
        answer_sha256=None,
    )
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        audit_review(root, path)
    (folder / "answer.txt").unlink()
    with pytest.raises(ValueError):
        audit_review(root, path)
    # A true infrastructure rejection has neither a file nor an emitted answer.
    (folder / "events.jsonl").write_text(
        json.dumps({"type": "turn.failed", "error": {"message": "before any answer"}})
        + "\n"
    )
    case["events_sha256"] = file_digest(folder / "events.jsonl")
    path.write_text(json.dumps(review))
    bound = audit_review(root, path)
    assert (
        bound["execution_failed_without_answer"] == 1 and bound["reviewed_answers"] == 0
    )


@pytest.mark.parametrize("target", ["events", "source"])
def test_original_observation_log_and_model_runtime_source_are_bound(
    review_files, target
):
    root, path, review = review_files
    file = (
        root / review["cases"][0]["id"] / "events.jsonl"
        if target == "events"
        else root / "source/runtime.txt"
    )
    file.write_text("changed")
    with pytest.raises(ValueError):
        audit_review(root, path)


@pytest.mark.parametrize(
    "observed,failed,expected",
    [(False, False, "incomplete"), (True, False, "failed"), (False, True, "failed")],
)
def test_finite_live_development_success_cannot_close_original_full_requirement(
    observed, failed, expected
):
    from scripts.audit_human_design import live_model_requirement_status

    assert (
        live_model_requirement_status(
            {
                "status": "bounded_first_answers_reviewed",
                "targets": [{"original_mechanical_checks_passed": not failed}],
                "reviewer_decisions": {"fail": int(observed), "pass": 24},
            }
        )
        == expected
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "remove_case",
        "rewrite_failure",
        "skip_unit",
        "change_quote",
        "omit_criterion",
        "change_criterion",
        "invent_unrun_review",
    ],
)
def test_failed_rows_criteria_and_complete_answer_cannot_be_removed_or_regraded(
    review_files, mutation
):
    root, path, review = review_files
    case = review["cases"][0]
    if mutation == "remove_case":
        review["cases"].pop()
    elif mutation == "rewrite_failure":
        case["original_mechanical_failures"] = []
    elif mutation == "skip_unit":
        case["units"].pop(0)
    elif mutation == "change_quote":
        case["units"][0]["quote"] = "Corrected line"
    elif mutation == "omit_criterion":
        case["criteria"].pop()
    elif mutation == "change_criterion":
        case["criteria"][0]["criterion"] = "easier criterion"
    else:
        review["cases"][1]["status"] = "reviewed"
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        audit_review(root, path)

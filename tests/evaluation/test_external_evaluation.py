"""External suite selection, integrity and hidden-data isolation; no model calls."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.validation.external_evaluation import (
    LAYERS,
    evaluation_summary,
    freeze_external_selection,
    json_bytes,
    load_external_suite,
    load_frozen_selection,
    sha256,
)
from scripts.evaluate_agent import model_prompt, prepare_workspace


def make_suite(root: Path):
    root.mkdir()
    cases = []
    identities = []
    for split in ("development", "holdout"):
        normalized = {
            "gender": "女",
            "year": 2000,
            "month": 1,
            "day": 1 if split == "development" else 2,
            "time_expression": "10:15",
        }
        fingerprint = sha256(
            (json.dumps(normalized, ensure_ascii=False, indent=2) + "\n").encode()
        )
        identity = {
            "source_case_id": split + "_birth",
            "identity_key": "birth:" + fingerprint,
            "birth_fingerprint": fingerprint,
            "split": split,
            "normalized_input": normalized,
        }
        identities.append(identity)
        for layer in LAYERS:
            cases.append(
                {
                    "id": split + "_" + layer,
                    "source_case_id": identity["source_case_id"],
                    "identity_key": identity["identity_key"],
                    "birth_fingerprint": identity["birth_fingerprint"],
                    "split": split,
                    "evaluation_layer": layer,
                    "source": {
                        "repository": "https://example.invalid/source",
                        "commit": "a" * 40,
                    },
                    "prompt": split + "_PROMPT_SENTINEL",
                    "manual_review": [split + "_RUBRIC_SENTINEL"],
                    "no_calculation": True,
                }
            )
    files = {
        "cases.json": {
            "suite_id": "mingli-bench-v1",
            "dataset_kind": "public_competition",
            "cases": cases,
        },
        "corpus.json": {"records": identities},
        "split-manifest.json": {
            "development": ["development_birth"],
            "holdout": ["holdout_birth"],
            "identities": identities,
        },
    }
    for name, value in files.items():
        (root / name).write_bytes(json_bytes(value))
    (root / "source.txt").write_text("UPSTREAM_RAW_INCLUDES_HOLDOUT_ANSWER")
    manifest = {
        "suite_id": "mingli-bench-v1",
        "dataset_kind": "public_competition",
        "schema_version": 1,
        "source_commit": "a" * 40,
        "cases_file": "cases.json",
        "corpus_file": "corpus.json",
        "split_manifest_file": "split-manifest.json",
        "split_policy": {"unit": "source_case_id"},
        "files": [],
    }
    for path in sorted(root.iterdir()):
        data = path.read_bytes()
        manifest["files"].append(
            {"path": path.name, "sha256": sha256(data), "bytes": len(data)}
        )
    (root / "manifest.json").write_bytes(json_bytes(manifest))
    return root


def rewrite_hashed(root, name, mutate):
    path = root / name
    document = json.loads(path.read_text())
    mutate(document)
    path.write_bytes(json_bytes(document))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest["files"] if row["path"] == name)
    entry.update(sha256=sha256(path.read_bytes()), bytes=path.stat().st_size)
    manifest_path.write_bytes(json_bytes(manifest))


def test_default_selection_and_frozen_replay_do_not_contain_holdout_content(tmp_path):
    root = make_suite(tmp_path / "suite")
    document = load_external_suite(root)
    assert document["split"] == "development"
    assert len(document["cases"]) == 3
    output = tmp_path / "frozen"
    output.mkdir()
    dataset = freeze_external_selection(document, output)
    (output / "case-dataset.json").write_bytes(dataset)
    assert b"holdout_PROMPT_SENTINEL" not in dataset
    assert b"holdout_RUBRIC_SENTINEL" not in dataset
    assert b"UPSTREAM_RAW_INCLUDES_HOLDOUT_ANSWER" not in dataset
    receipt = (output / "external-suite-receipt.json").read_text()
    assert "holdout_birth" not in receipt
    holdout = json.loads((root / "split-manifest.json").read_text())["identities"][1]
    assert holdout["identity_key"] not in receipt
    assert holdout["birth_fingerprint"] not in receipt
    assert document["provenance"]["source_artifacts"]
    (root / "cases.json").write_text("upstream changed after freezing")
    assert (
        load_frozen_selection(output / "case-dataset.json", "development") == document
    )
    with pytest.raises(ValueError, match="split or kind mismatch"):
        load_frozen_selection(output / "case-dataset.json", "holdout")
    with pytest.raises(ValueError, match="outside selected split"):
        load_frozen_selection(
            output / "case-dataset.json", "development", ["holdout_input_quality"]
        )
    (output / "case-dataset.json").write_bytes(dataset + b" ")
    with pytest.raises(ValueError, match="integrity mismatch"):
        load_frozen_selection(output / "case-dataset.json", "development")


def test_full_corpus_is_validated_before_subset_selection(tmp_path):
    root = make_suite(tmp_path / "suite")
    with pytest.raises(ValueError, match="outside selected split"):
        load_external_suite(root, case_ids=["holdout_input_quality"])
    with pytest.raises(ValueError, match="Duplicate requested"):
        load_external_suite(root, case_ids=["development_input_quality"] * 2)
    (root / "source.txt").write_text("source changed")
    with pytest.raises(ValueError, match="artifact integrity"):
        load_external_suite(root)


@pytest.mark.parametrize("field", ["identity_key", "birth_fingerprint"])
def test_duplicate_birth_identity_cannot_leak_between_splits(tmp_path, field):
    root = make_suite(tmp_path / "suite")
    rewrite_hashed(
        root,
        "split-manifest.json",
        lambda doc: doc["identities"][1].update({field: doc["identities"][0][field]}),
    )
    with pytest.raises(ValueError, match="leaks across source splits"):
        load_external_suite(root)


def test_relabelled_cases_and_unknown_layers_fail_closed(tmp_path):
    root = make_suite(tmp_path / "suite")
    rewrite_hashed(
        root, "cases.json", lambda doc: doc["cases"][0].update(split="holdout")
    )
    with pytest.raises(ValueError, match="leaks across splits"):
        load_external_suite(root)


def test_rekeying_a_duplicate_birth_cannot_bypass_split_validation(tmp_path):
    root = make_suite(tmp_path / "suite")
    rewrite_hashed(
        root,
        "corpus.json",
        lambda doc: doc["records"][1].update(
            normalized_input=doc["records"][0]["normalized_input"]
        ),
    )
    with pytest.raises(ValueError, match="fingerprint does not match inputs"):
        load_external_suite(root)


def test_layer_denominators_never_turn_mechanical_success_into_semantic_pass(tmp_path):
    document = load_external_suite(make_suite(tmp_path / "suite"))
    prepared = evaluation_summary(document)
    assert prepared["dataset_kind"] == "public_competition"
    assert prepared["semantic_acceptance"] == "not_run"
    case = document["cases"][0]
    summary = evaluation_summary(
        document, [{"case": case["id"], "mechanical_checks_passed": True}]
    )
    assert summary["semantic_acceptance"] == "pending"
    layer = summary["layer_denominators"][case["evaluation_layer"]]
    assert layer == {
        "selected": 1,
        "executed": 1,
        "mechanical_passed": 1,
        "semantic_reviewed": 0,
        "semantic_status": "pending",
    }
    assert sum(row["selected"] for row in summary["layer_denominators"].values()) == 3


def test_model_workspace_excludes_corpus_answers_and_evaluation_docs(tmp_path):
    source = tmp_path / "source"
    for name, text in {
        "AGENTS.md": "runtime instructions",
        "skills/onda-shiye/SKILL.md": "runtime skill",
        "src/fatebridge/example.py": "runtime code",
        "docs/runtime.md": "runtime guide",
        "docs/mingli-bench-evaluation.md": "HIDDEN_NEW_RUBRIC",
        "docs/validation/report.json": "HIDDEN_PAST_REPORT",
        "tests/fixtures/mingli_bench_v1/cases.json": "HIDDEN_CASES_AND_ANSWERS",
    }.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    assert (workspace / "docs/runtime.md").exists()
    contents = "\n".join(
        path.read_text() for path in workspace.rglob("*") if path.is_file()
    )
    assert "HIDDEN_" not in contents
    case = load_external_suite(make_suite(tmp_path / "suite"))["cases"][0]
    assert case["manual_review"][0] not in model_prompt(case)


def test_external_zero_tool_contract_is_explicit_without_changing_legacy_prompt():
    external = {
        "prompt": "user request",
        "allowed_tools": [],
        "evaluation_layer": "input_quality",
        "manual_review": ["HIDDEN_CRITERION"],
    }
    prompt = model_prompt(external)
    assert "不调用任何 FateBridge 工具" in prompt
    assert "HIDDEN_CRITERION" not in prompt
    assert model_prompt({"prompt": "user request", "allowed_tools": []}) == (
        "本次运行的工具合同：不调用任何 FateBridge 工具。"
        "请按适用技能核对已确认资料并直接回应当前请求。\n\nuser request"
    )


@pytest.mark.asyncio
async def test_reference_capture_preserves_external_projection_and_legacy_full_payload(
    tmp_path, monkeypatch
):
    import fastmcp
    import fastmcp.client.transports

    from scripts.evaluate_agent import prepare_references

    observed = []

    class FakeClient:
        def __init__(self, transport):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def call_tool(self, tool, arguments, **kwargs):
            observed.append((tool, arguments))
            return SimpleNamespace(
                structured_content={"run_metadata": {"run_id": "fake-reference"}},
                content=[],
                is_error=False,
            )

    monkeypatch.setattr(fastmcp, "Client", FakeClient)
    monkeypatch.setattr(
        fastmcp.client.transports, "StdioTransport", lambda **kwargs: kwargs
    )
    request = {
        "tool": "bazi_career",
        "arguments": {
            "birth_year": 2000,
            "fields": ["core", "career"],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    }
    base = {
        "prompt": "user request",
        "manual_review": ["hidden criterion"],
        "reference_request": request,
    }
    for name, external in (("external", True), ("legacy", False)):
        output = tmp_path / name
        output.mkdir()
        case = {**base, "id": name}
        if external:
            case.update(
                source_case_id="source-case",
                evaluation_layer="interpretation_fidelity",
                split="development",
            )
        await prepare_references([case], output, tmp_path)
        saved = json.loads(
            (output / "reference-payloads" / (name + ".json")).read_text()
        )
        assert saved["arguments"] == observed[-1][1]
        assert saved["is_error"] is False
    external_args, legacy_args = [arguments for _tool, arguments in observed]
    assert external_args["fields"] == ["core", "career"]
    assert external_args["strict_fields"] is True
    assert external_args["include_snapshot_text"] is False
    assert legacy_args["fields"] is None
    assert legacy_args["strict_fields"] is True
    assert legacy_args["include_snapshot_text"] is False


@pytest.mark.parametrize("split", ["development", "holdout"])
def test_external_prepare_only_and_replay_remain_sealed_without_models(
    tmp_path, monkeypatch, split
):
    import scripts.evaluate_agent as evaluator

    root = tmp_path / "root"
    fixture = root / "tests/fixtures"
    fixture.mkdir(parents=True)
    make_suite(fixture / "mingli_bench_v1")
    monkeypatch.setattr(evaluator, "ROOT", root)
    monkeypatch.setattr(evaluator, "freeze_source", lambda target: {})
    monkeypatch.setattr(evaluator, "source_manifest", lambda source: {})

    async def prepare(
        cases, output, source, native_selection, native_working_directory
    ):
        assert "SE_EPHE_PATH" in native_selection
        assert native_working_directory == Path.cwd()
        assert {case["split"] for case in cases} == {split}
        return []

    def prohibited(*args, **kwargs):
        raise AssertionError("Preparation must not resolve or invoke a model")

    monkeypatch.setattr(evaluator, "prepare_references", prepare)
    monkeypatch.setattr(evaluator.subprocess, "run", prohibited)
    monkeypatch.setattr(evaluator.subprocess, "check_output", prohibited)
    monkeypatch.setattr("fatebridge.diagnostics.resolve_codex_cli", prohibited)
    output = tmp_path / "prepared"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_agent",
            "--external-suite",
            "mingli-bench",
            "--split",
            split,
            "--prepare-only",
            "--output",
            str(output),
        ],
    )
    assert evaluator.main() == 0
    report = json.loads((output / "preparation.json").read_text())
    assert report["split"] == split
    assert report["model_invocations"] == 0
    assert report["semantic_acceptance"] == "not_run"
    assert report["dataset_kind"] == "public_competition"
    proposal = json.loads((output / "proposed-execution.json").read_text())
    assert "--external-suite" in proposal["command"]
    assert "--split" in proposal["command"]
    other = "holdout" if split == "development" else "development"
    assert other + "_PROMPT_SENTINEL" not in (output / "case-dataset.json").read_text()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_agent",
            "--external-suite",
            "mingli-bench",
            "--split",
            split,
            "--cases-file",
            str(output / "case-dataset.json"),
            "--prepare-only",
            "--output",
            str(tmp_path / "reprepared"),
        ],
    )
    (fixture / "mingli_bench_v1/cases.json").write_text("mutable source is now corrupt")
    assert evaluator.main() == 0

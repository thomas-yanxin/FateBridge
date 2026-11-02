"""Artifact packaging cannot turn missing evidence into semantic acceptance."""

import hashlib
import json

import pytest

from fatebridge.validation.sukuyo_engineering import (
    Artifact,
    Requirement,
    Selection,
    build_engineering_annex,
)


def artifact(tmp_path, name, data):
    path = tmp_path / name
    raw = json.dumps(data, ensure_ascii=False).encode()
    path.write_bytes(raw)
    return Artifact(path, hashlib.sha256(raw).hexdigest(), "frozen-test-version")


def prepared(tmp_path):
    calculation = artifact(tmp_path, "calc.json", {"candidate": None, "rows": [1, 2]})
    evidence = artifact(
        tmp_path, "evidence.json", {"a/b": {"~key": [None, {"adverse": True}]}}
    )
    requirements = [
        Requirement("r1", "完整原问题的要求", (Selection(evidence, "/a~1b/~0key"),)),
        Requirement("r2", "未取得原件", unavailable_reason="尚无具名原件目标图"),
    ]
    return calculation, evidence, requirements


def test_full_subtree_null_adverse_question_and_versions_are_retained(tmp_path):
    calculation, _, requirements = prepared(tmp_path)
    question = "  整题／所有分支？\n保留错误前提157，不改题。 "
    result = build_engineering_annex(question, calculation, requirements)
    assert result["question"] == question
    assert result["calculation"]["value"] == {"candidate": None, "rows": [1, 2]}
    assert result["requirements"][0]["evidence"][0]["value"] == [
        None,
        {"adverse": True},
    ]
    assert result["requirements"][1]["status"] == "unavailable"
    assert result["binding_verified"]
    assert result["evidence_complete"] is False
    assert result["semantic_verdict"] == "not_assessed"
    assert result["real_world_efficacy"] == "not_assessed"
    assert result["artifacts"][0]["source_version"] == "frozen-test-version"


def test_empty_pointer_selects_whole_document_and_explicit_null_is_available(tmp_path):
    calculation, evidence, _ = prepared(tmp_path)
    result = build_engineering_annex(
        "整题",
        calculation,
        [
            Requirement("root", "全文", (Selection(evidence),)),
            Requirement("null", "空值", (Selection(evidence, "/a~1b/~0key/0"),)),
        ],
    )
    assert result["evidence_complete"]
    assert result["requirements"][1]["status"] == "available"
    assert result["requirements"][1]["evidence"][0]["value"] is None


@pytest.mark.parametrize(
    "pointer",
    ["missing", "/absent", "/a~2b", "/a~1b/~0key/01", "/a~1b/~0key/-", "/a~1b/~0key/9"],
)
def test_missing_or_noncanonical_pointer_is_rejected(tmp_path, pointer):
    calculation, evidence, _ = prepared(tmp_path)
    with pytest.raises((KeyError, ValueError)):
        build_engineering_annex(
            "整题",
            calculation,
            [Requirement("r", "要求", (Selection(evidence, pointer),))],
        )


@pytest.mark.parametrize("kind", ["consultation", "", None])
def test_ordinary_consultation_cannot_implicitly_attach_repository_history(
    tmp_path, kind
):
    calculation, _, requirements = prepared(tmp_path)
    with pytest.raises(ValueError):
        build_engineering_annex("整题", calculation, requirements, request_kind=kind)


def test_drift_and_unbound_version_fail_closed(tmp_path):
    calculation, evidence, requirements = prepared(tmp_path)
    evidence.path.write_text("{}")
    with pytest.raises(ValueError, match="SHA"):
        build_engineering_annex("整题", calculation, requirements)
    bad = Artifact(calculation.path, calculation.sha256, "")
    with pytest.raises(ValueError):
        build_engineering_annex("整题", bad, requirements)


def test_ambiguous_or_absent_requirements_do_not_pass(tmp_path):
    calculation, evidence, requirements = prepared(tmp_path)
    invalid = [
        [],
        [requirements[0], requirements[0]],
        [Requirement("r", "要求")],
        [Requirement("r", "要求", (Selection(evidence),), unavailable_reason="缺")],
    ]
    for rows in invalid:
        with pytest.raises(ValueError):
            build_engineering_annex("整题", calculation, rows)


def test_conflicting_expected_identity_for_same_path_is_rejected(tmp_path):
    calculation, evidence, _ = prepared(tmp_path)
    wrong = Artifact(evidence.path, "0" * 64, evidence.source_version)
    with pytest.raises(ValueError):
        build_engineering_annex(
            "整题",
            calculation,
            [Requirement("r", "要求", (Selection(evidence), Selection(wrong)))],
        )


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}'])
def test_ambiguous_json_bytes_are_not_silently_normalized(tmp_path, raw):
    path = tmp_path / "ambiguous.json"
    path.write_bytes(raw)
    source = Artifact(path, hashlib.sha256(raw).hexdigest(), "test")
    with pytest.raises(ValueError):
        build_engineering_annex(
            "整题", source, [Requirement("r", "要求", (Selection(source),))]
        )


def test_one_read_per_path_and_all_later_selectors_use_that_same_read(
    tmp_path, monkeypatch
):
    calculation, evidence, requirements = prepared(tmp_path)
    from pathlib import Path

    original = Path.read_bytes
    reads = []

    def read_once(path):
        reads.append(path)
        assert reads.count(path) == 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    requirements.append(Requirement("whole", "再取全文", (Selection(evidence),)))
    build_engineering_annex("整题", calculation, requirements)
    assert len(reads) == 2

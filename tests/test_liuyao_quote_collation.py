"""Same-edition quoted words, immutable corrections and remaining fire gaps."""

import hashlib
import json
import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from scripts.liuyao_quote_collation import apply_quote_errata

BASE = Path(__file__).parent / "fixtures/liuyao_quote_collation_v43"
TRANSCRIPTION = json.loads((BASE / "transcription.json").read_text())
BEFORE = json.loads((BASE / "selected-clauses-before.json").read_text())
ERRATA = json.loads((BASE / "errata.json").read_text())


@pytest.mark.parametrize(
    "case", BEFORE["all_selected_clauses"], ids=lambda c: c["file"] + c["path"]
)
def test_every_selected_quotation_is_an_exact_same_edition_excerpt(case):
    profile = json.loads(
        files("fatebridge.data").joinpath("classical", case["file"]).read_text()
    )
    clause = profile
    for part in case["path"].strip("/").split("/"):
        clause = clause[int(part)] if isinstance(clause, list) else clause[part]
    assert any(
        clause["quote"] in passage["text"] for passage in TRANSCRIPTION["passages"]
    ), clause


def test_the_three_original_failures_and_all_material_hashes_are_retained():
    failed = [
        c
        for c in BEFORE["all_selected_clauses"]
        if not c["matches_frozen_transcription"]
    ]
    assert len(failed) == 3
    assert {c["quote"] for c in failed} == {
        c["old_quote"] for c in ERRATA["corrections"]
    }
    freeze = json.loads((BASE / "freeze.json").read_text())
    for relative, expected in freeze["files_sha256"].items():
        assert hashlib.sha256((BASE / relative).read_bytes()).hexdigest() == expected


def test_quotation_repairs_do_not_invent_the_missing_fire_positions():
    from fatebridge.core.liuyao_stages import STAGES, stage_knowledge

    assert STAGES["火"] == {"寅": "长生", "戌": "墓"}
    knowledge = stage_knowledge()
    assert knowledge["missing_stages"]["火"] == ["帝旺", "绝"]
    assert knowledge["table_complete"] is False
    assert knowledge["adjudication"] == "phase_positions_not_efficacy"


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_unapproved_transcription_cannot_become_a_generated_quote(
    rewrite_manifest, tmp_path
):
    copied = tmp_path / "tests/fixtures/liuyao_quote_collation_v43"
    shutil.copytree(BASE, copied)
    transcription = copied / "transcription.json"
    transcription.write_text(transcription.read_text() + " ")
    if rewrite_manifest:
        manifest = copied / "freeze.json"
        data = json.loads(manifest.read_text())
        data["files_sha256"]["transcription.json"] = hashlib.sha256(
            transcription.read_bytes()
        ).hexdigest()
        manifest.write_text(json.dumps(data))
    original = BASE.parent / "liuyao_stages_v15/profile.json"
    with pytest.raises(ValueError, match="Frozen same-edition quotation"):
        apply_quote_errata(
            json.loads(original.read_text()),
            root=tmp_path,
            original=original,
            artifact="liuyao-stages-v15.json",
        )

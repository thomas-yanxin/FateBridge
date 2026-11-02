"""Original source retention cannot substitute for changed reference data."""

import hashlib
from pathlib import Path

import pytest

from scripts.historical_source_identity import HistoricalSources

ARCHIVE = (
    Path(__file__).parent / "fixtures/architecture_refactor_v1/source-originals.json.gz"
)
TT_MODEL_SHA = "6f568f1633d5a1232937b2e1040479d60a222218ffecb543bb7dcdd4b5c356fa"


@pytest.mark.parametrize("present", [False, True])
def test_original_source_remains_hash_checked_after_retirement_or_edit(
    tmp_path, present
):
    path = tmp_path / "scripts/astrodice_tt_models.py"
    if present:
        path.parent.mkdir()
        path.write_text("different_current_implementation = True\n")
        assert hashlib.sha256(path.read_bytes()).hexdigest() != TT_MODEL_SHA
    assert HistoricalSources(tmp_path, archive=ARCHIVE).matches(path, TT_MODEL_SHA)


def test_reference_data_must_match_its_actual_bytes(tmp_path):
    sources = HistoricalSources(tmp_path, archive=ARCHIVE)
    path = tmp_path / "reference.json"
    path.write_bytes(b'{"value": 1}')
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert sources.matches(path, expected)
    path.write_bytes(b'{"value": 2}')
    assert not sources.matches(path, expected)
    assert not sources.matches(path, TT_MODEL_SHA)


def test_source_archive_tampering_cannot_rebind_original_identity(tmp_path):
    path = tmp_path / "source-originals.json.gz"
    path.write_bytes(ARCHIVE.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Frozen original source archive changed"):
        HistoricalSources(tmp_path, archive=path)

"""Portable boundary sources, complete cohorts and preserved uncertainty."""

import ast
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.astronomy import solar_term_reference as solar_source
from scripts.ren import ren_boundary_reference as source


@pytest.fixture(scope="module")
def reference():
    return source.load_ren_boundary_reference()


def test_reproduced_cohort_keeps_original_labels_and_interval_uncertainty(reference):
    rows = reference.packet.seconds.rows
    assert len(rows) == 19248 and len(reference.minutes.rows) == 9744
    assert len(reference.packet.seconds.reference_clock_sofa_checks) == 233
    uncertain = tuple(r for r in rows if r.inside_root_bracket)
    assert tuple(r.id for r in uncertain) == ("1952-立秋-floor",)
    row = uncertain[0]
    root = next(
        r for r in reference.solar.rows if r.year == row.year and r.index == row.index
    )
    assert row.input_jd_tt == root.bracket_tt[0] <= root.jd_tt
    assert row.expected.current_term == "大暑"
    assert reference.packet.seconds.new_independent_physical_events == 0


def test_packet_retains_three_historical_original_input_identity_differences(reference):
    observations = reference.packet.legacy_identity_observations
    assert {r["source"] for r in observations} == {
        "guard_freeze",
        "boundary_protocol",
        "minute_protocol",
    }
    assert all(r["matches_original"] is False for r in observations)
    assert all(
        r["original_expected_sha256"] != r["observed_sha256"] for r in observations
    )


def test_captured_producer_and_table_helper_import_no_candidate(reference):
    for text in [reference.packet.producer_source, reference.packet.helper_source]:
        tree = ast.parse(text)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(name.name.split(".")[0] for name in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        assert "fatebridge" not in imports


@pytest.mark.parametrize(
    "fault",
    [
        "producer",
        "helper",
        "source",
        "prune_seconds",
        "prune_minutes",
        "reorder",
        "uncertainty",
        "solar_source",
    ],
)
def test_coordinated_outer_checksum_edit_keeps_inner_source_and_cohort_checks(
    fault, tmp_path, monkeypatch
):
    packet = json.loads(gzip.decompress(source.REFERENCE_PATH.read_bytes()))
    if fault == "producer":
        packet["producer_source"] += "\n# changed\n"
    elif fault == "helper":
        packet["helper_source"] += "\n# changed\n"
    elif fault == "source":
        packet["source_inputs"]["calendar"]["text"] += "\n"
    elif fault == "prune_seconds":
        packet["seconds"]["rows"].pop()
    elif fault == "prune_minutes":
        item = packet["source_inputs"]["minute_data"]
        data = json.loads(item["text"])
        data["rows"].pop()
        item["text"] = json.dumps(data)
        item["sha256"] = hashlib.sha256(item["text"].encode()).hexdigest()
    elif fault == "reorder":
        rows = packet["seconds"]["rows"]
        rows[0], rows[1] = rows[1], rows[0]
    elif fault == "uncertainty":
        row = next(r for r in packet["seconds"]["rows"] if r["id"] == "1952-立秋-floor")
        row["inside_root_bracket"] = False
        packet["seconds"]["inside_root_bracket_ids"] = []
    else:
        packet["solar_reference_sha256"] = "changed"
    packed = gzip.compress(json.dumps(packet).encode(), mtime=0)
    path = tmp_path / "changed.json.gz"
    path.write_bytes(packed)
    monkeypatch.setattr(source, "REFERENCE_SHA256", hashlib.sha256(packed).hexdigest())
    with pytest.raises(ValueError):
        source.load_ren_boundary_reference(path)


def test_portable_reference_needs_only_two_readers_and_two_current_data_files(tmp_path):
    root = Path(__file__).resolve().parents[2]
    names = [
        "scripts/astronomy/solar_term_reference.py",
        "scripts/ren/ren_boundary_reference.py",
        str(solar_source.REFERENCE_PATH.relative_to(root)),
        str(source.REFERENCE_PATH.relative_to(root)),
    ]
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    code = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(tmp_path)!r})",
            "from scripts.ren.ren_boundary_reference import REFERENCE_PATH, load_ren_boundary_reference",
            "r = load_ren_boundary_reference()",
            "assert len(r.packet.seconds.rows) == 19248 and len(r.minutes.rows) == 9744",
            f"assert str(REFERENCE_PATH).startswith({str(tmp_path)!r})",
            "assert not any(n == 'fatebridge' or n.startswith('fatebridge.') for n in sys.modules)",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

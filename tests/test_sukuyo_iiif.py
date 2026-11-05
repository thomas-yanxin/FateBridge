"""Real source locators, incompatible schemas and offline delivery boundaries."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_engineering import Artifact
from fatebridge.validation.sukuyo_iiif import inspect_iiif_manifest

FIXTURES = Path(__file__).parent / "data/sukuyo-iiif-manifests-v1"
REFERENCE = json.loads((FIXTURES / "reference.json").read_bytes())
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/inspect_sukuyo_iiif.py"


def artifact(path):
    return Artifact(path, hashlib.sha256(path.read_bytes()).hexdigest(), "test source")


def saved(tmp_path, value):
    path = tmp_path / "source.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return artifact(path)


def source(version):
    case = REFERENCE["cases"][0 if version == 2 else 2]
    return json.loads((FIXTURES / case["file"]).read_bytes())


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_entire_real_manifest_and_all_precode_literal_expectations(case):
    path = FIXTURES / case["file"]
    assert path.stat().st_size == case["bytes"]
    result = inspect_iiif_manifest(
        Artifact(path, case["sha256"], case["declared_source_version"])
    )
    assert result["presentation_version"] == case["presentation_version"]
    assert result["canvas_occurrences"] == case["canvas_occurrences"]
    assert result["unique_canvas_ids"] == case["unique_canvases"]
    assert result["image_annotation_occurrences"] == case["painting_image_occurrences"]
    assert (
        result["exact_string_target_mismatches"]
        == case["exact_string_target_mismatches"]
    )
    assert result["binding"]["value"] == json.loads(path.read_bytes())
    first = result["canvases"][0]["annotations"][0]
    assert first["image_uri"] == case["first_image_uri"]
    assert (
        list(first["declared_image_dimensions"].values())
        == case["first_declared_image_dimensions"]
    )
    assert all(
        row["image_bytes_status"] == "not_fetched"
        and row["actual_downloaded_pixel_dimensions"] is None
        for canvas in result["canvases"]
        for row in canvas["annotations"]
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.pop("items"),
        lambda d: d.update({"sequences": []}),
        lambda d: d.update({"@context": "https://example.org/unknown-context"}),
        lambda d: d.update(
            {
                "@context": [
                    "http://iiif.io/api/presentation/2/context.json",
                    "http://iiif.io/api/presentation/3/context.json",
                ]
            }
        ),
        lambda d: d["items"][0]["items"][0].pop("items"),
        lambda d: d["items"][0].update({"width": True}),
        lambda d: d["items"][0]["items"][0]["items"][0].update({"body": []}),
    ],
)
def test_unsupported_or_missing_structure_is_not_a_silent_empty_book(tmp_path, change):
    data = source(3)
    change(data)
    with pytest.raises(ValueError):
        inspect_iiif_manifest(saved(tmp_path, data))


def test_multiple_sequences_and_repeated_canvas_are_not_lost_or_new_witnesses(tmp_path):
    data = source(2)
    sequence = copy.deepcopy(data["sequences"][0])
    sequence["canvases"] = sequence["canvases"][:1]
    alternate = copy.deepcopy(sequence)
    alternate["@id"] += "-alternate"
    data["sequences"] = [sequence, alternate]
    result = inspect_iiif_manifest(saved(tmp_path, data))
    assert result["canvas_set_count"] == 2
    assert result["canvas_occurrences"] == 2
    assert result["unique_canvas_ids"] == 1
    assert [row["sequence_id"] for row in result["canvases"]] == [
        sequence["@id"],
        alternate["@id"],
    ]


def test_exact_id_differences_are_preserved_without_renumbering():
    result = inspect_iiif_manifest(artifact(FIXTURES / REFERENCE["cases"][0]["file"]))
    first = result["canvases"][0]
    assert first["id"].endswith("/canvas/0")
    assert first["annotations"][0]["target"].endswith("/canvas/1")
    assert result["exact_string_target_mismatches"] == 40
    assert result["binding"]["value"]["sequences"][0]["canvases"][0]["@id"].endswith(
        "/canvas/0"
    )


def test_nonstring_target_kept_uncompared_instead_of_certified_or_discarded(tmp_path):
    data = source(3)
    canvas = data["items"][0]
    target = {
        "type": "SpecificResource",
        "source": canvas["id"],
        "selector": {"type": "FragmentSelector", "value": "xywh=1,2,3,4"},
    }
    canvas["items"][0]["items"][0]["target"] = target
    result = inspect_iiif_manifest(saved(tmp_path, data))
    row = result["canvases"][0]["annotations"][0]
    assert row["target"] == target
    assert row["exact_string_target_comparison"] == "not_compared"
    assert result["non_string_targets_not_compared"] == 1


def test_small_requested_rendition_is_not_certified_by_manifest_large_dimensions():
    result = inspect_iiif_manifest(artifact(FIXTURES / REFERENCE["cases"][2]["file"]))
    first = result["canvases"][0]["annotations"][0]
    assert "/full/2000,/" in first["image_uri"]
    assert first["declared_image_dimensions"] == {"width": 6480, "height": 4320}
    assert first["actual_downloaded_pixel_dimensions"] is None
    assert first["image_bytes_status"] == "not_fetched"


@pytest.mark.parametrize("literal", ['{"id":1,"id":2}', '{"x":NaN}', '{"x":1e999}'])
def test_ambiguous_or_nonfinite_json_not_bound_as_source(tmp_path, literal):
    path = tmp_path / "source.json"
    path.write_text(literal)
    with pytest.raises(ValueError):
        inspect_iiif_manifest(artifact(path))


def test_wrong_source_identity_rejected(tmp_path):
    current = saved(tmp_path, source(3))
    with pytest.raises(ValueError, match="SHA"):
        inspect_iiif_manifest(Artifact(current.path, "0" * 64, "test source"))


def test_actual_cli_keeps_full_source_and_never_overwrites_first_output(tmp_path):
    current = artifact(FIXTURES / REFERENCE["cases"][2]["file"])
    output = tmp_path / "inspection.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--manifest",
        str(current.path),
        "--sha256",
        current.sha256,
        "--source-version",
        current.source_version,
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    raw = output.read_bytes()
    assert json.loads(raw) == inspect_iiif_manifest(current)
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0
    assert output.read_bytes() == raw


def test_actual_cli_bad_sha_cannot_publish_partial_output(tmp_path):
    path = FIXTURES / REFERENCE["cases"][2]["file"]
    output = tmp_path / "must-not-exist.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(path),
            "--sha256",
            "0" * 64,
            "--source-version",
            "test source",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert not output.exists()


@pytest.mark.parametrize(
    "kind", ["Choice", "missing", "Unknown", ["Image"], 1, None, "Text"]
)
def test_unsupported_body_cannot_be_silently_counted_as_nonimage(tmp_path, kind):
    data = source(3)
    data["items"] = data["items"][:1]
    annotation = data["items"][0]["items"][0]["items"][0]
    image = copy.deepcopy(annotation["body"])
    if kind == "Choice":
        annotation["body"] = {"type": "Choice", "items": [image]}
    elif kind == "missing":
        annotation["body"].pop("type")
    else:
        annotation["body"]["type"] = kind
    with pytest.raises(ValueError, match="body type unsupported"):
        inspect_iiif_manifest(saved(tmp_path, data))


def test_mixed_choice_cannot_publish_partial_image_count(tmp_path):
    data = source(3)
    data["items"] = data["items"][:2]
    annotation = data["items"][0]["items"][0]["items"][0]
    annotation["body"] = {"type": "Choice", "items": [annotation["body"]]}
    with pytest.raises(ValueError, match="body type unsupported"):
        inspect_iiif_manifest(saved(tmp_path, data))


def test_actual_cli_choice_does_not_publish_a_zero_image_receipt(tmp_path):
    data = source(3)
    data["items"] = data["items"][:1]
    annotation = data["items"][0]["items"][0]["items"][0]
    annotation["body"] = {"type": "Choice", "items": [annotation["body"]]}
    current = saved(tmp_path, data)
    output = tmp_path / "must-not-exist.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(current.path),
            "--sha256",
            current.sha256,
            "--source-version",
            current.source_version,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "body type unsupported" in completed.stderr
    assert not output.exists()

"""Inspect frozen IIIF source locators without certifying manuscript identity."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.validation.sukuyo_artifacts import Artifact, read_artifact

CONTEXTS = {
    "http://iiif.io/api/presentation/2/context.json": 2,
    "https://iiif.io/api/presentation/2/context.json": 2,
    "http://iiif.io/api/presentation/3/context.json": 3,
    "https://iiif.io/api/presentation/3/context.json": 3,
}


def _object(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError("IIIF embedded object required")
    return value


def _list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise ValueError("IIIF embedded list required; missing is not zero")
    return value


def _identifier(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("IIIF identifier required")
    return value


def _dimensions(value: dict[str, Any]) -> dict[str, int | None]:
    result = {}
    for key in ("width", "height"):
        dimension = value.get(key)
        if dimension is not None and (type(dimension) is not int or dimension <= 0):
            raise ValueError("IIIF declared dimensions must be positive integers")
        result[key] = dimension
    return result


def _version(data: dict[str, Any]) -> int:
    contexts = data.get("@context")
    if isinstance(contexts, str):
        contexts = [contexts]
    versions = {
        CONTEXTS[item]
        for item in _list(contexts)
        if isinstance(item, str) and item in CONTEXTS
    }
    if len(versions) != 1:
        raise ValueError("IIIF Presentation version unknown or ambiguous")
    version = versions.pop()
    if version == 2:
        if data.get("@type") != "sc:Manifest" or "items" in data or "type" in data:
            raise ValueError("IIIF version2 manifest structure inconsistent")
    elif data.get("type") != "Manifest" or "sequences" in data or "@type" in data:
        raise ValueError("IIIF version3 manifest structure inconsistent")
    return version


def _annotations(canvas: dict[str, Any], version: int) -> list[dict[str, Any]]:
    if version == 2:
        return [_object(value) for value in _list(canvas.get("images"))]
    annotations: list[dict[str, Any]] = []
    for value in _list(canvas.get("items")):
        page = _object(value)
        if page.get("type") != "AnnotationPage":
            raise ValueError("IIIF embedded AnnotationPage required")
        # A referenced page cannot be inspected offline as an empty page.
        annotations.extend(_object(row) for row in _list(page.get("items")))
    return annotations


def inspect_iiif_manifest(artifact: Artifact) -> dict[str, Any]:
    """Read one fingerprinted JSON once, retaining full data and exact locators.

    This is a local engineering inspector for embedded Presentation2/3 image
    manifests, not a complete JSON-LD validator or an image downloader. Linked
    pages, Choice/list bodies and unsupported structural forms fail explicitly.
    Other source fields remain available in the complete bound manifest.
    """
    binding, _ = read_artifact(artifact)
    data = _object(binding["value"])
    version = _version(data)
    id_key = "@id" if version == 2 else "id"
    manifest_id = _identifier(data.get(id_key))
    sets: list[tuple[str | None, list[Any]]]
    if version == 2:
        sets = [
            (_identifier(row.get("@id")), _list(row.get("canvases")))
            for row in (_object(value) for value in _list(data.get("sequences")))
        ]
    else:
        sets = [(None, _list(data.get("items")))]
    canvases: list[dict[str, Any]] = []
    for set_ordinal, (sequence_id, values) in enumerate(sets, 1):
        for ordinal, value in enumerate(values, 1):
            canvas = _object(value)
            expected_type = "sc:Canvas" if version == 2 else "Canvas"
            type_key = "@type" if version == 2 else "type"
            if canvas.get(type_key) != expected_type:
                raise ValueError("IIIF Canvas structure required")
            canvas_id = _identifier(canvas.get(id_key))
            annotations = []
            for annotation_ordinal, annotation in enumerate(
                _annotations(canvas, version), 1
            ):
                target_key = "on" if version == 2 else "target"
                if target_key not in annotation:
                    raise ValueError("IIIF annotation target missing")
                target = annotation[target_key]
                if isinstance(target, str):
                    _identifier(target)
                    comparison = "equal" if target == canvas_id else "different"
                else:
                    # SpecificResource/list targets are kept, not declared bad.
                    comparison = "not_compared"
                body = _object(annotation.get("resource" if version == 2 else "body"))
                body_type = body.get(type_key)
                if body_type not in ("dctypes:Image", "Image"):
                    raise ValueError(
                        "IIIF body type unsupported; embedded Image required"
                    )
                is_image = body_type in ("dctypes:Image", "Image")
                image_id = _identifier(body.get(id_key)) if is_image else None
                annotations.append(
                    {
                        "ordinal": annotation_ordinal,
                        "id": deepcopy(annotation.get(id_key)),
                        "motivation": deepcopy(annotation.get("motivation")),
                        "target": deepcopy(target),
                        "exact_string_target_comparison": comparison,
                        "body_type": deepcopy(body_type),
                        "is_image": is_image,
                        "image_uri": image_id,
                        "declared_image_dimensions": _dimensions(body),
                        "service": deepcopy(body.get("service")),
                        "actual_downloaded_pixel_dimensions": None,
                        "image_bytes_status": "not_fetched",
                        "raw_annotation": deepcopy(annotation),
                    }
                )
            canvases.append(
                {
                    "set_ordinal": set_ordinal,
                    "sequence_id": sequence_id,
                    "ordinal_in_set": ordinal,
                    "id": canvas_id,
                    "label": deepcopy(canvas.get("label")),
                    "declared_canvas_dimensions": _dimensions(canvas),
                    "annotations": annotations,
                }
            )
    records = [row for canvas in canvases for row in canvas["annotations"]]
    return {
        "schema": "sukuyo_iiif_source_locators_v1",
        "binding": binding,
        "presentation_version": version,
        "manifest_id": manifest_id,
        "canvas_set_count": len(sets),
        "canvas_occurrences": len(canvases),
        "unique_canvas_ids": len({row["id"] for row in canvases}),
        "image_annotation_occurrences": sum(row["is_image"] for row in records),
        "exact_string_target_mismatches": sum(
            row["exact_string_target_comparison"] == "different" for row in records
        ),
        "non_string_targets_not_compared": sum(
            row["exact_string_target_comparison"] == "not_compared" for row in records
        ),
        "canvases": canvases,
        "evidence_status": "manifest_inspected_only",
        "scope": (
            "Counts are declared digital occurrences, not manuscripts, physical leaves "
            "or independent observations. Target differences are exact-string "
            "diagnostics, not a verdict on all annotation semantics. Image URIs and "
            "declared dimensions do not establish actual fetched resolution. Full "
            "parsed source data retained; no network, glyph, identity, calendar "
            "or prediction certification."
        ),
    }

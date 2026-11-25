"""Select inline facts within the serialized response character budget."""

from pydantic import JsonValue

from fatebridge.utils.errors import ParameterError
from fatebridge.utils.formatting import format_json_response

INLINE_RECEIPT_FIELD_LIMIT_CHARS = 512
INLINE_FIELD_PRIORITY = (
    "summary",
    "analysis_context",
    "status",
    "comprehensive_summary",
)


def overflow_response(
    payload: dict[str, JsonValue],
    delivery: dict[str, JsonValue],
    selected_fields: list[str] | None,
    compact: bool,
    original_chars: int,
    response_char_limit: int,
) -> dict[str, JsonValue]:
    def fits(candidate: dict[str, JsonValue]) -> bool:
        return (
            len(format_json_response(candidate, compact=compact)) <= response_char_limit
        )

    metadata = payload.get("run_metadata")
    deferred_metadata: list[JsonValue] = []
    if isinstance(metadata, dict):
        metadata = dict(metadata)
        for key in ("calculation_evidence", "runtime"):
            value = metadata.get(key)
            if (
                isinstance(value, dict)
                and len(format_json_response(value, compact=compact))
                > INLINE_RECEIPT_FIELD_LIMIT_CHARS
            ):
                path = f"run_metadata.{key}"
                summary: dict[str, JsonValue] = {"delivery_path": path}
                if key == "runtime":
                    ephemeris = value.get("ephemeris")
                    files = (
                        ephemeris.get("files") if isinstance(ephemeris, dict) else None
                    )
                    if isinstance(files, list):
                        summary["ephemeris_files_count"] = len(files)
                    else:
                        pass
                else:
                    pass
                metadata[key] = summary
                deferred_metadata.append(path)
            else:
                pass
    else:
        pass

    fields = [key for key in payload if key != "run_metadata"]
    if (
        deferred_metadata
        and original_chars
        - len(format_json_response(payload["run_metadata"], compact=compact))
        <= response_char_limit
    ):
        reference: dict[str, JsonValue] = {
            **delivery,
            "deferred_fields": list(deferred_metadata),
        }
        candidate: dict[str, JsonValue] = {
            **payload,
            "run_metadata": metadata,
            "result_delivery": reference,
        }
        if fits(candidate):
            return candidate
        else:
            pass
        reference = {
            key: value
            for key, value in reference.items()
            if key
            not in {
                "available_fields",
                "total_bytes",
                "page_chars",
                "rest_manifest_path",
            }
        }
        reference["compact_reference"] = True
        candidate["result_delivery"] = reference
        for drop in ((), ("first_page_uri",), ("file_path", "file_payload_path")):
            for key in drop:
                reference.pop(key)
            if fits(candidate):
                return candidate
            else:
                pass
        # note (budget): Deferred receipt fields can only come from a receipt object.
        assert isinstance(metadata, dict)
        receipt = dict(metadata)
        paths = list(deferred_metadata)
        candidate["run_metadata"] = receipt
        reference["deferred_fields"] = paths
        for key in ("provenance", "determinism"):
            if key in receipt:
                receipt.pop(key)
                paths.append(f"run_metadata.{key}")
                if fits(candidate):
                    return candidate
                else:
                    pass
            else:
                pass
    else:
        pass

    deferred: list[JsonValue] = [*fields, *deferred_metadata]
    delivery["deferred_fields"] = deferred
    output: dict[str, JsonValue] = {}
    if "run_metadata" in payload:
        output["run_metadata"] = metadata
    output["result_delivery"] = delivery
    is_output_within_budget = fits(output)
    if not is_output_within_budget and isinstance(metadata, dict):
        for key in ("provenance", "determinism"):
            if key in metadata:
                metadata.pop(key)
                deferred.append(f"run_metadata.{key}")
                is_output_within_budget = fits(output)
                if is_output_within_budget:
                    break
                else:
                    pass
            else:
                pass
    else:
        pass
    if not is_output_within_budget:
        raise ParameterError(
            "回执超过响应预算，请增大 response_char_limit",
            [{"path": "response_char_limit", "code": "response_limit_too_small"}],
        )
    else:
        pass
    for key in dict.fromkeys([*INLINE_FIELD_PRIORITY, *fields]):
        if key not in fields:
            continue
        else:
            pass
        paths = [name for name in deferred if name != key]
        candidate = {
            **output,
            key: payload[key],
            "result_delivery": {**delivery, "deferred_fields": paths},
        }
        if fits(candidate):
            output, deferred = candidate, paths
        else:
            pass

    projected_roots = {
        path.partition(".")[0] for path in selected_fields or () if "." in path
    }
    projected_roots.difference_update(selected_fields or ())
    for key in fields:
        value = payload[key]
        if key in output or not isinstance(value, dict):
            continue
        else:
            pass
        nested = value.get("first_view")
        if len(value) == 1 and isinstance(nested, dict):
            view, prefix = nested, f"{key}.first_view"
        elif key in projected_roots:
            view, prefix = value, key
        else:
            continue
        parent_paths = [name for name in deferred if name != key]
        selected: dict[str, JsonValue] = {}
        for child, fact in view.items():
            trial = {**selected, child: fact}
            paths = [
                *parent_paths,
                *(f"{prefix}.{name}" for name in view if name not in trial),
            ]
            candidate = {
                **output,
                key: {"first_view": trial} if view is nested else trial,
                "result_delivery": {**delivery, "deferred_fields": paths},
            }
            if fits(candidate):
                selected, output, deferred = trial, candidate, paths
            else:
                pass
    return output

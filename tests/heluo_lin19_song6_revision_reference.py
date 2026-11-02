"""R81 source-file-derived bindings; original R76/R77 evidence stays frozen."""

import json
from pathlib import Path

from tests.heluo_guan_shi_revision_reference import (
    rebind_r84_counts,
    rebind_r84_metadata,
)
from tests.heluo_song_glyph_revision_reference import rebind_r82_metadata
from tests.heluo_source_revision_reference import (
    rebind_reviewed_registry_counts as rebind_r77_counts,
)
from tests.heluo_source_revision_reference import (
    rebind_reviewed_source_metadata as rebind_r77_metadata,
)

REVISION = json.loads(
    (
        Path(__file__).parent
        / "fixtures/heluo_lin19_song6_v1/reference-metadata-migration-v1.json"
    ).read_bytes()
)
ADDENDUM = json.loads(
    (
        Path(__file__).parent
        / "fixtures/heluo_lin19_song6_v1/test-repair-addendum-v1.json"
    ).read_bytes()
)


def rebind_r81_metadata(value, parent=None, path=()):
    if isinstance(value, dict):
        pairs = (
            REVISION["text_provenance_pairs"]
            if parent == "text_provenance"
            else (
                REVISION["source_record_pairs"].get(value.get("key"), {})
                if parent == "source_records"
                else REVISION["provenance_pairs"] if parent == "provenance" else {}
            )
        )
        result = {}
        for key, item in value.items():
            if key in pairs:
                before, after = pairs[key]
                assert item == before, (parent, key, item)
                result[key] = after
            else:
                result[key] = rebind_r81_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r81_metadata(item, parent, path + (index,))
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        if path not in {
            ("rendered_text",),
            ("snapshot_text",),
            ("snapshot_export", "export_text"),
        } and not (
            len(path) == 4
            and path[:2] == ("snapshot_export", "sections")
            and isinstance(path[2], int)
            and path[3] == "content"
        ):
            return value
        # Replace entire independently specified metadata lines only. A hash,
        # version, scope or corpus ID embedded in body/notes remains literal.
        pairs = dict(REVISION["exact_metadata_footer_pairs"])
        result = []
        for line in value.splitlines(keepends=True):
            body = line.rstrip("\r\n")
            result.append(pairs.get(body, body) + line[len(body) :])
        return "".join(result)
    return value


def rebind_r81_counts(value, parent=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if parent == "coverage" and key in REVISION["coverage_field_pairs"]:
                before, after = REVISION["coverage_field_pairs"][key]
                assert item == before, (key, item)
                result[key] = after
            else:
                result[key] = rebind_r81_counts(item, key)
        return result
    if isinstance(value, list):
        return [rebind_r81_counts(item, parent) for item in value]
    return value


def rebind_reviewed_source_metadata(value):
    return rebind_r84_metadata(
        rebind_r82_metadata(rebind_r81_metadata(rebind_r77_metadata(value)))
    )


def rebind_reviewed_registry_counts(value):
    return rebind_r84_counts(rebind_r81_counts(rebind_r77_counts(value)))

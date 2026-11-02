"""R82 literal, source-first bindings; do not derive expected values from code."""

import copy
import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures/heluo_song_native_glyphs_v1"
REVISION = json.loads((FIXTURE / "legacy-source-migration-reference.json").read_bytes())
PROPOSAL = json.loads((FIXTURE / "source-proposal-reference.json").read_bytes())
OLD_POEMS = json.loads((FIXTURE / "poems-before.json").read_bytes())
NEW_POEMS = json.loads((FIXTURE / "poems-proposed.json").read_bytes())


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def rebind_r82_metadata(value, parent=None, path=()):
    """Change only declared metadata fields and complete metadata footer lines."""
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
                result[key] = copy.deepcopy(after)
            else:
                result[key] = rebind_r82_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r82_metadata(item, parent, path + (index,))
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
        pairs = dict(REVISION["exact_metadata_footer_pairs"])
        return "".join(
            pairs.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
            + line[len(line.rstrip("\r\n")) :]
            for line in value.splitlines(keepends=True)
        )
    return value


def rebind_reviewed_song_readings(readings):
    """Advance the exact historical Song entries, leaving other readings intact."""
    assert readings["poems"] == OLD_POEMS["entries"][-6:]
    assert (
        canonical(readings["poems"]) == REVISION["old_song6_entries_canonical_sha256"]
    )
    result = copy.deepcopy(readings)
    result["poems"] = copy.deepcopy(NEW_POEMS["entries"][-6:])
    assert canonical(result["poems"]) == REVISION["new_song6_entries_canonical_sha256"]
    return result

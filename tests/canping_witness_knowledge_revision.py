"""R99 metadata edge and reviewed literal additions; old knowledge oracles stay."""

import hashlib
import json
from copy import deepcopy

from tests.canping_witness_fixture_compat import ROOT, add_reviewed_selection_witnesses

RAW = (ROOT / "knowledge-catalogue-edge.json").read_bytes()
assert (
    hashlib.sha256(RAW).hexdigest()
    == "2e75a50b728513d15bee7baf3b702579450b2a91e21e4503d333cd0165440576"
)
REVISION = json.loads(RAW)


def rebind_r99_metadata(value, parent=None, path=()):
    if isinstance(value, dict):
        pairs = (
            REVISION["provenance_pairs"]
            if parent == "provenance"
            else (
                REVISION["source_record_pairs"].get(value.get("key"), {})
                if parent == "source_records"
                else {}
            )
        )
        result = {}
        for key, item in value.items():
            if key in pairs:
                before, after = pairs[key]
                assert type(item) is type(before) and item == before, (parent, key)
                result[key] = deepcopy(after)
            elif key == "record":
                result[key] = deepcopy(item)
            else:
                result[key] = rebind_r99_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r99_metadata(item, parent, path + (i,))
            for i, item in enumerate(value)
        ]
    if isinstance(value, str):
        allowed = path in {
            ("rendered_text",),
            ("snapshot_text",),
            ("snapshot_export", "export_text"),
        }
        allowed |= (
            len(path) == 4
            and path[:2] == ("snapshot_export", "sections")
            and isinstance(path[2], int)
            and path[3] == "content"
        )
        if allowed:
            pairs = dict(REVISION["exact_metadata_footer_pairs"])
            return "".join(
                pairs.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
                + line[len(line.rstrip("\r\n")) :]
                for line in value.splitlines(keepends=True)
            )
    return deepcopy(value)


def rebind_r99_knowledge(value):
    result = rebind_r99_metadata(value)
    if result.get("domain") != "canping" or result.get("category") != "text_cells":
        return result
    result["reference_details"]["record"] = add_reviewed_selection_witnesses(
        result["reference_details"]["record"]
    )
    notes = REVISION["ambiguity_notes"].get(result.get("key"))
    if not notes:
        return result
    before = result["lines"]
    assert result["tips"] == before
    after = before[:-1] + notes + before[-1:]
    old_body, new_body = "\n".join(before), "\n".join(after)
    result["lines"], result["tips"] = deepcopy(after), deepcopy(after)

    def replace_text(item, path=()):
        if isinstance(item, dict):
            return {k: replace_text(v, path + (k,)) for k, v in item.items()}
        if isinstance(item, list):
            return [replace_text(v, path + (i,)) for i, v in enumerate(item)]
        if isinstance(item, str):
            allowed = path in {
                ("rendered_text",),
                ("snapshot_text",),
                ("snapshot_export", "export_text"),
            }
            allowed |= (
                len(path) == 4
                and path[:2] == ("snapshot_export", "sections")
                and isinstance(path[2], int)
                and path[3] == "content"
            )
            if allowed and old_body in item:
                assert item.count(old_body) == 1
                return item.replace(old_body, new_body)
        return item

    return replace_text(result)

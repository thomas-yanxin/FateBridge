"""R92 bounded source edge. Original books, tests and numerical facts stay frozen."""

import copy
import hashlib
import json
from pathlib import Path

F = Path(__file__).parent / "fixtures/heluo_shike21_bi8_migration_v1"
R91 = Path(__file__).parent / "fixtures/heluo_shike21_bi8_v1"
REVISION = json.loads((F / "migration-reference.json").read_bytes())
LITERAL = json.loads((F / "reviewed-literals-v2.json").read_bytes())
SOURCE_NAMES = (
    "src/fatebridge/data/heluo/yaoci-collation-v1.json",
    "src/fatebridge/data/heluo/commentary-collation-v1.json",
    "src/fatebridge/data/heluo/poem-collation-v1.json",
    "src/fatebridge/data/knowledge/numerology-sources-v1.json",
)
CURRENT_HEADERS, CURRENT_COMMENTARIES, CURRENT_POEMS, CURRENT_CATALOGUE = (
    json.loads((R91 / "proposed-final" / n).read_bytes()) for n in SOURCE_NAMES
)


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


LITERAL_FIELDS = {
    "detail",
    "yaoci",
    "shige",
    "reading_notes",
    "header_reading_notes",
    "commentary_reading_notes",
    "poem_sections",
    "commentary_sections",
    "inherited_detail",
    "inherited_shige",
    "inherited_yaoci",
    "lines",
    "tips",
    "text",
    "answer",
    "notes",
    "number",
    "chart",
    "four_pillars",
    "calendar_context",
    "dayun",
    "judge",
}


def rebind_r92_metadata(value, parent=None, path=()):
    if isinstance(value, dict):
        pairs = (
            REVISION["text_provenance_pairs"]
            if parent == "text_provenance"
            else (
                REVISION["provenance_pairs"]
                if parent == "provenance"
                else (
                    REVISION["source_record_pairs"].get(value.get("key"), {})
                    if parent == "source_records"
                    else {}
                )
            )
        )
        result = {}
        for key, item in value.items():
            if key in pairs:
                before, after = pairs[key]
                assert type(item) is type(before) and item == before, (parent, key)
                result[key] = copy.deepcopy(after)
            elif key in LITERAL_FIELDS:
                result[key] = copy.deepcopy(item)
            else:
                result[key] = rebind_r92_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r92_metadata(item, parent, path + (i,))
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
    return copy.deepcopy(value)


def rebind_r92_counts(value, parent=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if parent == "coverage" and key in REVISION["coverage_field_pairs"]:
                before, after = REVISION["coverage_field_pairs"][key]
                assert type(item) is type(before) and item == before, key
                result[key] = after
            elif key in LITERAL_FIELDS or key == "record":
                result[key] = copy.deepcopy(item)
            else:
                result[key] = rebind_r92_counts(item, key)
        return result
    if isinstance(value, list):
        return [rebind_r92_counts(item, parent) for item in value]
    return copy.deepcopy(value)


def rebind_r92_record(record, key):
    if key not in REVISION["record_extensions"]:
        return copy.deepcopy(record)
    edge = REVISION["record_extensions"][key]
    assert canonical(record) == edge["before_after_metadata_sha256"], key
    result = copy.deepcopy(record)
    result.update(copy.deepcopy(edge["fields"]))
    assert result["verdict"] == record["verdict"]
    assert canonical(result) == edge["after_sha256"], key
    return result


def rebind_r92_render_row(row):
    key = f"{row['gua']}:{row['line']}"
    edge = REVISION["render_oracle_extensions"].get(key)
    if edge is None:
        return copy.deepcopy(row)
    assert row == edge["before"], key
    assert row["lines"] == edge["after"]["lines"]
    return copy.deepcopy(edge["after"])


def rebind_r92_business22(value, index):
    edge = REVISION["business22_edges"][str(index)]
    source = (
        Path(__file__).parent
        / f"fixtures/heluo_reading_delivery_v1/before22/{index:02d}.json"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == edge["before_file_sha256"]
    assert canonical(value) == canonical(json.loads(source.read_bytes()))
    body = lambda v: {k: x for k, x in v.items() if k != "snapshot_text"}
    assert canonical(body(value)) == edge["before_body_sha256"]
    result = copy.deepcopy(value)
    for patch in edge["patches"]:
        node = result
        for key in patch["path"][:-1]:
            node = node[key]
        key = patch["path"][-1]
        assert node[key] == patch["before"], patch["path"]
        node[key] = copy.deepcopy(patch["after"])
    assert canonical(body(result)) == edge["after_body_sha256"]
    # All fields beyond source objects were checked exact by the sealed builder.
    for key in (
        "chart",
        "four_pillars",
        "calendar_context",
        "dayun",
        "judge",
        "solar_term",
    ):
        assert result[key] == value[key], key
    return result


def assert_r92_source_addition():
    """Verify the complete union, not just a favorable old prefix."""
    from tests.heluo_current_source_reference import frozen_source as latest_source

    root = Path(__file__).parents[1]
    for name, expected, additions in zip(
        SOURCE_NAMES[:3],
        (CURRENT_HEADERS, CURRENT_COMMENTARIES, CURRENT_POEMS),
        (
            LITERAL["headers"],
            [
                {k: v for k, v in e.items() if k != "yaoci"}
                for e in LITERAL["commentaries"]
            ],
            LITERAL["poem_groups"],
        ),
        strict=True,
    ):
        old = json.loads((R91 / "before-source" / name).read_bytes())
        actual = json.loads((root / name).read_bytes())
        assert canonical(old) == REVISION["source_before_canonical"][name]
        assert expected["entries"] == old["entries"] + additions
        from tests.heluo_ben22_revision_reference import CURRENT_COMMENTARIES as NEW_C
        from tests.heluo_ben22_revision_reference import CURRENT_HEADERS as NEW_H
        from tests.heluo_ben22_revision_reference import assert_r96_source_addition

        if name in SOURCE_NAMES[:2]:
            assert actual["entries"][:126] == expected["entries"]
            from tests.heluo_bo23_revision_reference import frozen_source

            assert (NEW_H if name == SOURCE_NAMES[0] else NEW_C) == frozen_source(
                name, "before"
            )
            assert frozen_source(name) == latest_source(name, "before")
            assert actual == latest_source(name)
        else:
            assert actual == expected
            assert canonical(actual) == REVISION["source_after_canonical"][name]
        assert_r96_source_addition()
    catalogue = json.loads((root / SOURCE_NAMES[3]).read_bytes())
    from tests.canping_witness_knowledge_revision import REVISION as R99
    from tests.heluo_ben22_revision_reference import CURRENT_CATALOGUE as NEW_CATALOGUE
    from tests.heluo_ben22_revision_reference import REVISION as R96

    assert CURRENT_CATALOGUE["sources"] == R96["catalogue_sources_before"]
    assert NEW_CATALOGUE == R99["catalogue_before"]
    from tests.heluo_bo23_revision_reference import frozen_source

    assert R99["catalogue_after"] == frozen_source(SOURCE_NAMES[3], "before")
    assert frozen_source(SOURCE_NAMES[3]) == latest_source(SOURCE_NAMES[3], "before")
    assert catalogue == latest_source(SOURCE_NAMES[3])
    return True


def assert_r92_historical_file_edge(name, historical_sha256):
    before = R91 / "before-source" / name
    assert hashlib.sha256(before.read_bytes()).hexdigest() == historical_sha256
    assert historical_sha256 == REVISION["source_files_before_sha256"][name]
    actual = Path(__file__).parents[1] / name
    from tests.heluo_ben22_revision_reference import REVISION as R96
    from tests.heluo_ben22_revision_reference import assert_r96_historical_file_edge

    if name in R96["source_files_before_sha256"]:
        assert_r96_historical_file_edge(
            name, REVISION["source_files_after_sha256"][name]
        )
    else:
        assert (
            hashlib.sha256(actual.read_bytes()).hexdigest()
            == REVISION["source_files_after_sha256"][name]
        )
    assert_r92_source_addition()

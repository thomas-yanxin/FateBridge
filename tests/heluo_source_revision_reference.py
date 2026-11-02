"""Explicit source identity evolution; no production calculation or output oracle."""

import json
from pathlib import Path

MIGRATION = json.loads(
    (
        Path(__file__).parent
        / "fixtures/heluo_gu18_xu5_v1/reference-metadata-migration-final.json"
    ).read_bytes()
)
# Only source identities and source metadata may evolve. Texts, notes,
# applicability, branch choice, numbers, phases and unrelated values stay exact.
METADATA_KEYS = {
    "corpus_id",
    "commentary_corpus_id",
    "header_content_sha256",
    "commentary_sha256",
    "commentary_content_sha256",
    "poem_sha256",
    "poem_content_sha256",
    "poem_review_status",
    "transcription_policy",
    "commentary_transcription_policy",
    "poem_transcription_policy",
    "canonical_content_sha256",
    "loaded_file_sha256",
    "source_revision",
    "scope",
    "review_status",
    "source_catalogue_content_sha256",
    "version",
}


def rebind_reviewed_source_metadata(value, key=None, owner=None):
    if isinstance(value, dict):
        identity = value.get("key", value.get("corpus_id"))
        return {
            k: rebind_reviewed_source_metadata(v, k, identity) for k, v in value.items()
        }
    if isinstance(value, list):
        return [rebind_reviewed_source_metadata(v, key, owner) for v in value]
    if key == "source_catalogue_version":
        assert value == MIGRATION["source_catalogue_version_before"]
        return MIGRATION["source_catalogue_version_after"]
    if isinstance(value, str):
        if key in {"version", "source_revision"} and owner not in {
            "yaoci_collation",
            "commentary_collation",
            "poem_collation",
            "heluo_nlc_yaoci_headers_v8",
            "heluo_nlc_line_commentary_v11",
            "heluo_nlc_volume3_line_poems_v2",
        }:
            return value
        if key in METADATA_KEYS:
            return MIGRATION["scalar_pairs"].get(value, value)
        # Snapshot footers spell out source identities in lines. Evolve only
        # declared source-object headings and hash lines; all body lines exact.
        lines = value.splitlines(keepends=True)
        result = []
        for line in lines:
            if line.startswith(
                tuple(
                    "来源对象：" + n + "；"
                    for n in [
                        "yaoci_collation",
                        "commentary_collation",
                        "poem_collation",
                    ]
                )
            ):
                for old, new in MIGRATION["scalar_pairs"].items():
                    line = line.replace(old, new)
            elif line.startswith(("实际载入字节散列：", "所核内容身份：")):
                for old, new in MIGRATION["scalar_pairs"].items():
                    if len(old) == 64 and all(c in "0123456789abcdef" for c in old):
                        line = line.replace(old, new)
            result.append(line)
        return "".join(result)
    return value


def rebind_reviewed_registry_counts(value, key=None):
    if isinstance(value, dict):
        return {k: rebind_reviewed_registry_counts(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [rebind_reviewed_registry_counts(v, key) for v in value]
    if key in MIGRATION["coverage_field_pairs"]:
        old, new = MIGRATION["coverage_field_pairs"][key]
        assert value == old
        return new
    return value

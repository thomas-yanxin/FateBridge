"""Missing source versions stay null in data and explicit in reading text."""

import copy

import pytest

from fatebridge.services.knowledge import _build_knowledge_snapshot_text


@pytest.mark.parametrize(
    "revision,label", [(None, "未提供"), (0, "0"), ("0", "0"), ("1.2.0", "1.2.0")]
)
def test_missing_and_explicit_source_versions_remain_distinct_without_input_mutation(
    revision, label
):
    entry = {
        "domain": "heluo",
        "category": "source_collections",
        "key": "source",
        "title": "原文None保留",
        "tips": ["正文None保留"],
        "provenance": {
            "reference_policy_id": "numerology_source_reference_v1",
            "source_records": [
                {
                    "key": "source",
                    "source_title": "所選來源",
                    "source_revision": revision,
                    "review_status": "not_assessed",
                    "loaded_file_sha256": "fixed",
                    "canonical_content_sha256": "fixed",
                }
            ],
        },
    }
    before = copy.deepcopy(entry)
    snapshot = _build_knowledge_snapshot_text(entry)
    assert f"修订：{label}；状态：not_assessed" in snapshot
    assert "正文None保留" in snapshot and "原文None保留" in snapshot
    assert (
        entry == before
        and entry["provenance"]["source_records"][0]["source_revision"] == revision
    )

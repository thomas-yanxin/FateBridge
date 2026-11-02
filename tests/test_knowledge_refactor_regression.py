"""Whole-response pre/post proof, separate from historical edition receipts."""

from fatebridge.core.knowledge_store import load_knowledge_bundles
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.knowledge_refactor_reference import (
    assert_read_matches_before_repair,
    baseline,
    digest,
)


def test_all93_current_bazi_knowledge_reads_and_complete_registry_match_before_repair():
    expected = baseline()
    assert (
        digest(calculate_knowledge_registry(domain="bazi"))
        == expected["registry_sha256"]
    )
    for name in expected["reads"]:
        category, key = name.split("/", 1)
        assert_read_matches_before_repair(
            category,
            key,
            calculate_knowledge_read(domain="bazi", category=category, key=key),
        )
    assert (
        digest({k: v for k, v in load_knowledge_bundles().items() if k != "bazi"})
        == expected["other_domain_bundles_sha256"]
    )

"""Edition confusion changes factors; identity and unresolved gates must survive."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/data/sukuyo-sanskrit-before-production-v80.json"


@pytest.mark.parametrize("edition", ["cowell_neil_1886", "mukhopadhyaya_1954_titus"])
def test_source_specific_products(edition):
    from fatebridge.core.sukuyo_sanskrit_editions import sanskrit_edition_reference

    first = json.loads(
        (
            REFERENCE.parent / "sukuyo-sanskrit-adjudication-before-c-v80.json"
        ).read_bytes()
    )
    result = sanskrit_edition_reference()
    assert (
        result["conditional_products"][edition] == first["expected_products"][edition]
    )
    assert result["source_data"] == first["facts"]


@pytest.mark.parametrize(
    "flag",
    [
        "T1299_dawn_clock_resolved",
        "T2465_half_day_clock_resolved",
        "leap_short_month_priority_resolved",
        "Chinese_T1300_T1301_emendation",
        "cross_edition_named_units_equated",
        "physical_witness_independence_verified",
    ],
)
def test_source_comparison_does_not_certify_unknown_rules(flag):
    from fatebridge.core.sukuyo_sanskrit_editions import sanskrit_edition_reference

    assert sanskrit_edition_reference()["source_data"][flag] is False


def test_edition_data_tampering_rejected():
    from fatebridge.core.sukuyo_sanskrit_editions import (
        sanskrit_edition_reference,
        validate_edition_data,
    )

    data = copy.deepcopy(sanskrit_edition_reference()["source_data"])
    data["editions"][0]["water_chain_counts"] = data["editions"][1][
        "water_chain_counts"
    ]
    with pytest.raises(ValueError):
        validate_edition_data(data)


def test_new_source_is_additive_and_old_hash_scope_is_retained():
    from fatebridge.core.sukuyo_upstream_dawn import upstream_lines, upstream_reference

    result = upstream_reference()
    assert (
        result["source_bundle_sha256"]
        == "744af87237075bf003bbceed2def968afee781039ab6f706208b565831ff9c83"
    )
    assert (
        result["matanga_time_comparison"]["source_bundle_sha256"]
        == "8eb31ac1e216ef247b062b7d68bd8d1b98aece3b4d97841f8a15deb00b9e5908"
    )
    assert (
        result["sanskrit_edition_comparison"]["source_data"]["id"]
        == "sukuyo_sanskrit_editions_v80"
    )
    lines = upstream_lines(result)
    assert any("19840" in s and "15360" in s for s in lines)
    assert any("未刊全文" in s and "第三年" in s for s in lines)


def test_duplicate_paragraph_labels_and_invalid_bytes_are_not_silently_lost():
    from scripts.sukuyo.check_sukuyo_sanskrit_editions import parse_titus

    raw = b"<html><script>Paragraph: 999</script><br>Subchapter: I<br>Paragraph: 53<br>Verse: 2 first<br>Paragraph: 53<br>Verse: 2 second\xd7</html>"
    parsed = parse_titus(raw)
    assert [(r["paragraph_occurrence"], r["text"]) for r in parsed["records"]] == [
        (1, "first"),
        (2, "second[BYTE-D7]"),
    ]
    assert parsed["invalid_utf8_bytes"] == [{"byte_offset": len(raw) - 8, "hex": "d7"}]


def test_required_capture_set_rejects_a_passing_subset():
    from scripts.sukuyo.check_sukuyo_sanskrit_editions import verify

    with pytest.raises(ValueError, match="全部四份"):
        verify({})


def test_before_code_reference_identity():
    assert (
        hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
        == "7f98037a8906e806c4ce7c8a07c021e5968e07bcc8fccf2ce8fb68b121b4560f"
    )


def test_independent_adjudication_is_bound_separately():
    from fatebridge.core.sukuyo_sanskrit_editions import sanskrit_edition_reference

    assert (
        sanskrit_edition_reference()["adjudication_before_c_sha256"]
        == "b43af934885b1f9b361b5880edcc1d31ebb5c99c7cafd606fb21540fade4e660"
    )

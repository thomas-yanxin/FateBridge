"""Audit declared CFEPP cross-IDs, without inferring independent subjects.

This is a retrospective source-linkage audit of one pinned G5 revision. Names,
birth clocks, Mars positions and outcomes never decide a link. A missing link
does not establish that a person was absent from hypothesis development.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any

from fatebridge.validation.gauquelin import FINAL3_SHA256, decode_final3

G5_REVISION = "bf0db345b58127a438121b74ebf4ad843243a573"
SOURCE_FILES = {
    "ertel": (
        "data/raw/ertel/3a_sports-utf8.txt",
        "b7b0dd7a4207183d0842323e0f902cde4be09e7136a565ecf044694ac5ae4655",
    ),
    "corrections": (
        "src/commands/ertel/sport/ErtelSport.php",
        "a687740a53a131c3e99aa7b7feb81ec95e69d6efbe4b671063c9502f51350ffd",
    ),
    "integration": (
        "src/commands/cfepp/final3/ids.php",
        "a15741dab4c6af949784f0b2b5c3c2143c542985aee2e951db0f1d30f1cc2339",
    ),
}


def _positive_id(value: str) -> int | None:
    if value in ("", "0"):
        return None
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("invalid_source_cross_id")
    return int(value)


def _para_reference(value: str) -> tuple[str | None, int | None]:
    # A star denotes the separate, unpublished 76-person "Para lowers" pool.
    # It is not decoration on an ID in the published 535-person cohort.
    if value in ("", "0"):
        return None, None
    if value.startswith("*"):
        number = _positive_id(value[1:].strip())
        if number is None or number > 76:
            raise ValueError("invalid_para_lowers_reference")
        return "unpublished_lowers_76", number
    number = _positive_id(value)
    if number is None or number > 535:
        raise ValueError("invalid_para_published_reference")
    return "published_535", number


def _parse_ertel(text: str) -> list[dict[str, Any]]:
    """Offsets are Unicode characters, as in G5's mb_substr, not UTF-8 bytes."""
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    lines = text.splitlines(keepends=True)
    for index, original in enumerate(lines[6:-3], 7):
        line = original.rstrip("\r\n")
        if not line.strip():
            continue
        if len(line) < 169:
            raise ValueError("truncated_ertel_source_row")
        erid = _positive_id(line[7:13].strip())
        if erid is None or erid in seen:
            raise ValueError("missing_or_duplicate_ertel_id")
        seen.add(erid)
        para_raw = line[149:154].strip()
        para_group, para_number = _para_reference(para_raw)
        rows.append(
            {
                "ertel_id": erid,
                "source_line": index,
                "source_line_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "literal_cfepp_field": line[157:163].strip(),
                "raw_cfepp_id": _positive_id(line[157:163].strip()),
                "raw_gauquelin_source": line[:6].strip(),
                "raw_gauquelin_number": _positive_id(line[144:148].strip()),
                "raw_comite_para_id": para_raw,
                "comite_para_subset": para_group,
                "comite_para_number": para_number,
            }
        )
    return rows


def _parse_corrections(php: str) -> dict[int, int]:
    # Read only the literal data table. Never execute downloaded PHP.
    block = php.split("const ERTEL_CFEPP = [", 1)[1].split("];", 1)[0]
    entries = re.findall(r"^\s*(\d+)\s*=>\s*(\d+),", block, re.MULTILINE)
    result: dict[int, int] = {}
    for er, cf in entries:
        erid, cfid = int(er), int(cf)
        if erid in result or erid < 1 or not 1 <= cfid <= 1120:
            raise ValueError("invalid_or_duplicate_linkage_correction")
        result[erid] = cfid
    return result


def _link_index(
    rows: list[dict[str, Any]], corrections: dict[int, int]
) -> tuple[dict[int, list[dict[str, Any]]], dict[str, Any]]:
    """Keep collisions and invalid references visible; never let a dict win."""
    index: dict[int, list[dict[str, Any]]] = defaultdict(list)
    missing = 0
    for row in rows:
        cfid = corrections.get(row["ertel_id"], row["raw_cfepp_id"])
        if cfid is None:
            missing += 1
        else:
            index[cfid].append(row)
    return dict(index), {
        "linked_ertel_rows": sum(map(len, index.values())),
        "unlinked_ertel_rows": missing,
        "distinct_referenced_cfepp_ids": len(index),
        "collisions": [
            {"cfepp_id": cf, "ertel_ids": [r["ertel_id"] for r in values]}
            for cf, values in sorted(index.items())
            if len(values) > 1
        ],
        "out_of_range": [
            {"cfepp_id": cf, "ertel_ids": [r["ertel_id"] for r in values]}
            for cf, values in sorted(index.items())
            if not 1 <= cf <= 1120
        ],
    }


def audit_cfepp_linkage(
    final3: bytes, ertel: bytes, corrections: bytes, integration: bytes
) -> dict[str, Any]:
    """Replay declared links from fixed sources; no efficacy test or row filter.

    The extra CF-1119 / A1-2089 link and the CF-218 identity caution are source
    declarations, not a silent repair of the original Ertel table. Raw Gauquelin
    numbers are retained as raw values; other G5 identity tweaks are not replayed
    here, so these records must not be exported as canonical subject IDs.
    """
    supplied = {"ertel": ertel, "corrections": corrections, "integration": integration}
    provenance: dict[str, Any] = {
        "final3": {
            "sha256": FINAL3_SHA256,
            "rows": 1120,
            "archive_url": f"https://github.com/tig12/g5/blob/{G5_REVISION}/data/raw/cfepp/final3.zip",
        },
    }
    for key, data in supplied.items():
        path, expected = SOURCE_FILES[key]
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f"pinned_{key}_source_hash_mismatch")
        provenance[key] = {
            "sha256": actual,
            "url": f"https://github.com/tig12/g5/blob/{G5_REVISION}/{path}",
        }
    people = decode_final3(final3)
    source_rows = _parse_ertel(ertel.decode("utf-8"))
    if len(source_rows) != 4384:
        raise ValueError("pinned_ertel_row_count_mismatch")
    fixes = _parse_corrections(corrections.decode("utf-8"))
    if set(fixes).difference(r["ertel_id"] for r in source_rows):
        raise ValueError("correction_references_missing_ertel_row")
    raw, raw_summary = _link_index(source_rows, {})
    revised, revised_summary = _link_index(source_rows, fixes)
    ledger = []
    for person in people:
        cf = int(person["case_id"].removeprefix("CF-"))
        links = revised.get(cf, [])
        # Both declarations are in the hash-checked G5 sources above. The
        # ambiguous Rudler association remains in the ledger and in totals.
        caution = cf == 218
        manual_gauquelin = "A1-2089" if cf == 1119 else None
        declared_gauquelin = manual_gauquelin is not None or any(
            r["raw_gauquelin_source"].lstrip("*") in ("G:A01", "G:D06", "G:D10")
            and r["raw_gauquelin_number"] is not None
            for r in links
        )
        ledger.append(
            {
                "case_id": person["case_id"],
                "cohort": person["cohort"],
                "final3_line_sha256": person["source_line_sha256"],
                "raw_ertel_links": raw.get(cf, []),
                "revised_ertel_links": links,
                "ertel_link_status": (
                    "source_identity_caution"
                    if caution
                    else "source_declared" if links else "not_linked_in_these_sources"
                ),
                "identity_caution": (
                    "G5 notes possible confusion between Francis and Antoine Rudler"
                    if caution
                    else None
                ),
                "source_declared_manual_gauquelin_link": manual_gauquelin,
                "declared_gauquelin_presence": declared_gauquelin,
                "declared_comite_para_published_presence": any(
                    r["comite_para_subset"] == "published_535" for r in links
                ),
                "declared_comite_para_lowers_presence": any(
                    r["comite_para_subset"] == "unpublished_lowers_76" for r in links
                ),
            }
        )
    summaries = {}
    for group in ("all_1120", "published_1066", "supplementary_54"):
        subset = [r for r in ledger if group == "all_1120" or r["cohort"] == group]
        summaries[group] = {
            "rows": len(subset),
            "declared_ertel_presence": sum(
                bool(r["revised_ertel_links"]) for r in subset
            ),
            "not_linked_to_ertel": sum(not r["revised_ertel_links"] for r in subset),
            "declared_gauquelin_presence": sum(
                r["declared_gauquelin_presence"] for r in subset
            ),
            "declared_comite_para_published_presence": sum(
                r["declared_comite_para_published_presence"] for r in subset
            ),
            "declared_comite_para_lowers_presence": sum(
                r["declared_comite_para_lowers_presence"] for r in subset
            ),
            "identity_cautions": sum(r["identity_caution"] is not None for r in subset),
            "independently_verified_disjoint_subject_count": None,
        }
    changes = Counter(
        "added" if r["raw_cfepp_id"] is None else "changed_existing"
        for r in source_rows
        if r["ertel_id"] in fixes and r["raw_cfepp_id"] != fixes[r["ertel_id"]]
    )
    return {
        "schema_version": "cfepp_source_linkage_v1",
        "study_type": "retrospective_provenance_audit",
        "g5_revision": G5_REVISION,
        "source_provenance": provenance,
        "ertel_rows_retained": len(source_rows),
        "ertel_rows": source_rows,
        "ertel_cfepp_field_counts": {
            "nonempty_fields": sum(bool(r["literal_cfepp_field"]) for r in source_rows),
            "explicit_zero_fields": sum(
                r["literal_cfepp_field"] == "0" for r in source_rows
            ),
            "positive_id_fields": sum(
                r["raw_cfepp_id"] is not None for r in source_rows
            ),
            "empty_fields": sum(r["literal_cfepp_field"] == "" for r in source_rows),
        },
        "ertel_comite_para_subsets": dict(
            Counter(r["comite_para_subset"] or "not_linked" for r in source_rows)
        ),
        "raw_links": raw_summary,
        "revised_links": revised_summary,
        "maintainer_correction_entries": len(fixes),
        "effective_corrections": dict(changes),
        "cohorts": summaries,
        "rows": ledger,
        "scope": {
            "identity_basis": "source_declared_cross_ids_not_civil_registry_verification",
            "canonical_subject_ids_established": False,
            "other_g5_gauquelin_id_tweaks_replayed": False,
            "missing_link_means_independent": False,
            "historical_method_or_key_sectors_selected": False,
            "control_population_or_base_rate_evaluated": False,
            "independent_holdout_established": False,
            "prospective_prediction_evaluated": False,
            "predictive_efficacy_established": False,
            "authority_certified": False,
        },
    }

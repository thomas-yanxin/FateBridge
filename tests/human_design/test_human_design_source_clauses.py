"""Source completeness and candidate custody; no synthetic astronomy oracle."""

import copy
import json
import sys

import pytest

from scripts.human_design import audit_human_design_source_clauses as audit


def source_layout():
    pages = [""] * 133
    for gate in range(1, 65):
        pages[6 + 2 * (gate - 1)] = "\n".join(
            f"{line} neutral" for line in range(6, 0, -1)
        )
    return "\f".join(pages) + "\f"


def catalog():
    return {
        "gates": [
            {
                "gate": gate,
                "line_polarities": [
                    {
                        "line": line,
                        "exaltation_planet": "Moon",
                        "detriment_planet": "Sun",
                        "polarity_kind": "dual",
                    }
                    for line in range(1, 7)
                ],
            }
            for gate in range(1, 65)
        ]
    }


def review_for(report):
    return {
        "source_pdf_sha256": report["source_pdf_sha256"],
        "complete_source_reading_accepted": False,
        "clause_reviews": [
            {
                "line_id": row["line_id"],
                "source_layout_block_sha256": row["source_layout_block_sha256"],
                "review_kind": "visual_planet_and_polarity_clause_only",
                "complete_line_semantics_reviewed": False,
            }
            for row in report["line_rows"]
            if row["requires_clause_review"]
        ],
    }


@pytest.mark.parametrize(
    "clause",
    [
        "vEnUs has a role that the exact is-also grammar does not recognize.",
        "No polarity. No exaltation.",
        "There is neither an exaltation nor a detriment.",
        "Each planet. No specific planetary accent.",
        "Mercurial wording alone is not a new assignment.",
    ],
)
def test_broadened_candidates_do_not_silently_disappear(clause):
    report = audit.inventory(
        source_layout().replace("6 neutral", "6 " + clause, 1), catalog()
    )
    assert report["candidate_line_ids"] == ["1.6"]
    assert report["observed_line_count"] == 384
    assert report["complete_semantic_reviewed_line_count"] == 0
    assert not report["complete_source_reading_accepted"]


@pytest.mark.parametrize(
    "damage", ["delete_page", "delete_heading", "duplicate_heading"]
)
def test_incomplete_or_ambiguous_source_cannot_become_a_smaller_passing_subset(damage):
    layout = source_layout()
    if damage == "delete_page":
        layout = "\f".join(layout.split("\f")[1:])
    elif damage == "delete_heading":
        layout = layout.replace("1 neutral", "missing", 1)
    else:
        layout = layout.replace("1 neutral", "1 neutral\n1 duplicate", 1)
    with pytest.raises(ValueError):
        audit.inventory(layout, catalog())


@pytest.mark.parametrize("damage", ["omit", "duplicate"])
def test_catalogue_cannot_drop_or_duplicate_a_line(damage):
    reference = catalog()
    if damage == "omit":
        reference["gates"][0]["line_polarities"].pop()
    else:
        reference["gates"][0]["line_polarities"].append(
            reference["gates"][0]["line_polarities"][0]
        )
    with pytest.raises(ValueError):
        audit.inventory(source_layout(), reference)


@pytest.mark.parametrize(
    "damage",
    [
        "omit",
        "duplicate",
        "substitute",
        "source",
        "block",
        "scope",
        "full",
        "line_full",
    ],
)
def test_review_cannot_omit_substitute_or_promote_candidate_evidence(damage):
    report = audit.inventory(
        source_layout().replace("6 neutral", "6 No polarity.", 1), catalog()
    )
    review = review_for(report)
    if damage == "omit":
        review["clause_reviews"] = []
    elif damage == "duplicate":
        review["clause_reviews"] *= 2
    elif damage == "substitute":
        review["clause_reviews"][0]["line_id"] = "1.5"
    elif damage == "source":
        review["source_pdf_sha256"] = "0" * 64
    elif damage == "block":
        review["clause_reviews"][0]["source_layout_block_sha256"] = "0" * 64
    elif damage == "scope":
        review["clause_reviews"][0]["review_kind"] = "complete_reading"
    elif damage == "full":
        review["complete_source_reading_accepted"] = True
    else:
        review["clause_reviews"][0]["complete_line_semantics_reviewed"] = True
    with pytest.raises(ValueError):
        audit.bind_review(report, review)


def test_every_clause_review_still_cannot_claim_complete_interpretation(
    tmp_path, monkeypatch
):
    report = audit.inventory(
        source_layout().replace("6 neutral", "6 No polarity.", 1), catalog()
    )
    audit.bind_review(report, review_for(report))
    assert report["candidate_clause_review_count"] == 1
    assert not report["complete_source_reading_accepted"]
    output = tmp_path / "report.json"
    monkeypatch.setattr(audit, "audit", lambda *args: copy.deepcopy(report))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "source.pdf",
            "--output",
            str(output),
            "--require-complete-interpretation",
        ],
    )
    with pytest.raises(SystemExit) as error:
        audit.main()
    assert error.value.code == 1
    saved = json.loads(output.read_text())
    assert saved["observed_line_count"] == 384
    assert saved["complete_semantic_reviewed_line_count"] == 0


def test_different_pdf_is_rejected_before_text_extraction(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"different edition")
    monkeypatch.setattr(
        audit.subprocess,
        "check_output",
        lambda *args, **kwargs: pytest.fail("must check source identity first"),
    )
    with pytest.raises(ValueError, match="edition review"):
        audit.audit(source)

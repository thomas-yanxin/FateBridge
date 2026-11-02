"""Check a frozen book census without calculating or grading any chart."""

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDY = ROOT / "docs/validation/bazi-ditian-wholebook-census-v1"
GRADES = {"强", "中和", "弱"}
GROUPED_FORMULA_PLAN = (
    "docs/validation/bazi-eight-input-source-review-v1/"
    "formula-correction-plan-before-code.json"
)
GROUPED_FORMULA_PLAN_SHA256 = (
    "d97ee2d18936b5aa7e35abb720b2b69292b45e15deb96949acfc8aaec5164f3f"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bound(path):
    if sha(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Changed frozen document: {path.name}")
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_value(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def source_warning(kind, document, document_sha256, page, index, item):
    warning = {
        "source_kind": kind,
        "original_document": document,
        "original_document_sha256": document_sha256,
        "pdf_page": page,
        "warning_index": index,
        "item": item,
    }
    return dict(warning, warning_id=digest_value(warning))


def resolve_transcription_metadata(study, protocol_sha256, pdf_sha256, warnings, pages):
    """Apply bound page-metadata readings while retaining every initial warning.

    The bindings establish provenance, not image semantics or independent review.
    This mechanism cannot edit source-case pillars, judgments, actors or voices.
    """
    inventory = {warning["warning_id"]: warning for warning in warnings}
    metadata = {
        number: dict(origin["page"].get("retained_metadata", {}))
        for number, origin in pages.items()
    }
    documents, corrections, seen, edited, identities = {}, [], set(), set(), set()
    for path in sorted(study.glob("transcription-resolutions-*.json")):
        document = read_bound(path)
        require(
            isinstance(document, dict)
            and set(document)
            == {"protocol_sha256", "source_pdf_sha256", "resolutions"},
            "Transcription resolution document has unsupported fields",
        )
        require(
            document.get("protocol_sha256") == protocol_sha256
            and document.get("source_pdf_sha256") == pdf_sha256,
            "Transcription resolution lost protocol or source binding",
        )
        records = document.get("resolutions")
        require(
            isinstance(records, list) and bool(records),
            "Transcription resolution has no records",
        )
        for record in records:
            require(
                isinstance(record, dict)
                and set(record)
                == {
                    "resolution_id",
                    "kind",
                    "original_warnings",
                    "original_batch",
                    "original_batch_sha256",
                    "pdf_page",
                    "image_sha256",
                    "field",
                    "first_value_retained",
                    "corrected_value",
                    "anchor",
                    "evidence",
                },
                "Transcription resolution has unsupported edit or status fields",
            )
            identity = record.get("resolution_id")
            require(
                isinstance(identity, str)
                and bool(identity.strip())
                and identity not in identities,
                "Transcription resolution ID is absent or repeated",
            )
            identities.add(identity)
            require(
                record.get("kind") == "page_metadata_transcription",
                "Transcription resolution kind cannot close unknown or edit case data",
            )
            number = record.get("pdf_page")
            require(
                type(number) is int and number in pages,
                "Transcription resolution page is absent or not an integer",
            )
            origin = pages[number]
            require(
                record.get("original_batch") == origin["batch"]
                and record.get("original_batch_sha256") == origin["batch_sha256"]
                and record.get("image_sha256") == origin["page"]["image_sha256"],
                "Transcription resolution lost original batch or page image",
            )
            field = record.get("field")
            original_metadata = origin["page"].get("retained_metadata", {})
            first = original_metadata.get(field) if isinstance(field, str) else None
            value = record.get("corrected_value")
            require(
                isinstance(field, str)
                and field in original_metadata
                and isinstance(first, str)
                and record.get("first_value_retained") == first
                and isinstance(value, str)
                and bool(value.strip())
                and value != first
                and isinstance(record.get("anchor"), str)
                and bool(record["anchor"].strip()),
                "Transcription resolution lost existing metadata field or first value",
            )
            require(
                (number, field) not in edited,
                "Transcription resolution repeats an original metadata field",
            )
            originals = record.get("original_warnings")
            require(
                isinstance(originals, list) and bool(originals),
                "Transcription resolution has no original warning",
            )
            for original in originals:
                warning_id = original.get("warning_id")
                require(
                    warning_id in inventory
                    and original == inventory[warning_id]
                    and original["pdf_page"] == number,
                    "Transcription resolution lost original warning identity or page",
                )
                require(
                    warning_id not in seen,
                    "Transcription resolution repeats an original warning",
                )
                seen.add(warning_id)
            evidence = record.get("evidence", {})
            require(
                isinstance(evidence, dict)
                and set(evidence)
                == {"image", "image_sha256", "pdf_page", "parent_image_sha256"}
                and type(evidence["pdf_page"]) is int,
                "Transcription resolution evidence has unsupported fields or page",
            )
            image_path = evidence.get("image")
            require(
                isinstance(image_path, str)
                and not Path(image_path).is_absolute()
                and (study / image_path)
                .resolve()
                .is_relative_to((study / "transcription-evidence").resolve()),
                "Transcription resolution evidence path escaped its directory",
            )
            image = study / image_path
            require(
                image.is_file()
                and sha(image) == evidence.get("image_sha256")
                and evidence.get("pdf_page") == number
                and evidence.get("parent_image_sha256") == record["image_sha256"],
                "Transcription resolution lost evidence image or parent page binding",
            )
            edited.add((number, field))
            metadata[number][field] = value
            corrections.append(
                dict(
                    record,
                    resolution_document=path.name,
                    resolution_document_sha256=sha(path),
                )
            )
        documents[path.name] = sha(path)
    return {
        "transcription_resolution_documents_sha256": documents,
        "transcription_warnings_retained": warnings,
        "transcription_warning_inventory_sha256": digest_value(warnings),
        "remaining_transcription_warnings": [
            warning for warning in warnings if warning["warning_id"] not in seen
        ],
        "page_metadata_corrections": corrections,
        "resolved_page_metadata_sha256": digest_value(metadata),
    }


def resolve_source_prose(claims, origins, contexts, study):
    """Resolve bound reader corrections without altering initial claims or grades."""
    resolved = {identity: dict(claim) for identity, claim in claims.items()}
    corrections, seen = [], set()
    evidence_images = {sha(p) for p in (study / "page-images").glob("*.png")}
    for name, context in contexts.items():
        if context.get("kind") != (
            "reader_transcription_correction_not_source_author_disagreement"
        ):
            continue
        for qualification in context["qualifications"]:
            identity = qualification["target_id"]
            require(
                qualification["target_kind"] == "claim" and identity in claims,
                "Reader correction must target a source claim",
            )
            require(identity not in seen, "Reader correction target repeated")
            seen.add(identity)
            edit = qualification["qualification"]
            origin = origins[identity]
            require(
                context.get("original_batch_sha256") == origin["batch_sha256"]
                and origin["pdf_page"] in context.get("source_pages", []),
                "Reader correction lost original batch or page binding",
            )
            require(
                context.get("image_sha256")
                in evidence_images | {origin["image_sha256"]},
                "Reader correction lost image binding",
            )
            require(
                edit.get("field") == "retained_statement",
                "Reader correction cannot change source actors, voices or grades",
            )
            first = claims[identity].get("retained_statement")
            value = edit.get("corrected_value")
            require(
                isinstance(first, str)
                and edit.get("first_value_retained") == first
                and isinstance(value, str)
                and bool(value.strip())
                and value != first,
                "Reader correction lost first value or revised prose",
            )
            resolved[identity]["retained_statement"] = value
            corrections.append(
                {
                    "target_id": identity,
                    "context_document": name,
                    "original_batch": origin["batch"],
                    "field": "retained_statement",
                    "first_value_retained": first,
                    "corrected_value": value,
                }
            )
    return resolved, corrections


def resolve_case_input_alignment(
    cases,
    claims,
    case_origins,
    claim_origins,
    study,
    root,
    protocol_sha,
    pdf_sha,
    original_claims=None,
):
    """Resolve reviewed literal inputs and their references; retain every first value.

    Hash bindings cannot certify source reading. A frozen prospective review limits
    this mechanism to its explicit source-read edits, never grades or judgments.
    """
    resolved_cases = copy.deepcopy(cases)
    resolved_claims = copy.deepcopy(claims)
    positions = {case["case_id"]: case for case in resolved_cases}
    documents, corrections, reviews, questions, question_resolutions = (
        {},
        [],
        [],
        [],
        [],
    )
    resolution_requests = []
    seen_cases, seen_claims = set(), set()
    for path in sorted(study.glob("source-case-input-resolutions-*.json")):
        document = read_bound(path)
        require(
            set(document)
            == {"review_protocol", "review_protocol_sha256", "resolution_payload"},
            "Case input resolution has unsupported fields",
        )
        review_name = document["review_protocol"]
        require(
            isinstance(review_name, str)
            and not Path(review_name).is_absolute()
            and (root / review_name).resolve().is_relative_to(root.resolve()),
            "Case input review protocol escaped root",
        )
        review_path = root / review_name
        review_protocol = read_bound(review_path)
        require(
            sha(review_path) == document["review_protocol_sha256"],
            "Case input review protocol changed",
        )
        first_cases = review_path.parent / "all-original-cases-first.json"
        first_claims = review_path.parent / "all-original-claims-first.json"
        require(
            sha(first_cases) == review_protocol["all558_original_cases_sha256"]
            and sha(first_claims) == review_protocol["all1380_original_claims_sha256"]
            and json.loads(first_cases.read_text()) == cases
            and {c["claim_id"]: c for c in json.loads(first_claims.read_text())}
            == (original_claims if original_claims is not None else claims),
            "Case input alignment narrowed or changed the complete original collection",
        )
        payload = document["resolution_payload"]
        require(
            isinstance(payload, dict)
            and set(payload)
            == {
                "protocol_sha256",
                "source_pdf_sha256",
                "case_resolutions",
                "claim_reviews",
            }
            and payload["protocol_sha256"] == protocol_sha
            and payload["source_pdf_sha256"] == pdf_sha
            and review_protocol["source_protocol_sha256"] == protocol_sha
            and review_protocol["source_pdf_sha256"] == pdf_sha
            and digest_value(payload)
            == review_protocol["planned_payload_object_sha256"],
            "Case input resolution lost frozen source-reading payload",
        )
        edits, linked_reviews = payload["case_resolutions"], payload["claim_reviews"]
        require(
            isinstance(edits, list)
            and edits
            and isinstance(linked_reviews, list)
            and [e["case_id"] for e in edits] == review_protocol["exact_case_ids"]
            and [e["claim_id"] for e in linked_reviews]
            == review_protocol["exact_claim_ids"],
            "Case input review inventory narrowed or reordered",
        )

        def check_evidence(evidence, origin):
            require(
                set(evidence)
                == {
                    "pdf_page",
                    "original_batch",
                    "original_batch_sha256",
                    "image",
                    "image_sha256",
                }
                and evidence["pdf_page"] == origin["pdf_page"]
                and evidence["original_batch"] == origin["batch"]
                and evidence["original_batch_sha256"] == origin["batch_sha256"]
                and evidence["image_sha256"] == origin["image_sha256"],
                "Case input alignment lost original batch or source page",
            )
            image = evidence["image"]
            require(
                isinstance(image, str)
                and not Path(image).is_absolute()
                and (study / image).resolve().is_relative_to(study.resolve())
                and sha(study / image) == origin["image_sha256"],
                "Case input alignment evidence escaped or changed",
            )

        document_case_ids = set()
        order = ["year", "month", "day", "hour"]
        for edit in edits:
            require(
                set(edit)
                == {
                    "case_id",
                    "first_case_object",
                    "first_case_sha256",
                    "corrected_fields",
                    "source_evidence",
                    "prior_correction_document",
                    "prior_correction_document_sha256",
                },
                "Case input correction has unsupported fields",
            )
            identity = edit["case_id"]
            require(
                identity in positions and identity not in seen_cases,
                "Case input correction target absent or repeated",
            )
            case = positions[identity]
            require(
                case == edit["first_case_object"]
                and digest_value(case) == edit["first_case_sha256"],
                "Case input correction lost complete first case object",
            )
            patch = edit["corrected_fields"]
            literal_edit = set(patch) == {"literal_pillars", "anchor"}
            caption_edit = set(patch) == {"source_metadata"}
            require(literal_edit or caption_edit, "Unsupported case input field scope")
            if literal_edit:
                require(
                    set(patch["literal_pillars"]) == {"year", "month", "day", "hour"}
                    and all(
                        isinstance(v, str) and len(v) == 2
                        for v in patch["literal_pillars"].values()
                    )
                    and patch["literal_pillars"] != case["literal_pillars"],
                    "Case input correction cannot alter labels or fill unknown positions",
                )
            else:
                first_metadata = case.get("source_metadata", {})
                metadata = patch["source_metadata"]
                require(
                    isinstance(metadata, dict)
                    and set(metadata) == set(first_metadata)
                    and "source_caption_as_printed" in first_metadata
                    and isinstance(first_metadata["source_caption_as_printed"], str)
                    and isinstance(metadata["source_caption_as_printed"], str)
                    and bool(metadata["source_caption_as_printed"].strip())
                    and metadata["source_caption_as_printed"]
                    != first_metadata["source_caption_as_printed"]
                    and {
                        k: v
                        for k, v in metadata.items()
                        if k != "source_caption_as_printed"
                    }
                    == {
                        k: v
                        for k, v in first_metadata.items()
                        if k != "source_caption_as_printed"
                    },
                    "Caption correction cannot alter other metadata or infer a missing caption",
                )
            require(
                all(case["literal_pillars"].values()),
                "Incomplete source case cannot be completed by this mechanism",
            )
            first_flat = "".join(case["literal_pillars"][n] for n in order)
            after_flat = "".join(
                patch.get("literal_pillars", case["literal_pillars"])[n] for n in order
            )
            require(
                not literal_edit
                or patch["anchor"]
                == (
                    after_flat
                    if case.get("anchor") == first_flat
                    else case.get("anchor")
                ),
                "Case input correction changed non-literal source anchor",
            )
            check_evidence(edit["source_evidence"], case_origins[identity])
            prior_name = edit["prior_correction_document"]
            require(
                isinstance(prior_name, str)
                and not Path(prior_name).is_absolute()
                and (root / prior_name).resolve().is_relative_to(root.resolve())
                and sha(root / prior_name) == edit["prior_correction_document_sha256"],
                "Case input correction lost prior reviewed transcription",
            )
            prior = read_bound(root / prior_name)
            matches = [r for r in prior["records"] if r["case_id"] == identity]
            require(
                prior["source_pdf_sha256"] == pdf_sha
                and len(matches) == 1
                and matches[0]["before_case_object_sha256"] == digest_value(case)
                and matches[0]["after_literal_pillars"]
                == patch.get("literal_pillars", case["literal_pillars"])
                and matches[0]["after_anchor"] == patch.get("anchor", case["anchor"])
                and (
                    not caption_edit
                    or matches[0].get("after_source_metadata")
                    == patch["source_metadata"]
                ),
                "Case input alignment changed previously reviewed source literals",
            )
            corrections.append(copy.deepcopy(edit))
            case.update(copy.deepcopy(patch))
            seen_cases.add(identity)
            document_case_ids.add(identity)
        required_claims = {
            claim_id
            for identity in document_case_ids
            for claim_id in positions[identity].get("claim_ids", [])
        }
        reviewed_claims = set()
        for review in linked_reviews:
            require(
                set(review)
                == {
                    "claim_id",
                    "case_id",
                    "first_claim_object",
                    "first_claim_sha256",
                    "corrected_fields",
                    "source_evidence",
                    "review_scope",
                    "independent_external_review",
                },
                "Case claim review has unsupported fields",
            )
            identity, case_id = review["claim_id"], review["case_id"]
            require(
                identity in required_claims
                and case_id in document_case_ids
                and identity in positions[case_id].get("claim_ids", [])
                and identity not in seen_claims,
                "Case claim review absent, unlinked or repeated",
            )
            claim = resolved_claims[identity]
            require(
                claim == review["first_claim_object"]
                and digest_value(claim) == review["first_claim_sha256"],
                "Case claim review lost first claim or overlaps prior prose correction",
            )
            patch = review["corrected_fields"]
            require(
                isinstance(patch, dict)
                and set(patch)
                <= {
                    "assertion_subject",
                    "retained_statement",
                    "conditions_not_numerically_defined",
                }
                and all(k in claim and v != claim[k] for k, v in patch.items())
                and isinstance(review["review_scope"], str)
                and bool(review["review_scope"].strip())
                and review["independent_external_review"] is False,
                "Case claim correction cannot alter source judgment, grade or voice",
            )
            if "assertion_subject" in patch:
                before_case = next(
                    e["first_case_object"] for e in edits if e["case_id"] == case_id
                )
                require(
                    claim["assertion_subject"]
                    == "".join(before_case["literal_pillars"][n] for n in order) + "例"
                    and patch["assertion_subject"]
                    == "".join(positions[case_id]["literal_pillars"][n] for n in order)
                    + "例",
                    "Case claim actor correction is not the same literal-case reference",
                )
            check_evidence(review["source_evidence"], claim_origins[identity])
            require(
                claim_origins[identity]["pdf_page"]
                == case_origins[case_id]["pdf_page"],
                "Case claim review crossed an unreviewed page",
            )
            claim.update(copy.deepcopy(patch))
            reviews.append(copy.deepcopy(review))
            reviewed_claims.add(identity)
            seen_claims.add(identity)
        require(
            reviewed_claims == required_claims,
            "Case input correction omitted a linked claim review",
        )
        for key, kind in [
            ("remaining_printed_conflicts", "printed_source_conflict"),
            ("remaining_glyph_review", "glyph_review_pending"),
        ]:
            for identity in review_protocol[key]:
                require(
                    identity in positions, "Unresolved case question lost its target"
                )
                questions.append(
                    {"case_id": identity, "kind": kind, "review_protocol": review_name}
                )
        for request in review_protocol.get("resolved_previous_glyph_questions", []):
            require(
                isinstance(request, dict)
                and set(request)
                == {"original_question", "original_question_sha256", "case_id"}
                and request["case_id"] in document_case_ids,
                "Question resolution must accompany its own source input correction",
            )
            edit = next(e for e in edits if e["case_id"] == request["case_id"])
            patch = edit["corrected_fields"]
            first = edit["first_case_object"]["literal_pillars"]
            require(
                set(patch) == {"literal_pillars", "anchor"}
                and sum(first[n] != patch["literal_pillars"][n] for n in order) == 1,
                "Only a direct single-pillar glyph correction can resolve a glyph question",
            )
            resolution_requests.append(
                dict(
                    request,
                    resolution_document=path.name,
                    review_protocol=review_name,
                    correction_case_id=request["case_id"],
                )
            )
        documents[path.name] = sha(path)
    question_ids = {digest_value(q): q for q in questions}
    resolved_ids = set()
    for request in resolution_requests:
        identity = request["original_question_sha256"]
        question = request["original_question"]
        require(
            identity == digest_value(question)
            and identity in question_ids
            and question_ids[identity] == question
            and identity not in resolved_ids
            and question["case_id"] == request["case_id"]
            and question["kind"] == "glyph_review_pending"
            and question["review_protocol"] != request["review_protocol"],
            "Question resolution lost original glyph identity or tried to resolve a printed conflict",
        )
        resolved_ids.add(identity)
        question_resolutions.append(request)
    return (
        resolved_cases,
        resolved_claims,
        {
            "source_case_input_resolution_documents_sha256": documents,
            "source_case_input_corrections": corrections,
            "source_case_claim_alignment_reviews": reviews,
            "source_case_input_questions_retained": questions,
            "source_case_input_question_resolutions": question_resolutions,
            "remaining_case_input_questions": [
                q for q in questions if digest_value(q) not in resolved_ids
            ],
        },
    )


def parse_grouped_formula_positions(anchor):
    """Read the explicit 月日/年時 order; never complete an unnamed position."""
    pillar = r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"
    match = re.fullmatch(rf"({pillar})({pillar})月日({pillar})({pillar})年時", anchor)
    require(match is not None, "Formula does not explicitly name all four positions")
    month, day, year, hour = match.groups()
    return dict(year=year, month=month, day=day, hour=hour)


def resolve_grouped_formula_positions(
    cases, claims, study, root, protocol_sha, pdf_sha
):
    """Apply only the separately reviewed two printed formula transcriptions.

    The ordinary case-input resolver still rejects all NULL completion. These
    original-commentary theory examples explicitly print both ordered pairs;
    no date, calendar arithmetic, force label or historical identity is inferred.
    """
    paths = sorted(study.glob("source-formula-position-resolutions-*.json"))
    if not paths:
        return cases, claims, {}
    require(
        len(paths) == 1
        and paths[0].name == "source-formula-position-resolutions-v1.json",
        "Unknown or repeated grouped-formula resolution document",
    )
    binding = read_bound(paths[0])
    require(
        binding
        == {
            "review_plan": GROUPED_FORMULA_PLAN,
            "review_plan_sha256": GROUPED_FORMULA_PLAN_SHA256,
        },
        "Grouped-formula resolution lost its pinned review plan",
    )
    plan_path = root / GROUPED_FORMULA_PLAN
    require(
        sha(plan_path) == GROUPED_FORMULA_PLAN_SHA256, "Formula review plan changed"
    )
    plan = read_bound(plan_path)
    require(
        plan["source_protocol_sha256"] == protocol_sha
        and plan["source_pdf_sha256"] == pdf_sha,
        "Formula review belongs to a different source",
    )
    before_path = root / plan["before_snapshot"]["path"]
    require(
        sha(before_path) == plan["before_snapshot"]["sha256"],
        "Formula preimage changed",
    )
    before = read_bound(before_path)
    require(
        cases == before["resolved_source_cases"]
        and claims == before["resolved_source_claims"],
        "Formula review lost the complete558case/1380claim preimage",
    )
    for relative, expected in plan["evidence"].items():
        require(sha(root / relative) == expected, "Formula evidence image changed")
    require(
        [r["case_id"] for r in plan["resolutions"]] == ["MAIN-C332", "MAIN-C333"]
        and [r["claim_id"] for r in plan["resolutions"]]
        == ["CENSUS-R945", "CENSUS-R946"],
        "Formula review target inventory changed",
    )
    resolved, statements = copy.deepcopy(cases), copy.deepcopy(claims)
    lookup = {c["case_id"]: c for c in resolved}
    receipts = []
    for row in plan["resolutions"]:
        case, claim = lookup[row["case_id"]], statements[row["claim_id"]]
        require(
            all(v is None for v in case["literal_pillars"].values())
            and case["source_text_layer"] == "original_commentary"
            and case["speaker_chain"] == ["原注"]
            and case["kind"] == "source_counterfactual_relational_case"
            and case["anchor"] == row["anchor"]
            and row["claim_id"] in case["claim_ids"]
            and case["expected_daymaster_strength"] is None
            and not case["forbidden_daymaster_strengths"],
            "Formula resolution cannot fill a different unknown case or change a label",
        )
        parsed = parse_grouped_formula_positions(case["anchor"])
        require(
            parsed == row["expected_pillars"],
            "Formula order differs from reviewed reading",
        )
        case["literal_pillars"] = parsed
        case["source_metadata"]["source_condition"] = row["revised_source_condition"]
        case["source_metadata"]["literal_formula_position_provenance"] = {
            "method_id": "explicit_month_day_year_hour_pairs_v1",
            "printed_anchor": case["anchor"],
            "historical_birth_moment_identified": False,
            "strength_label_assigned": False,
            "review_plan_sha256": GROUPED_FORMULA_PLAN_SHA256,
        }
        claim["retained_statement"] = row["revised_retained_statement"]
        receipts.append(
            {
                "case_id": row["case_id"],
                "claim_id": row["claim_id"],
                "literal_formula_positions": parsed,
                "review_plan_sha256": GROUPED_FORMULA_PLAN_SHA256,
            }
        )
    return (
        resolved,
        statements,
        {
            "source_formula_position_documents_sha256": {paths[0].name: sha(paths[0])},
            "source_formula_position_corrections": receipts,
            "raw_complete_literal_cases_retained": sum(
                all(c["literal_pillars"].values()) for c in cases
            ),
        },
    )


def audit(study, root):
    protocol_path = study / "protocol.json"
    protocol = read_bound(protocol_path)
    require(
        sha(root / protocol["source_pdf"]) == protocol["source_pdf_sha256"],
        "Source PDF changed",
    )
    first, last = protocol["complete_physical_page_range"]
    expected = list(range(first, last + 1))
    require(first == 1 and last >= first, "Invalid physical page range")
    inventory = read_bound(study / "page-inventory-before-review.json")
    # The initial inventory is evidence of the original scope, never progress.
    require(
        [p["pdf_page"] for p in inventory["pages"]] == expected,
        "Initial inventory narrowed or reordered",
    )
    require(
        inventory["source_pdf_sha256"] == protocol["source_pdf_sha256"],
        "Initial inventory belongs to a different source",
    )
    addendum = read_bound(study / "source-layer-addendum-before-cases.json")
    require(
        addendum["parent_protocol_sha256"] == sha(protocol_path),
        "Source-layer protocol binding changed",
    )
    layers = set(addendum["allowed_layers"])
    batches, pages, cases, claims, page_uncertainties = {}, [], [], {}, []
    origins, case_origins, page_origins, transcription_warnings = {}, {}, {}, []
    for path in sorted(study.glob("review-batch-*.json")):
        batch = read_bound(path)
        require(
            batch["protocol_sha256"] == sha(protocol_path)
            and batch["source_pdf_sha256"] == protocol["source_pdf_sha256"],
            "Batch belongs to a different source or protocol",
        )
        require(
            batch["page_order"] == [p["pdf_page"] for p in batch["pages"]],
            "Batch page inventory differs from its actual records",
        )
        require(
            batch["strength_or_candidate_evaluation_performed"] is False,
            "Collection batch contains premature calculation",
        )
        for page in batch["pages"]:
            pages.append(page["pdf_page"])
            page_origins[page["pdf_page"]] = {
                "batch": path.name,
                "batch_sha256": sha(path),
                "page": page,
            }
            require(
                page["source_text_layer"] in layers,
                "Missing or unknown source text layer",
            )
            require(
                sha(study / page["image"]) == page["image_sha256"],
                "Page image changed",
            )
            require(
                page["page_case_and_rule_scan_complete"] is True,
                "Unread page included in completed page scans",
            )
            page_uncertainties.extend(
                {"pdf_page": page["pdf_page"], "item": item}
                for item in page.get("uncertainties", [])
            )
            transcription_warnings.extend(
                source_warning(
                    "page", path.name, sha(path), page["pdf_page"], index, item
                )
                for index, item in enumerate(page.get("uncertainties", []))
            )
            cases.extend(page["literal_cases"])
            for case in page["literal_cases"]:
                case_origins[case["case_id"]] = {
                    "batch": path.name,
                    "batch_sha256": sha(path),
                    "pdf_page": page["pdf_page"],
                    "image_sha256": page["image_sha256"],
                }
            for claim in page["technical_rule_claims"]:
                identity = claim["claim_id"]
                require(identity not in claims, "Duplicate source claim ID")
                require(
                    claim["source_text_layer"] in layers
                    and bool(claim["anchor"])
                    and bool(claim["assertion_subject"])
                    and bool(claim["judgment_context"]),
                    "Source claim lost its layer, anchor, actor or context",
                )
                claims[identity] = claim
                origins[identity] = {
                    "batch": path.name,
                    "batch_sha256": sha(path),
                    "pdf_page": page["pdf_page"],
                    "image_sha256": page["image_sha256"],
                }
        batches[path.name] = sha(path)
    require(pages == expected[: len(pages)], "Pages skipped, repeated or reordered")
    seen = set()
    known = 0
    for case in cases:
        require(case["case_id"] not in seen, "Duplicate case ID")
        seen.add(case["case_id"])
        require(case["source_text_layer"] in layers, "Case lost its source layer")
        require(
            set(case["literal_pillars"]) == {"year", "month", "day", "hour"},
            "Incomplete source case must retain all four positions, including nulls",
        )
        grade = case["expected_daymaster_strength"]
        forbidden = case["forbidden_daymaster_strengths"]
        require(grade is None or grade in GRADES, "Invalid exact body grade")
        require(set(forbidden) < GRADES, "Invalid or exhaustive forbidden grades")
        require(grade not in forbidden, "Contradictory body grade within one claim")
        linked = case.get("claim_ids", [])
        require(all(identity in claims for identity in linked), "Dangling case claim")
        if grade is not None or forbidden:
            evidence = case.get("body_judgment_claim_ids", [])
            require(bool(evidence), "Body label has no explicit body judgment")
            for identity in evidence:
                require(identity in linked, "Body evidence not linked to this case")
                claim = claims[identity]
                require(
                    claim["assertion_subject"] in {"daymaster", "day_element"}
                    and claim["judgment_context"] in {"natal", "natal_after_relation"},
                    "Other actor or later-luck statement used as natal body grade",
                )
            require(
                grade is None
                or any(
                    claims[i]["expected_daymaster_strength"] == grade for i in evidence
                ),
                "Exact grade differs from its source claim",
            )
            require(
                set(forbidden).issubset(
                    {
                        g
                        for i in evidence
                        for g in claims[i]["forbidden_daymaster_strengths"]
                    }
                ),
                "Forbidden grade differs from its source claim",
            )
        known += grade is not None
    contexts, context_data, qualification_count = {}, {}, 0
    for path in sorted(study.glob("source-context-*.json")):
        context = read_bound(path)
        require(
            context["protocol_sha256"] == sha(protocol_path)
            and context["source_pdf_sha256"] == protocol["source_pdf_sha256"],
            "Source context belongs to a different protocol or book",
        )
        for qualification in context["qualifications"]:
            targets = {"case": seen, "claim": set(claims)}
            require(
                qualification["target_kind"] in targets
                and qualification["target_id"] in targets[qualification["target_kind"]],
                "Source qualification lost its target",
            )
            require(
                bool(qualification["anchor"]) and bool(qualification["qualification"]),
                "Source qualification lost its anchor or conditions",
            )
            qualification_count += 1
        contexts[path.name] = sha(path)
        context_data[path.name] = context
    resolved_claims, corrections = resolve_source_prose(
        claims, origins, context_data, study
    )
    claims_before_case_alignment_sha = digest_value(resolved_claims)
    resolved_cases, resolved_claims, case_alignment = resolve_case_input_alignment(
        cases,
        resolved_claims,
        case_origins,
        origins,
        study,
        root,
        sha(protocol_path),
        protocol["source_pdf_sha256"],
        original_claims=claims,
    )
    resolved_cases, resolved_claims, formula_alignment = (
        resolve_grouped_formula_positions(
            resolved_cases,
            resolved_claims,
            study,
            root,
            sha(protocol_path),
            protocol["source_pdf_sha256"],
        )
    )
    resolved_sha256 = hashlib.sha256(
        json.dumps(
            resolved_claims, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    all_pages = pages == expected
    full_page_progress_uncertainties, progress_records = [], []
    for path in sorted(study.glob("progress-*.json")):
        progress = read_bound(path)
        prefix = progress["reviewed_pages"]
        require(prefix == pages[: len(prefix)], "Progress page list is not a prefix")
        require(
            progress["whole_book_collection_complete"] is False or all_pages,
            "Premature full-book completion claim",
        )
        progress_records.append(progress)
        if prefix == expected:
            full_page_progress_uncertainties.extend(
                {"progress_document": path.name, "item": item}
                for item in progress.get("unresolved_items_retained", [])
            )
            for index, item in enumerate(progress.get("unresolved_items_retained", [])):
                match = re.match(r"^Page(\d+)(?:\D|$)", item)
                transcription_warnings.append(
                    source_warning(
                        "full_page_progress",
                        path.name,
                        sha(path),
                        int(match[1]) if match else None,
                        index,
                        item,
                    )
                )
    transcription = resolve_transcription_metadata(
        study,
        sha(protocol_path),
        protocol["source_pdf_sha256"],
        transcription_warnings,
        page_origins,
    )
    frozen = False
    freeze_path = study / "collection-freeze.json"
    if freeze_path.exists():
        freeze = read_bound(freeze_path)
        require(all_pages, "Incomplete book cannot be frozen as complete")
        require(
            freeze["protocol_sha256"] == sha(protocol_path)
            and freeze["source_pdf_sha256"] == protocol["source_pdf_sha256"]
            and freeze["batches_sha256"] == batches,
            "Whole-book freeze does not bind every original batch",
        )
        require(
            freeze.get("context_documents_sha256", {}) == contexts,
            "Whole-book freeze omitted source qualifications",
        )
        if corrections:
            require(
                freeze.get("resolved_source_claims_sha256") == resolved_sha256,
                "Whole-book freeze omitted resolved reader corrections",
            )
        if case_alignment["source_case_input_resolution_documents_sha256"]:
            require(
                freeze.get("source_case_input_resolution_documents_sha256")
                == case_alignment["source_case_input_resolution_documents_sha256"]
                and freeze.get("resolved_source_cases_sha256")
                == digest_value(resolved_cases)
                and freeze.get("resolved_source_claims_sha256") == resolved_sha256,
                "Whole-book freeze omitted case input and claim alignment bindings",
            )
            require(
                not case_alignment["remaining_case_input_questions"],
                "Unresolved source-case input questions prevent comparison",
            )
        if formula_alignment:
            require(
                freeze.get("source_formula_position_documents_sha256")
                == formula_alignment["source_formula_position_documents_sha256"]
                and freeze.get("resolved_source_cases_sha256")
                == digest_value(resolved_cases)
                and freeze.get("resolved_source_claims_sha256") == resolved_sha256,
                "Whole-book freeze omitted grouped-formula source bindings",
            )
        require(
            freeze["remaining_transcription_uncertainties"] == [],
            "Unresolved transcription prevents comparison",
        )
        if transcription["page_metadata_corrections"]:
            require(
                all(
                    freeze.get(key) == transcription[key]
                    for key in [
                        "transcription_resolution_documents_sha256",
                        "transcription_warning_inventory_sha256",
                        "resolved_page_metadata_sha256",
                    ]
                ),
                "Whole-book freeze omitted transcription resolution bindings",
            )
        require(
            not transcription["remaining_transcription_warnings"],
            "Retained source uncertainty prevents comparison",
        )
        frozen = True
    for progress in progress_records:
        require(
            progress["candidate_evaluation_allowed"] is False or frozen,
            "Partial or unfrozen collection allows candidate evaluation",
        )
    return {
        "collection_integrity_passed": True,
        "source_pdf_sha256": protocol["source_pdf_sha256"],
        "batches_sha256": batches,
        "context_documents_sha256": contexts,
        "source_qualifications_retained": qualification_count,
        "source_prose_corrections": corrections,
        "resolved_source_claims_sha256": resolved_sha256,
        "resolved_source_claims_before_case_alignment_sha256": claims_before_case_alignment_sha,
        "resolved_source_cases_sha256": digest_value(resolved_cases),
        "resolved_source_cases": resolved_cases,
        "resolved_source_claims": resolved_claims,
        **case_alignment,
        **formula_alignment,
        "reviewed_pages": len(pages),
        "total_physical_pages": len(expected),
        "next_page": expected[len(pages)] if not all_pages else None,
        "literal_case_records": len(cases),
        "complete_literal_cases": sum(
            all(c["literal_pillars"].values()) for c in resolved_cases
        ),
        "exact_body_labels": known,
        "unknown_body_labels_retained": len(cases) - known,
        "source_claim_records": len(claims),
        "page_uncertainties_retained": page_uncertainties,
        "full_page_progress_uncertainties_retained": full_page_progress_uncertainties,
        **transcription,
        "all_physical_pages_scanned": all_pages,
        "whole_book_collection_frozen": frozen,
        "candidate_evaluation_allowed": frozen,
        "new_model_executions": 0,
        "independent_annotation_review": "not_certified",
        "semantic_annotation_correctness": "not_certified",
        "production_changed": False,
        "original_gates_superseded": False,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    require(not args.output.exists(), "Output already exists")
    result = audit(args.study, ROOT)
    result["require_complete"] = args.require_complete
    result["command_gate_passed"] = (
        result["whole_book_collection_frozen"] if args.require_complete else True
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"batches_sha256", "page_uncertainties_retained"}
            },
            ensure_ascii=False,
        )
    )
    return int(not result["command_gate_passed"])


if __name__ == "__main__":
    raise SystemExit(main())

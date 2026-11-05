"""Earth source readings preserve unresolved glyphs and past clear errors."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.core.canping_texts import lookup_record
from fatebridge.core.output_numerology import CanpingReadingRevision
from fatebridge.utils.errors import NumerologySourceError
from tests.numerology.test_canping_rereading_depth import jpeg_dimensions


def test_inherited_corpus_callers_cannot_poison_source_cache_or_its_provenance(
    monkeypatch,
):
    original = texts._loaded
    loaded = copy.deepcopy(original(texts.INHERITED_PATH))
    monkeypatch.setattr(
        texts,
        "_loaded",
        lambda path: loaded if path == texts.INHERITED_PATH else original(path),
    )
    before = lookup_record("火", 2838, "male")["selection"]["inherited_text"]
    before_hash = texts.collation_summary()["inherited_corpus_sha256"]
    detached = texts.inherited_corpus()
    detached["parts"]["火"]["3838"]["male"] = "caller mutation"
    assert lookup_record("火", 2838, "male")["selection"]["inherited_text"] == before
    assert texts.inherited_corpus()["parts"]["火"]["3838"]["male"] == before
    assert texts.collation_summary()["inherited_corpus_sha256"] == before_hash


ROOT = Path(__file__).parents[1] / "fixtures/canping_earth_rereading_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
CELLS = REFERENCE["cells"]


@pytest.mark.parametrize("cell", CELLS)
def test_earth_revisions_keep_the_actual_previous_status(cell):
    out = lookup_record("土", cell["number"], cell["kind"])
    s = out["selection"]
    r = s["reading_revision"]
    assert out["text"] == cell["text"] and s["cell_status"] == cell["state"]
    assert (
        r["previous_text"] == cell["previous_text"]
        and r["previous_cell_status"] == cell["previous_cell_status"]
    )
    assert (
        r["previous_collation_version"] == "1.10.0"
        and r["rereading_id"] == REFERENCE["fixture_id"]
    )
    assert s["source_pdf_page"] == r["source_pdf_page"] == cell["pdf_page"]
    assert r["note"] == cell["note"]
    assert ("editorial_unknown_marker" in s) == ("□" in cell["text"])
    assert bool(s.get("reading_uncertainties")) == ("□" in cell["text"])
    assert "number_attribution_status" not in s
    CanpingReadingRevision.model_validate(r)


@pytest.mark.parametrize("page", REFERENCE["pages"])
def test_three_native_pages_keep_source_identity_and_full_coordinate_coverage(page):
    m = json.loads((ROOT / REFERENCE["source_manifest_file"]).read_text())
    c = m["sequences"][0]["canvases"][page["pdf_page"] - 1]
    assert [c["width"], c["height"]] == page["canvas_dimensions"] == [5900, 4400]
    assert {tuple(r["region"]) for r in page["regions"]} == {
        (0, 0, 2950, 2200),
        (2950, 0, 2950, 2200),
        (0, 2200, 2950, 2200),
        (2950, 2200, 2950, 2200),
    }
    for r in page["regions"]:
        raw = (ROOT / r["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == r["sha256"] and jpeg_dimensions(
            raw
        ) == (2950, 2200)
        assert r["canvas"] == c["@id"] and r["reused_prior_region"] is False
        assert r["url"].endswith(
            "/" + ",".join(map(str, r["region"])) + "/full/0/native.jpg"
        )


def test_earth_clear_correction_does_not_count_as_another_resolved_uncertainty():
    old = json.loads((ROOT.parent / "canping_earth_v1/reference.json").read_text())
    assert (
        old["unambiguous_earth_cells"] == 231 and old["unresolved_reading_cells"] == 3
    )
    uncertain = [
        c for c in CELLS if c["previous_cell_status"] == "source_reading_uncertain"
    ]
    clear = [
        c for c in CELLS if c["previous_cell_status"] == "source_cell_visually_collated"
    ]
    assert len(CELLS) == REFERENCE["reviewed_cells"] == 3
    assert len(uncertain) == REFERENCE["reviewed_previous_uncertain_cells"] == 3
    assert len(clear) == REFERENCE["corrected_previously_clear_cells"] == 0
    assert REFERENCE["reviewed_previous_clear_cells"] == 1
    assert (
        sum(c["state"] == "source_cell_visually_collated" for c in uncertain)
        == REFERENCE["resolved_cells"]
        == 1
    )
    assert (
        sum(c["state"] == "source_reading_uncertain" for c in uncertain)
        == REFERENCE["still_uncertain_cells"]
        == 2
    )
    assert {(c["number"], c["kind"]) for c in uncertain} == {
        (c["number"], c["kind"]) for c in old["uncertain_cells"]
    }
    comparison = REFERENCE["comparison_cells"][0]
    assert (
        comparison["text"]
        == lookup_record("土", 3379, "male")["text"]
        == "八尺長燈檠，清光射白晝。"
    )
    assert not comparison["text_changed"] and not comparison["prior_state_changed"]
    assert "reading_revision" not in lookup_record("土", 3379, "male")["selection"]
    assert len(REFERENCE["withdrawn_draft_readings"]) == 1
    assert (
        REFERENCE["native_region_count"],
        REFERENCE["reused_region_count"],
        REFERENCE["new_stored_region_count"],
    ) == (12, 0, 12)
    for f, h in [
        (REFERENCE["literal_file"], REFERENCE["literal_sha256"]),
        (REFERENCE["source_manifest_file"], REFERENCE["source_manifest_sha256"]),
        (REFERENCE["glyph_reference_file"], REFERENCE["glyph_reference_sha256"]),
    ]:
        assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h
    for k in (
        "new_numbered_cells_examined",
        "new_independent_reviews",
        "new_classical_birth_examples",
        "new_independent_calendar_instants",
        "new_real_world_outcomes",
    ):
        assert REFERENCE[k] == 0
    glyph = json.loads((ROOT / REFERENCE["glyph_reference_file"]).read_text())
    assert (
        glyph["scope"]
        == "ancillary_unicode_glyph_identification_only; no_classical_edition_or_word_sense_confirmation"
    )
    s = texts.collation_summary()
    assert (
        s["collated_cells"] == 1123
        and s["unresolved_reading_cells"] == s["pending_cells"] == 47
    )
    assert (
        s["total_cells"] == s["visually_examined_cells"] == 1170
        and s["unexamined_cells"] == 0
    )
    assert (
        s["part_coverage"]["土"]["collated_cells"] == 232
        and s["part_coverage"]["土"]["unresolved_reading_cells"] == 2
    )
    assert (
        "10/11/13/11/2 (47 total)." in s["scope"] and "1122 of 1170" not in s["scope"]
    )
    assert (
        s["rereading_witness"]["resolved_cells"] == 30
        and s["rereading_witness"]["still_uncertain_cells"] == 10
    )
    extra = {w["fixture_id"]: w for w in s["additional_rereading_witnesses"]}
    assert len(extra) == 4
    for part, counts in [
        ("fire", (6, 5)),
        ("wood", (3, 1)),
        ("gold", (4, 11)),
        ("earth", (1, 2)),
    ]:
        w = extra[f"canping_{part}_native_rereading_v1"]
        assert (w["resolved_cells"], w["still_uncertain_cells"]) == counts
    assert s["number_reading_witness"]["headers_still_uncertain"] == 6
    assert not s["numbered_table_clear_readings_complete"]


@pytest.mark.parametrize("number,kind", [(2460, "luck"), (3363, "luck")])
def test_two_earth_unreadable_ends_remain_uncertain(number, kind):
    out = lookup_record("土", number, kind)
    assert (
        "□" in out["text"]
        and out["selection"]["cell_status"] == "source_reading_uncertain"
    )


@pytest.mark.parametrize("change", ["remove_earth", "duplicate_earth", "wrong_batch"])
def test_earth_rereading_requires_its_own_witness(monkeypatch, change):
    original = texts._loaded
    loaded = copy.deepcopy(original(texts.COLLATION_PATH))
    d = loaded["data"]
    if change == "remove_earth":
        d["additional_rereading_witnesses"] = [
            w
            for w in d["additional_rereading_witnesses"]
            if w["fixture_id"] != REFERENCE["fixture_id"]
        ]
    elif change == "duplicate_earth":
        d["additional_rereading_witnesses"].append(
            copy.deepcopy(
                next(
                    w
                    for w in d["additional_rereading_witnesses"]
                    if w["fixture_id"] == REFERENCE["fixture_id"]
                )
            )
        )
    else:
        next(e for e in d["entries"] if (e["element"], e["number"]) == ("土", 3377))[
            "reading_revisions"
        ]["female"]["rereading_id"] = "canping_gold_native_rereading_v1"
    monkeypatch.setattr(
        texts, "_loaded", lambda p: loaded if p == texts.COLLATION_PATH else original(p)
    )
    with pytest.raises(ValueError, match="复读"):
        texts._collation()
    with pytest.raises(NumerologySourceError) as error:
        texts.collation_summary()
    assert error.value.reason == "invalid_canping_text_collation"
    assert isinstance(error.value.__cause__, ValueError)
    assert "复读" in str(error.value.__cause__)
    assert error.value.as_result()["status_code"] == 503
    assert error.value.as_result()["retryable"] is False

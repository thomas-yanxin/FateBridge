"""Fire rereadings retain uncertain glyphs and revise more than placeholders."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.core.canping_texts import lookup_record
from fatebridge.utils.errors import NumerologySourceError
from tests.numerology.test_canping_rereading_depth import jpeg_dimensions

ROOT = Path(__file__).parents[1] / "fixtures/canping_fire_rereading_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
CELLS = REFERENCE["cells"]


@pytest.mark.parametrize("cell", CELLS)
def test_all_eleven_fire_revisions_keep_prior_reading_and_specific_witness(cell):
    result = lookup_record("火", cell["number"], cell["kind"])
    s = result["selection"]
    assert result["text"] == cell["text"] and s["cell_status"] == cell["state"]
    assert s["source_pdf_page"] == cell["pdf_page"]
    r = s["reading_revision"]
    assert r["rereading_id"] == REFERENCE["fixture_id"]
    assert r["previous_collation_version"] == "1.7.0"
    assert r["previous_text"] == cell["previous_text"]
    assert r["previous_cell_status"] == "source_reading_uncertain"
    assert r["note"] == cell["note"]
    assert ("editorial_unknown_marker" in s) == ("□" in cell["text"])
    assert bool(s.get("reading_uncertainties")) == ("□" in cell["text"])
    if "□" in cell["text"]:
        assert s["reading_uncertainties"] == [cell["note"]]


@pytest.mark.parametrize("page", REFERENCE["pages"])
def test_six_native_pages_keep_actual_pixels_and_reused_region_identity(page):
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
        assert hashlib.sha256(raw).hexdigest() == r["sha256"]
        assert jpeg_dimensions(raw) == (2950, 2200)
        assert r["canvas"] == c["@id"]
        assert r["url"].endswith(
            "/" + ",".join(map(str, r["region"])) + "/full/0/native.jpg"
        )
        assert r["reused_prior_region"] == (page["pdf_page"] in (77, 80))


def test_fire_rereading_adds_only_six_confirmed_cells_and_keeps_prior_witnesses():
    assert len(CELLS) == REFERENCE["reviewed_previous_uncertain_cells"] == 11
    assert (
        sum(c["state"] == "source_cell_visually_collated" for c in CELLS)
        == REFERENCE["resolved_cells"]
        == 6
    )
    assert (
        sum(c["state"] == "source_reading_uncertain" for c in CELLS)
        == REFERENCE["still_uncertain_cells"]
        == 5
    )
    for file, digest in [
        (REFERENCE["literal_file"], REFERENCE["literal_sha256"]),
        (REFERENCE["source_manifest_file"], REFERENCE["source_manifest_sha256"]),
    ]:
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest
    assert (
        REFERENCE["native_region_count"] == 24
        and REFERENCE["reused_region_count"] == 8
        and REFERENCE["new_stored_region_count"] == 16
    )
    for k in (
        "new_numbered_cells_examined",
        "new_independent_reviews",
        "new_classical_birth_examples",
        "new_independent_calendar_instants",
        "new_real_world_outcomes",
    ):
        assert REFERENCE[k] == 0
    old = json.loads((ROOT.parent / "canping_fire_v1/reference.json").read_text())
    assert len(old["uncertain_cells"]) == 17
    s = texts.collation_summary()
    assert (
        "Current unresolved water/fire/wood/gold/earth cells: 10/11/13/11/2 (47 total)."
        in s["scope"]
    )
    assert (
        s["collated_cells"] == 1123
        and s["unresolved_reading_cells"] == s["pending_cells"] == 47
    )
    assert (
        s["part_coverage"]["火"]["collated_cells"] == 223
        and s["part_coverage"]["火"]["unresolved_reading_cells"] == 11
    )
    assert (
        s["total_cells"] == s["visually_examined_cells"] == 1170
        and s["unexamined_cells"] == 0
    )
    assert not s["numbered_table_clear_readings_complete"]
    assert (
        s["rereading_witness"]["resolved_cells"] == 30
        and s["rereading_witness"]["still_uncertain_cells"] == 10
    )
    assert (
        s["additional_rereading_witnesses"][0]["fixture_id"] == REFERENCE["fixture_id"]
    )
    assert s["additional_rereading_witnesses"][0]["resolved_cells"] == 6
    assert s["number_reading_witness"]["headers_still_uncertain"] == 6


@pytest.mark.parametrize(
    "number,kind",
    [(3141, "male"), (2741, "luck"), (3341, "luck"), (3345, "luck"), (2347, "luck")],
)
def test_retained_ambiguities_are_not_counted_or_filled_from_meaning(number, kind):
    result = lookup_record("火", number, kind)
    assert (
        "□" in result["text"]
        and result["selection"]["cell_status"] == "source_reading_uncertain"
    )
    assert result["selection"]["reading_uncertainties"]


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_witness",
        "missing_fire_witness",
        "water_revision_given_fire_witness",
        "fire_revision_given_water_witness",
    ],
)
def test_multiple_rereadings_cannot_overwrite_or_misattribute_prior_evidence(
    monkeypatch, change
):
    original = texts._loaded
    loaded = copy.deepcopy(original(texts.COLLATION_PATH))
    d = loaded["data"]
    if change == "duplicate_witness":
        d["additional_rereading_witnesses"].append(
            copy.deepcopy(d["rereading_witness"])
        )
    elif change == "missing_fire_witness":
        d["additional_rereading_witnesses"] = [
            w
            for w in d["additional_rereading_witnesses"]
            if w["fixture_id"] != REFERENCE["fixture_id"]
        ]
    elif change == "water_revision_given_fire_witness":
        next(e for e in d["entries"] if (e["element"], e["number"]) == ("水", 3241))[
            "reading_revisions"
        ]["female"]["rereading_id"] = REFERENCE["fixture_id"]
    else:
        next(e for e in d["entries"] if (e["element"], e["number"]) == ("火", 2543))[
            "reading_revisions"
        ]["luck"]["rereading_id"] = d["rereading_witness"]["fixture_id"]
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


def test_separate_fire_witness_and_revision_objects_are_isolated():
    s = texts.collation_summary()
    s["additional_rereading_witnesses"][0]["pages"].clear()
    r = lookup_record("火", 2543, "luck")
    r["selection"]["reading_revision"]["previous_text"] = "changed"
    assert (
        len(texts.collation_summary()["additional_rereading_witnesses"][0]["pages"])
        == 6
    )
    assert (
        lookup_record("火", 2543, "luck")["selection"]["reading_revision"][
            "previous_text"
        ]
        == "田獵無一禽，徒勞費鴛□。"
    )

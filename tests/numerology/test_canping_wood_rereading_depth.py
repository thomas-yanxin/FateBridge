"""Native wood readings keep unusual literals and remaining ambiguous glyphs."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.core.canping_texts import lookup_record
from fatebridge.utils.errors import NumerologySourceError
from tests.numerology.test_canping_rereading_depth import jpeg_dimensions


@pytest.mark.parametrize(
    "number,kind,text",
    [
        (2206, "male", "洞庭風葉舞，撫手上南山。"),
        (2412, "male", "玉藍凝絲竹，蟾宮火上山。"),
        (2519, "luck", "遇水得逢橋，憂心傾□然。"),
    ],
)
def test_native_wood_rereadings_are_selected(number, kind, text):
    assert lookup_record("木", number, kind)["text"] == text


ROOT = Path(__file__).parents[1] / "fixtures/canping_wood_rereading_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
CELLS = REFERENCE["cells"]


@pytest.mark.parametrize("cell", CELLS)
def test_all_four_wood_revisions_retain_the_prior_reading_and_specific_witness(cell):
    out = lookup_record("木", cell["number"], cell["kind"])
    s = out["selection"]
    r = s["reading_revision"]
    assert out["text"] == cell["text"] and s["cell_status"] == cell["state"]
    assert s["source_pdf_page"] == cell["pdf_page"]
    assert (
        r["rereading_id"] == REFERENCE["fixture_id"]
        and r["previous_collation_version"] == "1.8.0"
    )
    assert (
        r["previous_text"] == cell["previous_text"]
        and r["previous_cell_status"] == "source_reading_uncertain"
    )
    assert r["note"] == cell["note"] and r["source_pdf_page"] == cell["pdf_page"]
    assert ("editorial_unknown_marker" in s) == ("□" in cell["text"])
    assert bool(s.get("reading_uncertainties")) == ("□" in cell["text"])
    assert "number_attribution_status" not in s


@pytest.mark.parametrize("page", REFERENCE["pages"])
def test_four_native_pages_keep_pixels_source_identity_and_explicit_reuse(page):
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
        assert r["reused_prior_region"] == (page["pdf_page"] in (84, 86))


def test_only_three_confirmed_cells_are_added_and_all_old_witnesses_remain():
    assert len(CELLS) == REFERENCE["reviewed_previous_uncertain_cells"] == 4
    assert (
        sum(c["state"] == "source_cell_visually_collated" for c in CELLS)
        == REFERENCE["resolved_cells"]
        == 3
    )
    assert (
        sum(c["state"] == "source_reading_uncertain" for c in CELLS)
        == REFERENCE["still_uncertain_cells"]
        == 1
    )
    assert (
        REFERENCE["native_region_count"],
        REFERENCE["reused_region_count"],
        REFERENCE["new_stored_region_count"],
    ) == (16, 8, 8)
    for f, h in [
        (REFERENCE["literal_file"], REFERENCE["literal_sha256"]),
        (REFERENCE["source_manifest_file"], REFERENCE["source_manifest_sha256"]),
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
    old = json.loads((ROOT.parent / "canping_wood_v1/reference.json").read_text())
    assert (
        len(old["uncertain_cells"]) == 16 and old["new_unambiguous_wood_cells"] == 218
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
        s["part_coverage"]["木"]["collated_cells"] == 221
        and s["part_coverage"]["木"]["unresolved_reading_cells"] == 13
    )
    assert (
        "Current unresolved water/fire/wood/gold/earth cells: 10/11/13/11/2 (47 total)."
        in s["scope"]
    )
    assert "1115 clear" not in s["scope"] and "55 total" not in s["scope"]
    assert s["rereading_witness"]["fixture_id"] == "canping_water_native_rereading_v1"
    assert (
        s["rereading_witness"]["resolved_cells"],
        s["rereading_witness"]["still_uncertain_cells"],
    ) == (30, 10)
    extra = {w["fixture_id"]: w for w in s["additional_rereading_witnesses"]}
    assert len(extra) == 4
    assert (
        extra["canping_fire_native_rereading_v1"]["resolved_cells"],
        extra["canping_fire_native_rereading_v1"]["still_uncertain_cells"],
    ) == (6, 5)
    assert (
        extra[REFERENCE["fixture_id"]]["resolved_cells"],
        extra[REFERENCE["fixture_id"]]["still_uncertain_cells"],
    ) == (3, 1)
    assert (
        s["number_reading_witness"]["headers_still_uncertain"] == 6
        and s["number_reading_witness"]["headers_resolved"] == 0
    )
    assert not s["numbered_table_clear_readings_complete"]


def test_reading_one_of_two_unknown_glyphs_does_not_confirm_the_whole_cell():
    r = lookup_record("木", 2519, "luck")
    s = r["selection"]
    assert r["text"] == "遇水得逢橋，憂心傾□然。"
    assert (
        s["cell_status"] == "source_reading_uncertain"
        and s["editorial_unknown_marker"] == "□"
    )
    assert s["reading_uncertainties"] and "疑似什" in s["reading_uncertainties"][0]
    assert s["reading_revision"]["previous_text"] == "遇水得逢橋，憂心□□然。"


@pytest.mark.parametrize(
    "change", ["remove_wood_only", "duplicate_wood_id", "wood_revision_given_fire_id"]
)
def test_wood_rereading_cannot_be_lost_duplicated_or_attributed_to_fire(
    monkeypatch, change
):
    original = texts._loaded
    loaded = copy.deepcopy(original(texts.COLLATION_PATH))
    d = loaded["data"]
    if change == "remove_wood_only":
        d["additional_rereading_witnesses"] = [
            w
            for w in d["additional_rereading_witnesses"]
            if w["fixture_id"] != REFERENCE["fixture_id"]
        ]
    elif change == "duplicate_wood_id":
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
        next(e for e in d["entries"] if (e["element"], e["number"]) == ("木", 2412))[
            "reading_revisions"
        ]["male"]["rereading_id"] = "canping_fire_native_rereading_v1"
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


def test_wood_witness_and_previous_reading_are_separate_copies():
    s = texts.collation_summary()
    next(
        w
        for w in s["additional_rereading_witnesses"]
        if w["fixture_id"] == REFERENCE["fixture_id"]
    )["pages"].clear()
    r = lookup_record("木", 2206, "male")
    r["selection"]["reading_revision"]["previous_text"] = "changed"
    assert (
        len(
            next(
                w
                for w in texts.collation_summary()["additional_rereading_witnesses"]
                if w["fixture_id"] == REFERENCE["fixture_id"]
            )["pages"]
        )
        == 4
    )
    assert (
        lookup_record("木", 2206, "male")["selection"]["reading_revision"][
            "previous_text"
        ]
        == "洞庭風葉舞，□手上南山。"
    )

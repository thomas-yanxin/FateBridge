"""Native gold rereadings retain uncertain spans and the historical record."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.core.canping_texts import lookup_record
from fatebridge.utils.errors import NumerologySourceError
from tests.test_canping_rereading_depth import jpeg_dimensions


@pytest.mark.parametrize(
    "number,kind,text",
    [
        (2914, "male", "御苑溝渠裏，翩翩一點紅。"),
        (2209, "luck", "冒暑去投林，當途風少息。"),
        (2514, "male", "蝴蝶在林中，採花爲麴蘖。"),
        (2221, "luck", "臨春花柳香，好遂追遊世。"),
        (3314, "luck", "蕙蘭花□，各自逞馨香。"),
    ],
)
def test_native_gold_rereadings_are_selected(number, kind, text):
    assert lookup_record("金", number, kind)["text"] == text


ROOT = Path(__file__).parent / "fixtures/canping_gold_rereading_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
CELLS = REFERENCE["cells"]


@pytest.mark.parametrize("cell", CELLS)
def test_gold_revisions_retain_old_text_state_version_and_source(cell):
    out = lookup_record("金", cell["number"], cell["kind"])
    s = out["selection"]
    r = s["reading_revision"]
    assert out["text"] == cell["text"] and s["cell_status"] == cell["state"]
    assert s["source_pdf_page"] == cell["pdf_page"]
    assert r["rereading_id"] == REFERENCE["fixture_id"]
    assert r["previous_collation_version"] == "1.9.0"
    assert r["previous_text"] == cell["previous_text"]
    assert r["previous_cell_status"] == "source_reading_uncertain"
    assert r["note"] == cell["note"] and r["source_pdf_page"] == cell["pdf_page"]
    assert ("editorial_unknown_marker" in s) == ("□" in cell["text"])
    assert bool(s.get("reading_uncertainties")) == ("□" in cell["text"])
    assert "number_attribution_status" not in s


@pytest.mark.parametrize("page", REFERENCE["pages"])
def test_seven_native_gold_pages_keep_source_pixels_and_coordinates(page):
    manifest = json.loads((ROOT / REFERENCE["source_manifest_file"]).read_text())
    canvas = manifest["sequences"][0]["canvases"][page["pdf_page"] - 1]
    assert (
        [canvas["width"], canvas["height"]] == page["canvas_dimensions"] == [5900, 4400]
    )
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
        assert r["canvas"] == canvas["@id"]
        assert r["url"].endswith(
            "/" + ",".join(map(str, r["region"])) + "/full/0/native.jpg"
        )
        assert r["reused_prior_region"] is False


def test_only_four_whole_cells_gain_clear_status_and_prior_batches_stay_separate():
    assert len(CELLS) == REFERENCE["reviewed_previous_uncertain_cells"] == 15
    assert (
        sum(c["state"] == "source_cell_visually_collated" for c in CELLS)
        == REFERENCE["resolved_cells"]
        == 4
    )
    assert (
        sum(c["state"] == "source_reading_uncertain" for c in CELLS)
        == REFERENCE["still_uncertain_cells"]
        == 11
    )
    assert (
        REFERENCE["native_region_count"],
        REFERENCE["reused_region_count"],
        REFERENCE["new_stored_region_count"],
    ) == (28, 0, 28)
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
    old = json.loads((ROOT.parent / "canping_gold_v1/reference.json").read_text())
    assert (
        old["unambiguous_gold_cells"] == 219 and old["unresolved_reading_cells"] == 15
    )
    assert {(c["number"], c["kind"]) for c in CELLS} == {
        (int(c["number"]), c["kind"])
        for c in old["expected_special_states"]
        if c["state"] == "source_reading_uncertain"
    }
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
        s["part_coverage"]["金"]["collated_cells"] == 223
        and s["part_coverage"]["金"]["unresolved_reading_cells"] == 11
    )
    assert (
        "Current unresolved water/fire/wood/gold/earth cells: 10/11/13/11/2 (47 total)."
        in s["scope"]
    )
    assert "1118 of 1170" not in s["scope"] and "52 total" not in s["scope"]
    assert (
        s["rereading_witness"]["resolved_cells"],
        s["rereading_witness"]["still_uncertain_cells"],
    ) == (30, 10)
    extra = {w["fixture_id"]: w for w in s["additional_rereading_witnesses"]}
    assert len(extra) == 4
    for part, counts in [("fire", (6, 5)), ("wood", (3, 1)), ("gold", (4, 11))]:
        w = extra[f"canping_{part}_native_rereading_v1"]
        assert (w["resolved_cells"], w["still_uncertain_cells"]) == counts
    assert (
        s["number_reading_witness"]["headers_resolved"] == 0
        and s["number_reading_witness"]["headers_still_uncertain"] == 6
    )
    assert not s["numbered_table_clear_readings_complete"]


def test_partial_flower_reading_cannot_borrow_same_number_female_completion():
    r = lookup_record("金", 3314, "luck")
    s = r["selection"]
    assert r["text"] == "蕙蘭花□，各自逞馨香。"
    assert (
        s["cell_status"] == "source_reading_uncertain"
        and s["editorial_unknown_marker"] == "□"
    )
    assert "不得抄同號女文" in s["reading_uncertainties"][0]
    assert s["reading_revision"]["previous_text"] == "蕙蘭□，各自逞馨香。"
    assert lookup_record("金", 3314, "female")["text"] == "蕙蘭花一處，各自逞馨香。"


@pytest.mark.parametrize(
    "change", ["remove_gold", "duplicate_gold", "gold_revision_given_wood_id"]
)
def test_gold_rereading_requires_its_own_unique_witness(monkeypatch, change):
    original = texts._loaded
    loaded = copy.deepcopy(original(texts.COLLATION_PATH))
    d = loaded["data"]
    if change == "remove_gold":
        d["additional_rereading_witnesses"] = [
            w
            for w in d["additional_rereading_witnesses"]
            if w["fixture_id"] != REFERENCE["fixture_id"]
        ]
    elif change == "duplicate_gold":
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
        next(e for e in d["entries"] if (e["element"], e["number"]) == ("金", 2914))[
            "reading_revisions"
        ]["male"]["rereading_id"] = "canping_wood_native_rereading_v1"
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


def test_gold_witness_and_old_reading_are_isolated_copies():
    s = texts.collation_summary()
    next(
        w
        for w in s["additional_rereading_witnesses"]
        if w["fixture_id"] == REFERENCE["fixture_id"]
    )["pages"].clear()
    r = lookup_record("金", 2914, "male")
    r["selection"]["reading_revision"]["previous_text"] = "changed"
    assert (
        len(
            next(
                w
                for w in texts.collation_summary()["additional_rereading_witnesses"]
                if w["fixture_id"] == REFERENCE["fixture_id"]
            )["pages"]
        )
        == 7
    )
    assert (
        lookup_record("金", 2914, "male")["selection"]["reading_revision"][
            "previous_text"
        ]
        == "□苑溝渠裏，翩翩一點紅。"
    )

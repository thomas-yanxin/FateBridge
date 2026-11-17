"""Primary 1900 table, leap-month edges and protected audit denominator."""

import copy
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from fatebridge.validation.meihua_calendar import (
    audit_tam_1900,
    reference_bundle,
    tam_calendar_rows,
)

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_calendar_v2"


def cells():
    return json.loads((REFERENCES / "cells.json").read_text())["cells"]


def test_all_supported_1900_dates_match_primary_labels_in_declared_zones():
    report = audit_tam_1900(REFERENCES)
    assert report["primary_printed_date_count"] == 365
    assert report["unique_supported_date_count"] == 365
    assert report["excluded_before_supported_start"] == 0
    assert report["newly_supported_prefix_count"] == 30
    assert report["first_supported_date"] == "1900-01-01"
    assert report["last_supported_date"] == "1900-12-31"
    assert {r["timezone"] for r in report["reports"]} == {"Asia/Shanghai", "UTC+08:00"}
    assert report["selected_checks_passed"]
    assert not report["real_world_predictive_efficacy_established"]


def test_printed_leap_eighth_month_and_year_boundary():
    _, rows = reference_bundle(REFERENCES)
    by_date = {r["date"].isoformat(): r for r in rows}
    expected = {
        "1900-01-01": (1899, 12, 1, False),
        "1900-01-31": (1900, 1, 1, False),
        "1900-02-28": (1900, 1, 29, False),
        "1900-09-23": (1900, 8, 30, False),
        "1900-09-24": (1900, 8, 1, True),
        "1900-10-22": (1900, 8, 29, True),
        "1900-10-23": (1900, 9, 1, False),
        "1900-12-31": (1900, 11, 10, False),
    }
    for d, expected_row in expected.items():
        assert (
            tuple(by_date[d][k] for k in ("year", "month", "day", "is_leap_month"))
            == expected_row
        )
    assert len({r["date"] for r in rows}) == 365


@pytest.mark.parametrize(
    "mutation", ["removed", "duplicate", "day_gap", "wrong_leap", "invalid_gregorian"]
)
def test_source_decoder_rejects_omission_and_bad_transcriptions(mutation):
    records = copy.deepcopy(cells())
    if mutation == "removed":
        records.pop()
    elif mutation == "duplicate":
        records[1] = records[0]
    elif mutation == "day_gap":
        records[1]["printed_label"] = "初三"
    elif mutation == "wrong_leap":
        next(r for r in records if r["date"] == "1900-09-24")[
            "printed_label"
        ] = "閏七月"
    else:
        records[59]["date"] = "1900-02-29"
    with pytest.raises(ValueError):
        tam_calendar_rows(records, initial_lunar_year=1899)


def test_changed_primary_material_cannot_silently_become_a_new_oracle(tmp_path):
    target = tmp_path / "refs"
    shutil.copytree(REFERENCES, target)
    p = target / "cells.json"
    p.write_text(p.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        reference_bundle(target)


@pytest.mark.parametrize(
    "mutation",
    [None, "outside", "other_shared_scan", "changed", "rehashed", "redirected"],
)
def test_only_registered_shared_original_is_allowed_outside_bundle(tmp_path, mutation):
    target = tmp_path / "tests/fixtures/meihua_calendar_v2"
    shutil.copytree(REFERENCES, target)
    scan = target / "sources/tam-1900.pdf"
    original = scan.read_bytes()
    shared = (
        tmp_path
        / "tests/data/shared_sources/data/ziwei_independent/calendar_1900_sources_v1/tam/sources/tam-1900.pdf"
    )
    shared.parent.mkdir(parents=True)
    shared.write_bytes(original)
    destination = shared
    if mutation in {"outside", "other_shared_scan", "redirected"}:
        other = (
            tmp_path / "outside.pdf"
            if mutation != "other_shared_scan"
            else shared.with_name("unregistered.pdf")
        )
        other.write_bytes(original)
        if mutation == "redirected":
            shared.unlink()
            shared.symlink_to(other)
        else:
            destination = other
    elif mutation in {"changed", "rehashed"}:
        shared.write_bytes(original + b"changed")
        if mutation == "rehashed":
            path = target / "sources.json"
            manifest = json.loads(path.read_text())
            next(
                r for r in manifest["artifacts"] if r["file"] == "sources/tam-1900.pdf"
            )["sha256"] = hashlib.sha256(shared.read_bytes()).hexdigest()
            path.write_text(json.dumps(manifest))
    scan.unlink()
    scan.symlink_to(destination)
    if mutation is None:
        _, rows = reference_bundle(target)
        assert len(rows) == 365
        assert rows[0]["date"] == date(1900, 1, 1)
        assert rows[-1]["date"] == date(1900, 12, 31)
    else:
        with pytest.raises(ValueError, match="escapes|Frozen artifact changed"):
            reference_bundle(target)


def test_audit_cannot_get_perfect_agreement_by_shrinking_supported_dates(monkeypatch):
    monkeypatch.setattr(
        "fatebridge.core.almanac.LUNAR_SUPPORTED_SOLAR_START", date(1900, 2, 1)
    )
    with pytest.raises(ValueError, match="do not shrink"):
        audit_tam_1900(REFERENCES)

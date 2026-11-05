"""Exercise real saved evidence and reject broken event/clock bindings."""

from __future__ import annotations

import copy
import json
import shutil

import pytest

from tests.support import ren_calendar_standard_reference as audit


def test_primary_reading_keeps_requirement_distinct_from_source_uncertainty():
    reading = audit.source_reading()
    assert reading["minute_table_physical_uncertainty_seconds"] is None
    assert reading["minute_rounding_algorithm_established"] is False
    assert reading["normative_requirement_is_not_measured_source_error"] is True
    assert reading["standard"]["full_12_page_standard_read"] is False


@pytest.mark.parametrize("rehash", [False, True])
def test_official_reading_rejects_changed_source_and_coordinated_rehash(
    tmp_path, rehash
):
    folder = tmp_path / "reading"
    shutil.copytree(audit.CORPUS, folder)
    target = folder / "reading.json"
    target.write_text(
        target.read_text().replace(
            '"minute_rounding_algorithm_established": false',
            '"minute_rounding_algorithm_established": true',
        )
    )
    if rehash:
        manifest = json.loads((folder / "freeze.json").read_text())
        manifest["files"]["reading.json"] = audit.sha(target)
        (folder / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit.source_reading(folder)

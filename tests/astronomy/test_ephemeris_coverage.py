"""Negative controls for the file-interval coverage gate."""

from scripts.astronomy.audit_ephemeris_coverage import interval_coverage


def row(start, end):
    return {"start_tt_jd": start, "end_tt_jd": end}


def test_empty_or_external_files_cannot_establish_coverage():
    assert interval_coverage([], 10, 20)["gaps"] == [[10, 20]]
    assert interval_coverage([row(0, 5), row(25, 30)], 10, 20)["covered"] is False


def test_an_internal_gap_is_reported_even_when_endpoints_have_files():
    result = interval_coverage([row(0, 14), row(16, 30)], 10, 20)
    assert result["covered"] is False
    assert result["gaps"] == [[14, 16]]


def test_overlapping_and_touching_files_cover_a_continuous_domain():
    assert interval_coverage([row(15, 30), row(0, 15)], 10, 20)["covered"] is True
    assert interval_coverage([row(14, 25), row(0, 16)], 10, 20)["covered"] is True


def test_a_partial_last_file_does_not_count_as_full_coverage():
    assert interval_coverage([row(0, 19)], 10, 20)["gaps"] == [[19, 20]]

"""Native solar terms against HKO's published 2026 major-term table.

Source: Hong Kong Observatory, 2026SolarTerms24.pdf, page 1:
https://www.hko.gov.hk/en/gts/astron2026/files/2026SolarTerms24.pdf
The twelve dates and Hong Kong times below were checked against that table.
Its minute publication supports the existing 60-second comparison only. This
does not supersede the separate historical Moshier one-second failures.

Keep the vectors here so clean-checkout CI does not need ignored local archives,
ephemeris files, a network request, or an expected value produced by FateBridge.
"""

from datetime import datetime

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.ephemeris_runtime import preserve_ephemeris_path
from fatebridge.core.moshier_solar import MODEL_ID, PROVIDER


@pytest.fixture(scope="module")
def moshier_terms(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch, preserve_ephemeris_path():
        patch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        patch.setenv("SE_EPHE_PATH", str(tmp_path_factory.mktemp("native-ephe")))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        terms = get_solar_terms_for_year(2026, "Asia/Hong_Kong")
        assert len(terms) == 24
        assert {term.ephemeris_model for term in terms} == {MODEL_ID}
        assert {term.resolution_provider for term in terms} == {PROVIDER}
        yield {term.name: term for term in terms}


@pytest.mark.parametrize(
    "name,published",
    [
        ("大寒", "2026-01-20T09:45:00+08:00"),
        ("雨水", "2026-02-18T23:52:00+08:00"),
        ("春分", "2026-03-20T22:46:00+08:00"),
        ("谷雨", "2026-04-20T09:39:00+08:00"),
        ("小满", "2026-05-21T08:37:00+08:00"),
        ("夏至", "2026-06-21T16:25:00+08:00"),
        ("大暑", "2026-07-23T03:13:00+08:00"),
        ("处暑", "2026-08-23T10:19:00+08:00"),
        ("秋分", "2026-09-23T08:05:00+08:00"),
        ("霜降", "2026-10-23T17:38:00+08:00"),
        ("小雪", "2026-11-22T15:23:00+08:00"),
        ("冬至", "2026-12-22T04:50:00+08:00"),
    ],
)
def test_native_terms_match_published_hko_minutes(moshier_terms, name, published):
    term = moshier_terms[name]
    expected = datetime.fromisoformat(published)
    assert term.moment.utcoffset() == expected.utcoffset()
    assert abs((term.moment - expected).total_seconds()) <= 60

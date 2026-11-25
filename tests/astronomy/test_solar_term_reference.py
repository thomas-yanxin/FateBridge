"""All packaged solar TT roots against a frozen independent implementation."""

import ast
import gzip
import hashlib
import json
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import almanac, de440_solar
from scripts.astronomy import solar_term_reference as source


@pytest.fixture(scope="module")
def reference():
    return source.load_solar_term_reference()


@pytest.fixture(scope="module")
def packaged_solar(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
        patch.setenv("SE_EPHE_PATH", str(tmp_path_factory.mktemp("solar-reference")))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        yield


_CI_YEARS = [
    1699,
    1700,
    1701,
    1799,
    1800,
    1899,
    1900,
    1972,
    2000,
    2026,
    2100,
    2200,
    2201,
    2300,
    2301,
]


def _assert_year_matches_both_tt_paths(year, reference):
    expected = reference.rows[(year - 1699) * 24 : (year - 1699 + 1) * 24]
    context = min(max(year, 1700), 2300)
    terms = (
        almanac.get_solar_terms_for_year(year, "UTC")
        if year == context
        else almanac._solar_terms_for_context_year(year, "UTC", context)
    )
    profile = (
        de440_solar.MODEL_ID if 1800 <= year <= 2200 else de440_solar.EXTENDED_MODEL_ID
    )
    assert len(terms) == len(expected) == 24
    for term, root in zip(terms, expected):
        assert term.name == root.name
        assert term.resolution_provider == "jpl_de440"
        assert term.ephemeris_model == profile
        details = term.solar_model_details
        assert details["source_kernel_sha256"] == reference.source.kernel_sha256
        assert details["reference_event_table_used"] is False
        assert details["numerical_resolution_is_physical_accuracy"] is False
        if year != context:
            assert details["adjacent_boundary_context_year"] == context
            assert details["solar_model_input_years"] == [1700, 2300]
        else:
            pass
        parts = details["selected_crossing_tt_parts"]
        delta = float(
            (
                sum((Fraction.from_float(part) for part in parts), Fraction(0))
                - Fraction.from_float(root.jd_tt)
            )
            * 86400
        )
        month = root.index // 2 + 1
        low = (
            date(year, month, 1 if root.index % 2 == 0 else 12).toordinal() + 1721424.5
        )
        high = (
            date(year, month, 12 if root.index % 2 == 0 else 28).toordinal() + 1721424.5
        )
        scalar = de440_solar.longitude_crossing_tt(
            float((root.index + 19) % 24 * 15), low, high, profile_id=profile
        )
        scalar_delta = (scalar["jd_tt"] - root.jd_tt) * 86400
        # Preserve the historical1s gate and the preregistered10ms diagnostic.
        assert abs(delta) <= 1.0 and abs(scalar_delta) <= 1.0, root
        assert abs(delta) <= 0.01 and abs(scalar_delta) <= 0.01, root


@pytest.mark.parametrize(
    "years",
    [tuple(_CI_YEARS[i::4]) for i in range(4)],
    ids=lambda ys: f"{ys[0]}..{ys[-1]}",
)
def test_packaged_boundary_and_strided_years_match_both_tt_paths(
    years, reference, packaged_solar
) -> None:
    for year in years:
        _assert_year_matches_both_tt_paths(year, reference)


@pytest.mark.parametrize("outside,context", [(1699, 1700), (2301, 2300)])
def test_reference_guards_keep_the_public_packaged_range(
    outside: int, context: int, packaged_solar
) -> None:
    almanac._solar_terms_for_context_year(outside, "UTC", context)
    with pytest.raises(ValueError, match="1700..2300"):
        almanac.get_solar_terms_for_year(outside, "UTC")


def test_reference_producer_is_preserved_without_candidate_imports(reference) -> None:
    tree = ast.parse(reference.source.producer_source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        else:
            pass
    assert {"numpy", "skyfield"} <= imports
    assert "fatebridge" not in imports
    assert reference.production_imports == ()


def test_reference_byte_edit_is_rejected(tmp_path: Path) -> None:
    data = bytearray(source.REFERENCE_PATH.read_bytes())
    data[-1] ^= 1
    target = tmp_path / "changed.json.gz"
    target.write_bytes(data)
    with pytest.raises(ValueError, match="identity changed"):
        source.load_solar_term_reference(target)


@pytest.mark.parametrize("change", ["producer", "prune", "order", "candidate_import"])
def test_coordinated_packet_checksum_edit_keeps_provenance_and_full_cohort_guards(
    change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet = json.loads(gzip.decompress(source.REFERENCE_PATH.read_bytes()))
    if change == "producer":
        packet["source"]["producer_source"] += "\n# altered producer\n"
    elif change == "prune":
        packet["rows"].pop()
    elif change == "order":
        packet["rows"][0], packet["rows"][1] = packet["rows"][1], packet["rows"][0]
    else:
        packet["production_imports"] = ["fatebridge"]
    packed = gzip.compress(
        json.dumps(packet, ensure_ascii=False).encode(), compresslevel=1, mtime=0
    )
    target = tmp_path / "coordinated.json.gz"
    target.write_bytes(packed)
    monkeypatch.setattr(source, "REFERENCE_SHA256", hashlib.sha256(packed).hexdigest())
    with pytest.raises(ValueError):
        source.load_solar_term_reference(target)

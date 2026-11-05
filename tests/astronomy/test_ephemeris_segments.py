"""Manual CE file-table examples and boundary-aware download selection.

Reference: Swiss Ephemeris general documentation 2.1.1. Planet and Moon
files cover 600-year blocks. No data files or network calls are used here.
"""

from pathlib import Path

import pytest

from fatebridge import fetch_ephe
from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from tests.fixtures.ephemeris_manifest import manifest_for_payloads


@pytest.fixture(autouse=True)
def synthetic_download_catalog(monkeypatch):
    names = set(ephemeris_files_for_years(range(1, 10000))) | set(
        fetch_ephe.DEFAULT_FILES
    )
    catalog = manifest_for_payloads({name: b"SW-test" for name in names})
    monkeypatch.setattr(
        fetch_ephe, "load_ephemeris_manifest", lambda path=None: catalog
    )


@pytest.mark.parametrize(
    "years,segments",
    [
        ([1], ["00"]),
        ([1500], ["12"]),
        ([2024], ["18"]),
        ([3001], ["30"]),
        ([9999], ["96"]),
        ([599], ["00", "06"]),
        ([600], ["00", "06"]),
        ([1799], ["12", "18"]),
        ([1800], ["12", "18"]),
        ([2399], ["18", "24"]),
        ([2400], ["18", "24"]),
        ([2024, 9999, 2024], ["18", "96"]),
    ],
)
def test_segments_follow_reference_file_table_with_adjacent_year_guard(years, segments):
    expected = tuple(
        name for code in segments for name in [f"sepl_{code}.se1", f"semo_{code}.se1"]
    )
    assert ephemeris_files_for_years(years) == expected


@pytest.mark.parametrize("years", [[], [0], [-1], [10000], [True], [2024.0], ["2024"]])
def test_invalid_year_plans_fail_before_downloading(years):
    with pytest.raises(ValueError):
        ephemeris_files_for_years(years)


@pytest.mark.parametrize(
    "flags,expected",
    [
        (["--years", "9999"], ("sepl_96.se1", "semo_96.se1")),
        (
            ["--year-range", "2399", "2401"],
            ("sepl_18.se1", "semo_18.se1", "sepl_24.se1", "semo_24.se1"),
        ),
        ([], fetch_ephe.DEFAULT_FILES),
    ],
)
def test_cli_downloads_the_actual_selected_segments(
    tmp_path, monkeypatch, flags, expected
):
    requested = []
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda url: requested.append(url) or b"SW-test"
    )
    assert fetch_ephe.main(["--dest", str(tmp_path), *flags]) == 0
    assert tuple(Path(url).name for url in requested) == expected
    assert {p.name for p in tmp_path.iterdir()} == set(expected)


def test_custom_directory_requires_explicit_runtime_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch_ephe, "_download", lambda url: b"SW-test")
    assert fetch_ephe.main(["--dest", str(tmp_path), "--years", "9999"]) == 0
    output = capsys.readouterr().out
    assert "Set SE_EPHE_PATH" in output
    assert "auto-discovers" not in output


@pytest.mark.parametrize(
    "flags",
    [
        ["--years", "0"],
        ["--year-range", "2400", "2399"],
        ["--year-range", "1", "10000"],
        ["--files", "x.se1", "--years", "2024"],
        ["--years", "2024", "--year-range", "2024", "2025"],
    ],
)
def test_invalid_cli_selection_never_downloads(monkeypatch, flags):
    def forbidden(*a, **kw):
        raise AssertionError("Invalid selection must not start a network request")

    monkeypatch.setattr(fetch_ephe, "_download", forbidden)
    with pytest.raises(SystemExit) as error:
        fetch_ephe.main(flags)
    assert error.value.code == 2

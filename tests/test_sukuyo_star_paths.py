"""Long native search paths must not silently discard the research catalogue."""

import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime, guolao
from fatebridge.core.fixed_star_paths import fixed_star_search_path
from fatebridge.services.divination import calculate_suzhan_analysis


@pytest.mark.parametrize("relative_to_data", [False, True])
def test_long_catalogue_plus_operator_path_keeps_coordinates_and_configuration(
    monkeypatch, tmp_path, relative_to_data
):
    # Each directory is a valid native input, but concatenating both exceeds
    # the actual AS_MAXCH-1-13 limit in Swiss 2.10's swe_set_ephe_path().
    # macOS's pytest root happens to be longer than Linux's. Construct each
    # input at a declared byte length so both platforms actually exceed the
    # combined native limit, while either input remains individually valid.
    tail_bytes = 220 - len(os.fsencode(str(tmp_path.resolve()))) - 1
    assert tail_bytes > 0, "Test root already exceeds the intended input length"
    catalogue = tmp_path / ("c" * tail_bytes)
    operator = tmp_path / ("e" * tail_bytes)
    catalogue.mkdir()
    operator.mkdir()
    for name in ["sefstars.txt", "sources.json"]:
        shutil.copy2(guolao.DATA / name, catalogue / name)
    assert len(os.fsencode(str(catalogue.resolve()))) <= 242
    assert len(os.fsencode(str(operator.resolve()))) <= 242
    assert (
        len(
            os.fsencode(str(catalogue.resolve()) + os.pathsep + str(operator.resolve()))
        )
        > 242
    )
    previous = ephemeris_runtime.configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(operator))
    try:
        ephemeris_runtime.configure_ephemeris_path(str(operator))
        baseline = calculate_suzhan_analysis(
            date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
        )
        assert "error" not in baseline, baseline
        monkeypatch.setattr(guolao, "DATA", catalogue)
        if relative_to_data:
            monkeypatch.chdir(tmp_path)
        cwd = Path.cwd()
        with fixed_star_search_path(catalogue, str(operator)) as search:
            assert len(os.fsencode(search)) <= 242
            assert [Path(p).resolve() for p in search.split(os.pathsep)] == [
                catalogue.resolve(),
                operator.resolve(),
            ]
        actual = calculate_suzhan_analysis(
            date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
        )
        assert "error" not in actual, actual
        assert actual["astronomy"] == baseline["astronomy"]
        assert actual["chart"] == baseline["chart"]
        assert Path.cwd() == cwd
        assert os.environ["SE_EPHE_PATH"] == str(operator)
        assert ephemeris_runtime.configured_ephemeris_path() == str(operator)
    finally:
        monkeypatch.delenv("SE_EPHE_PATH")
        ephemeris_runtime.configure_ephemeris_path(previous)


def test_unsupported_compact_directory_links_fail_explicitly(monkeypatch, tmp_path):
    long_catalogue = tmp_path / ("a" * 100)
    long_operator = tmp_path / ("b" * 100)

    def denied(*args, **kwargs):
        raise OSError("synthetic platform denies directory links")

    monkeypatch.setattr(Path, "symlink_to", denied)
    with pytest.raises(ValueError, match="Cannot create compact fixed-star paths"):
        with fixed_star_search_path(long_catalogue, str(long_operator)):
            pytest.fail("A silent native default would use a different catalogue")


@pytest.mark.parametrize("separator", [";", ":"])
@pytest.mark.skipif(os.name == "nt", reason="Colon is not a Windows directory name")
def test_literal_catalogue_separator_is_not_a_native_search_list(
    monkeypatch, tmp_path, separator
):
    catalogue = tmp_path / ("catalogue" + separator + "copy")
    catalogue.mkdir()
    for name in ["sefstars.txt", "sources.json"]:
        shutil.copy2(guolao.DATA / name, catalogue / name)
    baseline = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
    )
    assert "error" not in baseline, baseline
    monkeypatch.setattr(guolao, "DATA", catalogue)
    cwd = Path.cwd()
    configured = ephemeris_runtime.configured_ephemeris_path()
    environment = os.environ.get("SE_EPHE_PATH")
    actual = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
    )
    assert "error" not in actual, actual
    assert actual["chart"] == baseline["chart"]
    assert actual["astronomy"] == baseline["astronomy"]
    assert Path.cwd() == cwd
    assert ephemeris_runtime.configured_ephemeris_path() == configured
    assert os.environ.get("SE_EPHE_PATH") == environment


@pytest.mark.skipif(os.name == "nt", reason="POSIX separator-bearing directory")
def test_separator_in_temporary_root_never_escapes_to_native_code(
    monkeypatch, tmp_path
):
    from fatebridge.core import fixed_star_paths

    temporary = tmp_path / "temporary;root"
    temporary.mkdir()

    @contextmanager
    def use_temporary(**kwargs):
        yield str(temporary)

    monkeypatch.setattr(fixed_star_paths, "TemporaryDirectory", use_temporary)
    with pytest.raises(ValueError, match="native search separator"):
        with fixed_star_search_path(tmp_path / "catalogue;copy", ""):
            pytest.fail("An ambiguous native search path must never be used")

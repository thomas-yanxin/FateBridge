"""Unit tests for the Swiss Ephemeris data-file fetcher.

The download itself is always stubbed so the suite never touches the network.
"""

import pytest

from fatebridge import fetch_ephe


def _stub_download(monkeypatch, payload=b"SWdata"):
    monkeypatch.setattr(fetch_ephe, "_download", lambda url, timeout=60: payload)


def test_fetch_one_writes_validated_file(tmp_path, monkeypatch):
    _stub_download(monkeypatch, b"SWISSEPH-fake")

    out = fetch_ephe.fetch_one("sepl_18.se1", tmp_path)

    assert out == tmp_path / "sepl_18.se1"
    assert out.read_bytes() == b"SWISSEPH-fake"


def test_fetch_one_rejects_non_ephemeris_content(tmp_path, monkeypatch):
    _stub_download(monkeypatch, b"<!DOCTYPE html><html>nope</html>")

    with pytest.raises(ValueError):
        fetch_ephe.fetch_one("sepl_18.se1", tmp_path)

    # No partial/garbage file should be left behind on a failed validation.
    assert not (tmp_path / "sepl_18.se1").exists()


def test_fetch_one_skips_existing_file(tmp_path, monkeypatch):
    target = tmp_path / "semo_18.se1"
    target.write_bytes(b"SW-existing")
    calls = []
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda url, timeout=60: calls.append(url) or b"SW-new"
    )

    out = fetch_ephe.fetch_one("semo_18.se1", tmp_path)

    assert out.read_bytes() == b"SW-existing"
    assert calls == []


def test_fetch_one_force_redownloads(tmp_path, monkeypatch):
    target = tmp_path / "semo_18.se1"
    target.write_bytes(b"SW-existing")
    _stub_download(monkeypatch, b"SW-new")

    out = fetch_ephe.fetch_one("semo_18.se1", tmp_path, force=True)

    assert out.read_bytes() == b"SW-new"


def test_fetch_ephemeris_downloads_each_file(tmp_path, monkeypatch):
    _stub_download(monkeypatch)

    paths = fetch_ephe.fetch_ephemeris(tmp_path, ["a.se1", "b.se1"])

    assert [p.name for p in paths] == ["a.se1", "b.se1"]
    assert all(p.exists() for p in paths)


def test_default_dest_is_project_ephe_dir():
    assert fetch_ephe.default_dest().name == "ephe"


def test_main_reports_success(tmp_path, monkeypatch, capsys):
    _stub_download(monkeypatch)

    rc = fetch_ephe.main(["--dest", str(tmp_path), "--files", "x.se1"])

    assert rc == 0
    assert (tmp_path / "x.se1").exists()
    assert "Done." in capsys.readouterr().out


def test_main_returns_error_on_failure(tmp_path, monkeypatch):
    def boom(url, timeout=60):
        raise OSError("network down")

    monkeypatch.setattr(fetch_ephe, "_download", boom)

    rc = fetch_ephe.main(["--dest", str(tmp_path), "--files", "x.se1"])

    assert rc == 1


@pytest.mark.parametrize("existing", [False, True])
def test_failed_file_write_preserves_destination_and_removes_temporary_file(
    tmp_path, monkeypatch, existing
):
    target = tmp_path / "sepl_18.se1"
    if existing:
        target.write_bytes(b"SW-old-data")
    _stub_download(monkeypatch, b"SW-new-data")

    def interrupted(_):
        raise OSError("simulated disk interruption")

    monkeypatch.setattr(fetch_ephe.os, "fsync", interrupted)
    with pytest.raises(OSError, match="interruption"):
        fetch_ephe.fetch_one(target.name, tmp_path, force=True)
    assert target.read_bytes() == b"SW-old-data" if existing else not target.exists()
    assert set(tmp_path.iterdir()) == ({target} if existing else set())

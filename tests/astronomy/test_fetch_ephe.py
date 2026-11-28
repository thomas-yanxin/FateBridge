"""Verify offline Swiss Ephemeris acquisition and its CLI contract."""

from pathlib import Path

import pytest

from fatebridge import fetch_ephe
from tests.support.ephemeris_context import manifest_for_payloads


def _stub_manifest(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    manifest = manifest_for_payloads(
        {
            name: payload
            for name in ["sepl_18.se1", "semo_18.se1", "a.se1", "b.se1", "x.se1"]
        }
    )
    monkeypatch.setattr(
        fetch_ephe, "load_ephemeris_manifest", lambda path=None: manifest
    )


def _stub_download(monkeypatch: pytest.MonkeyPatch, payload: bytes = b"SWdata") -> None:
    _stub_manifest(monkeypatch, payload)
    monkeypatch.setattr(fetch_ephe, "_download", lambda url, timeout=60: payload)


def test_fetch_one_writes_validated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_download(monkeypatch, b"SWISSEPH-fake")

    out = fetch_ephe.fetch_one("sepl_18.se1", tmp_path)

    assert out == tmp_path / "sepl_18.se1"
    assert out.read_bytes() == b"SWISSEPH-fake"


def test_fetch_one_rejects_non_ephemeris_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_download(monkeypatch, b"<!DOCTYPE html><html>nope</html>")

    with pytest.raises(ValueError):
        fetch_ephe.fetch_one("sepl_18.se1", tmp_path)

    # No partial/garbage file should be left behind on a failed validation.
    assert not (tmp_path / "sepl_18.se1").exists()


def test_fetch_one_skips_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "semo_18.se1"
    target.write_bytes(b"SW-existing")
    _stub_manifest(monkeypatch, b"SW-existing")
    calls = []
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda url, timeout=60: calls.append(url) or b"SW-new"
    )

    out = fetch_ephe.fetch_one("semo_18.se1", tmp_path)

    assert out.read_bytes() == b"SW-existing"
    assert calls == []


def test_fetch_one_force_redownloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "semo_18.se1"
    target.write_bytes(b"SW-existing")
    _stub_download(monkeypatch, b"SW-new")

    out = fetch_ephe.fetch_one("semo_18.se1", tmp_path, force=True)

    assert out.read_bytes() == b"SW-new"


def test_fetch_ephemeris_downloads_each_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_download(monkeypatch)

    paths = fetch_ephe.fetch_ephemeris(tmp_path, ["a.se1", "b.se1"])

    assert [p.name for p in paths] == ["a.se1", "b.se1"]
    assert all(p.exists() for p in paths)


def test_default_dest_is_project_ephe_dir() -> None:
    assert fetch_ephe.default_dest().name == "ephe"


def test_main_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_download(monkeypatch)

    rc = fetch_ephe.main(["--dest", str(tmp_path), "--files", "x.se1"])

    assert rc == 0
    assert (tmp_path / "x.se1").exists()
    assert "Done." in capsys.readouterr().out


def test_main_returns_error_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_manifest(monkeypatch, b"SW-expected")

    def unavailable_download(url: str, timeout: int = 60) -> bytes:
        raise OSError("network down")

    monkeypatch.setattr(fetch_ephe, "_download", unavailable_download)

    rc = fetch_ephe.main(["--dest", str(tmp_path), "--files", "x.se1"])

    assert rc == 1
    assert "network down" in capsys.readouterr().err


@pytest.mark.parametrize("existing", [False, True])
def test_failed_file_write_preserves_destination_and_removes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    target = tmp_path / "sepl_18.se1"
    if existing:
        target.write_bytes(b"SW-old-data")
    else:
        pass
    _stub_download(monkeypatch, b"SW-new-data")

    def interrupted(descriptor: int) -> None:
        raise OSError("simulated disk interruption")

    monkeypatch.setattr(fetch_ephe.os, "fsync", interrupted)
    with pytest.raises(OSError, match="interruption"):
        fetch_ephe.fetch_one(target.name, tmp_path, force=True)
    assert target.read_bytes() == b"SW-old-data" if existing else not target.exists()
    assert set(tmp_path.iterdir()) == ({target} if existing else set())


@pytest.mark.parametrize("size, included", [(242, True), (243, False)])
def test_verify_only_guidance_respects_entire_swiss_path_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    size: int,
    included: bool,
) -> None:
    payload = b"SW-existing"
    _stub_manifest(monkeypatch, payload)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "archive"
    destination.mkdir()
    (destination / "sepl_18.se1").write_bytes(payload)
    monkeypatch.setenv("SE_EPHE_PATH", "a" * (size - len(";archive")) + ";archive")

    assert (
        fetch_ephe.main(
            ["--dest", "archive", "--files", "sepl_18.se1", "--verify-only"]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "checksum verified" in captured.out
    assert ("already includes this directory" in captured.out) is included
    assert ("exceeds the Swiss Ephemeris path limit" in captured.out) is not included
    assert captured.err == ""

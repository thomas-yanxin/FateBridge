"""Small real-layout fixtures test streaming integrity, never full accuracy."""

import hashlib
import io
import os
import ssl
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge import fetch_jpl as fetch
from fatebridge.core.jpl_ephemeris import jpl_header

FIXTURE = Path(__file__).parents[1] / "fixtures/human-design-de441-j2000.eph"


def kernel_fixture() -> tuple[fetch._KernelSpec, bytes]:
    raw = FIXTURE.read_bytes()
    header = jpl_header(FIXTURE)
    return (
        fetch._KernelSpec(
            "fixture.eph",
            "https://ssd.jpl.nasa.gov/fixture.eph",
            len(raw),
            hashlib.sha256(raw).hexdigest(),
            header["start_julian_day_tdb"],
            header["end_julian_day_tdb"],
        ),
        raw,
    )


class Response(io.BytesIO):
    def __init__(
        self, raw: bytes, status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(raw)
        self.status = status
        self.headers = (
            headers if headers is not None else {"Content-Length": str(len(raw))}
        )


def test_streamed_file_is_verified_and_a_valid_existing_file_needs_no_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected, raw = kernel_fixture()
    calls = []

    def open_request(request, **kwargs):
        assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["context"].check_hostname
        assert request.get_header("Accept-encoding") == "identity"
        calls.append(request.full_url)
        return Response(raw)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", open_request)
    progress, receipt = [], {}
    path = fetch._acquire(
        tmp_path,
        selected,
        progress=lambda n, total: progress.append((n, total)),
        receipt=receipt,
    )
    assert path.read_bytes() == raw and path.name == selected.filename
    assert progress[-1] == (len(raw), len(raw))
    assert receipt["file_content_verified"]
    assert not receipt["final_metadata"]["astronomical_accuracy_certified"]
    again = {}
    assert fetch._acquire(tmp_path, selected, receipt=again) == path
    assert calls == [selected.url] and again["network_request_performed"] is False


@pytest.mark.parametrize(
    "problem",
    ["checksum", "truncated", "oversized", "partial_response", "content_length"],
)
def test_bad_download_never_becomes_an_installed_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    selected, raw = kernel_fixture()
    body, status, headers = raw, 200, None
    if problem == "checksum":
        body = raw[:-1] + bytes([raw[-1] ^ 1])
    elif problem == "truncated":
        body = raw[:-1]
        headers = {}
    elif problem == "oversized":
        body = raw + b"x"
        headers = {}
    elif problem == "partial_response":
        status = 206
        headers = {"Content-Range": "bytes 0-40719/2788676624"}
    else:
        headers = {"Content-Length": "5"}
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen", lambda *a, **k: Response(body, status, headers)
    )
    with pytest.raises(ValueError):
        fetch._acquire(tmp_path, selected)
    assert not (tmp_path / selected.filename).exists()
    assert not list(tmp_path.glob(".de441-download-*"))


def test_existing_invalid_file_is_preserved_and_not_downloaded_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected, _ = kernel_fixture()
    target = tmp_path / selected.filename
    target.write_bytes(b"original invalid file")
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network called")
    )
    with pytest.raises(ValueError):
        fetch._acquire(tmp_path, selected)
    assert target.read_bytes() == b"original invalid file"


def test_concurrent_target_creation_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected, raw = kernel_fixture()
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: Response(raw))
    target = tmp_path / selected.filename

    def concurrent_change(received_bytes: int, total_bytes: int) -> None:
        assert received_bytes == total_bytes == len(raw)
        target.write_bytes(b"concurrent owner's file")

    with pytest.raises(ValueError):
        fetch._acquire(tmp_path, selected, progress=concurrent_change)
    assert target.read_bytes() == b"concurrent owner's file"


def test_tls_setup_failure_closes_and_removes_staging_file(tmp_path: Path) -> None:
    selected, _ = kernel_fixture()
    with pytest.raises(OSError):
        fetch._acquire(tmp_path, selected, ca_file=tmp_path / "missing-ca-file")
    assert not list(tmp_path.glob(".de441-download-*"))


@pytest.mark.parametrize("file_bytes, loadable", [(255, True), (256, False)])
def test_verify_only_cli_never_calls_the_acquirer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    file_bytes: int,
    loadable: bool,
) -> None:
    selected, raw = kernel_fixture()
    selected = replace(selected, filename=fetch.DE441.filename)
    monkeypatch.setattr(fetch, "DE441", selected)
    fixed_bytes = len(os.fsencode(tmp_path / "d" / selected.filename)) - 1
    destination = tmp_path / ("d" * (file_bytes - fixed_bytes))
    destination.mkdir()
    target = destination / selected.filename
    target.write_bytes(raw)
    monkeypatch.setattr(
        fetch, "fetch_de441", lambda *a, **k: pytest.fail("acquisition called")
    )

    assert fetch.main(["--verify-only", "--dest", str(destination)]) == 0
    output = capsys.readouterr().out
    assert f"Full content pin verified: {target}" in output
    assert ("Select explicitly with SE_EPHE_PATH=" in output) is loadable
    assert ("Copy the verified file" in output) is not loadable
    assert target.read_bytes() == raw


@pytest.mark.parametrize("prefix", ["", "生"])
@pytest.mark.parametrize("file_bytes, accepted", [(255, True), (256, False)])
def test_full_cli_acquisition_respects_native_file_path_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
    file_bytes: int,
    accepted: bool,
) -> None:
    selected, raw = kernel_fixture()
    selected = replace(selected, filename=fetch.DE441.filename)
    monkeypatch.setattr(fetch, "DE441", selected)
    fixed_bytes = len(os.fsencode(tmp_path / "d" / selected.filename)) - 1
    padding = file_bytes - fixed_bytes - len(os.fsencode(prefix))
    destination = tmp_path / (prefix + "d" * padding)
    target = destination / selected.filename
    assert len(os.fsencode(target)) == file_bytes
    calls = []

    def reply(request, **kwargs):
        calls.append(request.full_url)
        return Response(raw)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", reply)
    assert fetch.main(["--dest", str(destination)]) == (0 if accepted else 1)
    assert calls == ([selected.url] if accepted else [])
    if accepted:
        assert target.read_bytes() == raw
    else:
        assert not destination.exists()


@pytest.mark.parametrize(
    "delimiter",
    [
        pytest.param(";", id="semicolon"),
        pytest.param("\r", id="carriage-return"),
        pytest.param("\n", id="line-feed"),
        pytest.param(
            ":",
            id="colon",
            marks=pytest.mark.skipif(os.pathsep != ":", reason="Unix delimiter"),
        ),
    ],
)
def test_full_cli_rejects_nonliteral_swiss_install_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    delimiter: str,
) -> None:
    destination = tmp_path / f"left{delimiter}right"
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network called")
    )
    assert fetch.main(["--dest", str(destination)]) == 1
    assert "search-path delimiters" in capsys.readouterr().err
    assert not destination.exists()

"""Small real-layout fixtures test streaming integrity, never full accuracy."""

import hashlib
import io
import ssl
from pathlib import Path

import pytest

from fatebridge import fetch_jpl as fetch
from fatebridge.core.jpl_ephemeris import jpl_header

FIXTURE = (
    Path(__file__).parents[1]
    / "data/astrodice/reference_sets/study-lunar-split/diagnostic-kernels/case-02.eph"
)


def spec():
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
    def __init__(self, raw, status=200, headers=None):
        super().__init__(raw)
        self.status = status
        self.headers = (
            headers if headers is not None else {"Content-Length": str(len(raw))}
        )


def test_streamed_file_is_verified_and_a_valid_existing_file_needs_no_download(
    tmp_path, monkeypatch
):
    selected, raw = spec()
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
def test_bad_download_never_becomes_an_installed_kernel(tmp_path, monkeypatch, problem):
    selected, raw = spec()
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
    tmp_path, monkeypatch
):
    selected, _ = spec()
    target = tmp_path / selected.filename
    target.write_bytes(b"original invalid file")
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network called")
    )
    with pytest.raises(ValueError):
        fetch._acquire(tmp_path, selected)
    assert target.read_bytes() == b"original invalid file"


def test_concurrent_target_creation_is_not_overwritten(tmp_path, monkeypatch):
    selected, raw = spec()
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: Response(raw))
    target = tmp_path / selected.filename

    def concurrent_change(done, total):
        target.write_bytes(b"concurrent owner's file")

    with pytest.raises(ValueError):
        fetch._acquire(tmp_path, selected, progress=concurrent_change)
    assert target.read_bytes() == b"concurrent owner's file"


def test_tls_setup_failure_closes_and_removes_staging_file(tmp_path, monkeypatch):
    selected, _ = spec()
    with pytest.raises(OSError):
        fetch._acquire(tmp_path, selected, ca_file=tmp_path / "missing-ca-file")
    assert not list(tmp_path.glob(".de441-download-*"))


def test_verify_only_cli_never_calls_the_acquirer(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(fetch, "verify_de441", lambda path: seen.append(path) or {})
    monkeypatch.setattr(
        fetch, "fetch_de441", lambda *a, **k: pytest.fail("acquisition called")
    )
    assert fetch.main(["--verify-only", "--dest", str(tmp_path)]) == 0
    assert seen == [tmp_path / fetch.DE441.filename]

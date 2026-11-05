"""Complete-span source copying, strict range identity and corruption refusal."""

import json
import struct

import pytest

from fatebridge import fetch_jpl as prepare


def source_bytes():
    # These synthetic records test byte copying and coverage only; their numeric
    # contents never act as an astronomical expected value.
    head = bytearray(prepare.RECORD_BYTES)
    head[:84] = b"Synthetic DE441 byte-copy test; no physical reference".ljust(84, b" ")
    struct.pack_into("<d", head, 2668, 32.0)
    struct.pack_into("<2d", head, 2680, 149597870.7, 81.30056822149722)
    triples = (
        (3, 14, 4),
        (171, 10, 2),
        (231, 13, 2),
        (309, 11, 1),
        (342, 8, 1),
        (366, 7, 1),
        (387, 6, 1),
        (405, 6, 1),
        (423, 6, 1),
        (441, 13, 8),
        (753, 11, 2),
        (819, 10, 4),
    )
    struct.pack_into("<36i", head, 2696, *(value for row in triples for value in row))
    struct.pack_into("<i", head, 2840, 441)
    struct.pack_into("<3i", head, 2844, 899, 10, 4)
    constants = bytes(prepare.RECORD_BYTES)
    seed_record = struct.pack("<1018d", *(i / 1024 for i in range(1018)))
    begin = prepare.january_first(3000) - 64
    count = 32
    struct.pack_into("<2d", head, 2652, begin, begin + count * 32)
    records = []
    for i in range(count):
        record = bytearray(seed_record)
        struct.pack_into("<2d", record, 0, begin + i * 32, begin + (i + 1) * 32)
        records.append(record)
    return bytes(head) + constants + b"".join(records)


def test_preparation_copies_every_original_record_and_retains_guards(
    monkeypatch, tmp_path
):
    original = source_bytes()
    calls = []

    def ranges(start, size, etag=None):
        assert etag in {None, '"source-object"'}
        calls.append((start, size))
        return original[start : start + size], {
            "ETag": '"source-object"',
            "Content-Range": f"bytes {start}-{start + size - 1}/{len(original)}",
        }

    monkeypatch.setattr(prepare, "source_range", ranges)
    output = tmp_path / "complete.eph"
    manifest = prepare.prepare(output, 3000, 3001)
    assert manifest["status"] == "ready"
    assert manifest["runtime_default_changed"] is False
    assert manifest["full_remote_file_sha256_verified"] is False
    assert manifest["start_julian_day_tdb"] <= prepare.january_first(3000) - 32
    assert manifest["end_julian_day_tdb"] >= prepare.january_first(3001) + 32
    copied = output.read_bytes()
    first = manifest["original_first_record"]
    stop = first + manifest["record_count"]
    assert (
        copied[prepare.RECORD_BYTES : 2 * prepare.RECORD_BYTES]
        == original[prepare.RECORD_BYTES : 2 * prepare.RECORD_BYTES]
    )
    assert (
        copied[2 * prepare.RECORD_BYTES :]
        == original[
            (first + 2) * prepare.RECORD_BYTES : (stop + 2) * prepare.RECORD_BYTES
        ]
    )
    assert all(
        a == b or i < 252 or 2652 <= i < 2668
        for i, (a, b) in enumerate(
            zip(original[: prepare.RECORD_BYTES], copied[: prepare.RECORD_BYTES])
        )
    )
    assert prepare.verify(output) == manifest
    assert len(calls) == 2
    with pytest.raises(ValueError, match="already exists"):
        prepare.prepare(output, 3000, 3001)
    # Full-source verification must reject a changed numeric word.
    data = bytearray(copied)
    data[2 * prepare.RECORD_BYTES + 24] ^= 1
    output.write_bytes(data)
    with pytest.raises(ValueError, match="bytes or extent changed"):
        prepare.verify(output)


def test_failed_download_preserves_manifest_without_installing_source(
    monkeypatch, tmp_path
):
    original = source_bytes()

    def failing(start, size, etag=None):
        if start:
            raise OSError("interrupted original source transfer")
        return original[:size], {
            "ETag": '"source-object"',
            "Content-Range": f"bytes 0-{size - 1}/{len(original)}",
        }

    monkeypatch.setattr(prepare, "source_range", failing)
    output = tmp_path / "incomplete.eph"
    with pytest.raises(OSError, match="interrupted"):
        prepare.prepare(output, 3000, 3001)
    manifest = json.loads(output.with_suffix(".eph.manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["downloaded_coefficient_bytes"] == 0
    assert manifest["error_type"] == "OSError"
    assert not output.exists()


@pytest.mark.parametrize("fault", ["status", "range", "etag", "short"])
def test_original_http_range_cannot_silently_become_another_object(monkeypatch, fault):
    class Response:
        status = 206
        headers = {"Content-Range": "bytes 0-15/100", "ETag": '"source"'}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            return b"x" * (15 if fault == "short" else 16)

    response = Response()
    response.headers = dict(response.headers)
    if fault == "status":
        response.status = 200
    elif fault == "range":
        response.headers["Content-Range"] = "bytes 16-31/100"
    elif fault == "etag":
        response.headers["ETag"] = '"different"'
    monkeypatch.setattr(
        prepare.urllib.request, "urlopen", lambda *args, **kwargs: response
    )
    with pytest.raises(ValueError, match="byte range or source identity changed"):
        prepare.source_range(0, 16, '"source"')


@pytest.mark.parametrize(
    "arguments",
    [
        ["--start-year", "3000", "--end-year", "3600"],
        ["--output", "source.eph"],
        ["--output", "source.eph", "--start-year", "3000"],
        ["--output", "source.eph", "--dest", "other-directory"],
        ["--output", "source.eph", "--ca-file", "other-ca.pem"],
        ["--output", "source.eph", "--verify-only", "--start-year", "3000"],
    ],
)
def test_full_file_and_span_cli_parameters_are_explicitly_separated(
    monkeypatch, arguments
):
    monkeypatch.setattr(
        prepare.urllib.request,
        "urlopen",
        lambda *a, **kw: pytest.fail("Invalid arguments must not start a transfer"),
    )
    with pytest.raises(SystemExit) as error:
        prepare.main(arguments)
    assert error.value.code == 2

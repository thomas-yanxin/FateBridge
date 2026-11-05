"""Independent reference acquisition rejects bad bytes before replacing files."""

import hashlib
import json

import pytest

from scripts.astronomy import prepare_reference_kernel


@pytest.fixture
def kernel_root(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_reference_kernel, "ROOT", tmp_path)
    metadata = tmp_path / "src/fatebridge/data/astronomy/de440-solar-v1.json"
    metadata.parent.mkdir(parents=True)
    content = b"pinned independent kernel"
    metadata.write_text(
        json.dumps(
            {
                "source": {
                    "url": "https://example.invalid/reference.bsp",
                    "kernel_sha256": hashlib.sha256(content).hexdigest(),
                }
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "ephe/solar-de440.bsp"
    target.parent.mkdir()
    return target, content


def test_verified_cached_reference_needs_no_network(kernel_root, monkeypatch):
    target, content = kernel_root
    target.write_bytes(content)

    def unexpected_download(*args):
        pytest.fail("A verified reference must remain usable offline")

    monkeypatch.setattr(
        prepare_reference_kernel.urllib.request, "urlretrieve", unexpected_download
    )
    assert prepare_reference_kernel.main(["--verify-only"]) == 0
    assert prepare_reference_kernel.main([]) == 0
    assert target.read_bytes() == content


@pytest.mark.parametrize("existing", [None, b"corrupt reference"])
def test_verification_rejects_missing_or_corrupt_reference(kernel_root, existing):
    target, _ = kernel_root
    if existing is not None:
        target.write_bytes(existing)
    with pytest.raises(ValueError, match="missing or corrupt"):
        prepare_reference_kernel.main(["--verify-only"])


def test_bad_download_preserves_existing_reference_then_valid_download_replaces_it(
    kernel_root, monkeypatch
):
    target, content = kernel_root
    previous = b"existing unqualified reference"
    target.write_bytes(previous)

    def download_bad_bytes(url, destination):
        destination.write_bytes(b"unqualified response")

    monkeypatch.setattr(
        prepare_reference_kernel.urllib.request, "urlretrieve", download_bad_bytes
    )
    with pytest.raises(ValueError, match="do not match"):
        prepare_reference_kernel.main([])
    assert target.read_bytes() == previous
    assert list(target.parent.iterdir()) == [target]

    def download_good_bytes(url, destination):
        destination.write_bytes(content)

    monkeypatch.setattr(
        prepare_reference_kernel.urllib.request, "urlretrieve", download_good_bytes
    )
    assert prepare_reference_kernel.main([]) == 0
    assert target.read_bytes() == content
    assert list(target.parent.iterdir()) == [target]

"""Prospective records become visible only after a complete, exclusive write."""

import errno
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def load_cli():
    path = Path(__file__).resolve().parents[2] / "scripts/sukuyo/sukuyo_blind_study.py"
    spec = importlib.util.spec_from_file_location("sukuyo_atomic_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("failure", ["write", "close", "fsync", "link"])
def test_failed_publication_leaves_no_final_file_and_allows_retry(
    tmp_path, monkeypatch, failure
):
    cli = load_cli()
    output = tmp_path / "registration.json"
    raw = b'{"complete": true}\n'
    original_temporary = cli.tempfile.NamedTemporaryFile
    original_sync, original_link = cli.os.fsync, cli.os.link

    class FaultyFile:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            self.stream.__exit__(*args)
            if failure == "close":
                raise OSError(errno.ENOSPC, "injected close failure")

        def write(self, data):
            if failure == "write":
                self.stream.write(data[:7])
                raise OSError(errno.ENOSPC, "injected partial write")
            return self.stream.write(data)

    def temporary(*args, **kwargs):
        return FaultyFile(original_temporary(*args, **kwargs))

    def sync(fd):
        if failure == "fsync":
            raise OSError(errno.ENOSPC, "injected fsync failure")
        return original_sync(fd)

    def link(source, target):
        if failure == "link":
            raise OSError(errno.EIO, "injected publication failure")
        return original_link(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(cli.tempfile, "NamedTemporaryFile", temporary)
        patch.setattr(cli.os, "fsync", sync)
        patch.setattr(cli.os, "link", link)
        with pytest.raises(OSError):
            cli._publish_output(output, raw)
        assert not output.exists()
        assert list(tmp_path.iterdir()) == []
    cli._publish_output(output, raw)
    assert output.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("kind", ["file", "dangling_symlink"])
def test_existing_commitment_or_symlink_is_never_replaced(tmp_path, kind):
    cli = load_cli()
    output = tmp_path / "sealed.json"
    if kind == "file":
        output.write_bytes(b"existing commitment")
    else:
        output.symlink_to("absent-target")
    with pytest.raises(FileExistsError):
        cli._publish_output(output, b"replacement")
    if kind == "file":
        assert output.read_bytes() == b"existing commitment"
    else:
        assert output.is_symlink() and output.readlink() == Path("absent-target")
        assert not (tmp_path / "absent-target").exists()
    assert list(tmp_path.iterdir()) == [output]


def test_concurrent_writers_have_one_complete_winner(tmp_path):
    cli = load_cli()
    output = tmp_path / "registration.json"
    payloads = [b"first complete\n", b"second complete\n"]

    def publish(raw):
        try:
            cli._publish_output(output, raw)
        except FileExistsError:
            return "existing"
        return "published"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, payloads))
    assert sorted(outcomes) == ["existing", "published"]
    assert output.read_bytes() == payloads[outcomes.index("published")]
    assert list(tmp_path.iterdir()) == [output]


def test_actual_draft_cli_preserves_json_and_refuses_a_second_write(tmp_path):
    cli = Path(__file__).resolve().parents[2] / "scripts/sukuyo/sukuyo_blind_study.py"
    output = tmp_path / "draft.json"
    command = [sys.executable, str(cli), "draft", "--output", str(output)]
    first = subprocess.run(command, capture_output=True)
    assert first.returncode == 0, first.stderr
    raw = output.read_bytes()
    data = json.loads(raw)
    assert data["status"] == "draft_not_registered"
    assert data["real_world_sample_count"] == 0 and not data["authority_certified"]
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [output]

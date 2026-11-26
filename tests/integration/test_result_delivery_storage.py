"""Single-file result delivery, exact JSON pages and shared retention."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.private_files import open_private_file
from tests.support.result_delivery import block_writes, reconstruct

if sys.platform == "win32":
    import pywintypes

    from fatebridge.utils import private_files_windows
else:
    pass


def test_private_files_loads_only_the_host_backend() -> None:
    """Import in a fresh process so test doubles cannot mask a platform dependency."""
    selected, excluded = (
        ("win32security", "fcntl")
        if sys.platform == "win32"
        else ("fcntl", "win32security")
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fatebridge.utils.private_files; "
            "assert sys.argv[1] in sys.modules and sys.argv[2] not in sys.modules",
            selected,
            excluded,
        ],
        check=True,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows token APIs")
@pytest.mark.parametrize("should_fail", [False, True])
def test_windows_user_lookup_closes_the_token(
    monkeypatch: pytest.MonkeyPatch, should_fail: bool
) -> None:
    """A token returned by Win32 is closed even when querying its owner fails."""
    closed: list[bool] = []
    token = SimpleNamespace(Close=lambda: closed.append(True))
    api = private_files_windows.win32security
    expected_sid = private_files_windows.windows_user()

    def read_token(
        handle: SimpleNamespace, token_information_class: int
    ) -> tuple[pywintypes.SIDType, int]:
        assert handle is token and token_information_class == api.TokenUser
        if should_fail:
            raise OSError("token query failed")
        else:
            return (expected_sid, 0)

    monkeypatch.setattr(api, "OpenProcessToken", lambda process, access: token)
    monkeypatch.setattr(api, "GetTokenInformation", read_token)
    if should_fail:
        with pytest.raises(OSError, match="token query failed"):
            private_files_windows.windows_user()
    else:
        assert private_files_windows.windows_user() == expected_sid
    assert closed == [True]


def test_private_json_and_unicode_pages_preserve_the_same_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = delivery.ResultStore(tmp_path / "results")
    original = {
        "earlier": {"大量文字": '祖孙故事👩🏽‍💻\\"\n' * 300},
        "run_metadata": {"run_id": "fixed", "tool_name": "probe"},
        "中文": [{"text": "🌳上海\t\n" * 1200}, None, True, 1.5],
    }
    ref = store.put(original)
    result_id = ref["result_id"]
    artifact = Path(ref["file_path"])
    assert set(store.directory.iterdir()) == {artifact, store.directory / ".lock"}
    os.close(open_private_file(artifact, os.O_RDONLY))
    assert json.loads(artifact.read_text(encoding="utf-8"))["payload"] == original
    with monkeypatch.context() as blocked:
        block_writes(blocked)
        assert store.manifest(result_id)["run_metadata"] == original["run_metadata"]
        assert reconstruct(store, result_id) == original
        for path, value in [
            ("中文.0.text", original["中文"][0]["text"]),
            ("中文.1", None),
            ("中文.2", True),
            ("中文.3", 1.5),
            ("earlier", original["earlier"]),
        ]:
            assert reconstruct(store, result_id, path) == value
        text = format_json_response(original)
        for offset in (1, 2047, 2048, 2049, len(text)):
            assert (
                store.page(result_id, offset)["text"]
                == text[offset : offset + delivery.PAGE_CHARS]
            )
        with pytest.raises(ValueError, match="未在当前 MCP 配置中公开"):
            store.page(result_id, allowed_tools={"hidden"})
    assert set(store.directory.iterdir()) == {artifact, store.directory / ".lock"}


def test_next_write_reclaims_expired_results_and_crashed_staging_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = delivery.ResultStore(tmp_path / "results")
    ref = store.put({"text": "中文" * 5000})
    artifact = Path(ref["file_path"])
    pending = store.directory / ("f" * 48 + ".pending")
    pending.write_bytes(b"interrupted write")
    monkeypatch.setattr(delivery.time, "time", lambda: ref["expires_at"] + 1)
    with pytest.raises(ParameterError, match="过期"):
        store.page(ref["result_id"])
    assert artifact.exists()
    store.put({"text": "current"})
    assert not artifact.exists()
    assert not pending.exists()


def test_oversize_attempt_preserves_existing_deliverables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = delivery.ResultStore(tmp_path / "results")
    ref = store.put({"text": "keep this run"})
    monkeypatch.setattr(delivery, "MAX_STORED_BYTES", 4096)
    with pytest.raises(ParameterError, match="容量"):
        store.put({"text": "x" * 5000})
    assert store.get(ref["result_id"]) == {"text": "keep this run"}

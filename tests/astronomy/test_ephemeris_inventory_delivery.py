"""Runtime ephemeris inventories remain consistent across transports."""

from pathlib import Path

import pytest

from fatebridge.services import replay_metadata
from tests.support.transports import SPECS, inputs, rest, surface_calls

PATH = "run_metadata.runtime"


def test_semicolon_directory_inventory_is_equal_across_transports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, surface_calls
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        # Small auxiliary file, tracked by provenance but unused in this chart.
        (directory / "seasnam.txt").write_text(name)
    monkeypatch.setenv("SE_EPHE_PATH", "first;second")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    expected = replay_metadata.ephemeris_inventory()
    assert set(expected["files"]) == {"0/seasnam.txt", "1/seasnam.txt"}
    spec = SPECS["bazi_career"]
    payload = inputs(spec)
    options = dict(fields=[PATH], detail="audit")
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=options,
        options=options,
        flags=["--fields", PATH, "--detail", "audit"],
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in (response.json(), protocol.structured_content, cli):
        assert output["run_metadata"]["runtime"]["ephemeris"] == expected

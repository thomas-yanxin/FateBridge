"""Clause role, graph alternatives, immutable old outputs and adapter rejection."""

import gzip
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.core.human_design import human_design_knowledge as base
from fatebridge.core.human_design import human_design_knowledge_v4 as hd
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three

ROOT = Path(__file__).resolve().parents[2]
rest = shared_rest


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def test_all_384_v4_rows_preserve_v3_meanings_and_honest_coverage() -> None:
    registry = base.build_registry()["domains"][0]["categories"]
    assert registry[2]["coverage"] == registry[1]["coverage"]
    assert registry[2]["coverage"]["local_editorial_paraphrases"] == 18
    assert registry[2]["coverage"]["independently_accepted_line_meanings"] == 0
    selected = []
    for gate in range(1, 65):
        for line in range(1, 7):
            key = f"{gate}.{line}"
            record = hd.read_reference(key=key)["reference_details"]["record"]
            parent = base.read_reference(category="lines_v3", key=key)[
                "reference_details"
            ]["record"]
            extra = record.pop("source_context_annotations")
            assert record == parent
            if extra:
                selected.append(key)
                assert len(extra) == 1
                assert extra[0]["personal_condition_satisfied"] is None
                assert extra[0]["source_interpretation_resolved"] is False
            else:
                pass
    assert selected == ["2.3", "6.3", "7.2", "12.6", "42.1"]


@pytest.mark.parametrize("key", ["2.3", "6.3", "7.2", "12.6", "42.1", "3.4", "64.6"])
def test_actual_reference_content_on_three_adapters(
    key: str, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v4", "key": key},
        ["category", "key", "reference_details", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert cli["provenance"]["source_catalogue_version"] == 4
    assert cli["reference_details"]["record"]["actual_fixing_state"] is None


@pytest.mark.parametrize("fault", ["version"])
def test_adapters_reject_forged_annotations_even_if_projecting_unrelated_field(
    fault: str,
    monkeypatch: pytest.MonkeyPatch,
    rest,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    key = "42.1"
    result = calculate_knowledge_read(
        domain="human_design", category="lines_v4", key=key
    )
    if fault == "version":
        result["category"] = "lines_v3"
    else:
        pass
    execute = execution.execute_spec

    def forged(spec, request):
        if spec.key == "knowledge_read":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(result), (), {}))
        else:
            pass
        return execute(spec, request)

    monkeypatch.setattr(execution, "execute_spec", forged)
    response, code, _, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v4", "key": key},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code != 0 and mcp.is_error


@pytest.mark.parametrize("mode", ["read", "registry"])
def test_context_bytes_changed_after_load_are_detected_next_call(
    mode: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / hd.CATALOGUE_PATH.name
    path.write_bytes(hd.CATALOGUE_PATH.read_bytes())
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    method = "_catalogue" if mode == "read" else "_registry_category"
    original = getattr(hd, method)

    def changed(*args):
        result = original(*args)
        path.write_bytes(path.read_bytes() + b"{")
        return result

    monkeypatch.setattr(hd, method, changed)
    assert hd.read_reference(key="7.2") if mode == "read" else base.build_registry()
    with pytest.raises(EphemerisSourceError) as caught:
        (hd.read_reference(key="7.2") if mode == "read" else base.build_registry())
    assert caught.value.reason == "human_design_reference_invalid"


def test_source_replaced_before_lookup_is_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / hd.CATALOGUE_PATH.name
    path.write_bytes(hd.CATALOGUE_PATH.read_bytes() + b"{")
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    with pytest.raises(EphemerisSourceError) as caught:
        hd.read_reference(key="7.2")
    assert caught.value.reason == "human_design_reference_invalid"

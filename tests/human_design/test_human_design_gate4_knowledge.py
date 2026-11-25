"""Gate4 source drafts, immutable older versions and actual adapter binding."""

import hashlib
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

import fatebridge.application.execution as execution
from fatebridge.core.human_design import human_design_knowledge as base
from fatebridge.core.human_design import human_design_knowledge_v5 as hd
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three
from validation.human_design_context_lines import (
    verify_human_design_context_packet,
)
from validation.human_design_context_packet import (
    build_human_design_context_packet,
)
from validation.human_design_line_packet_cli import read

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tests/data/human_design/gate4"
E = BASE
rest = shared_rest


@pytest.fixture(scope="module")
def sources():
    from tests.support.human_design_current import semantic_sources

    return semantic_sources("gate4")


@pytest.fixture(scope="module")
def packets(sources):
    return {
        key: build_human_design_context_packet(source, reference_category="lines_v5")
        for key, source in sources.items()
    }


@pytest.mark.parametrize(
    "line,heading,up,down",
    [
        (1, "Pleasure", "Moon", "Earth"),
        (2, "Acceptance", "Moon", "Mars"),
        (3, "Irresponsibility", "Venus", "Pluto"),
        (4, "The liar", "Sun", "Saturn"),
        (5, "Seduction", "Jupiter", "Pluto"),
        (6, "Excess", "Mercury", "Mars"),
    ],
)
def test_every_specific_gate4_line_has_source_bound_unassessed_qualifier(
    line: int, heading: str, up: str, down: str
) -> None:
    path = E / "gate4-independent-source-locators.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "142450d0504ba8ec747e45e153289e7a58450c612a53ed24d5b9ca238d752995"
    )
    fact = read(path)["rows"][line - 1]
    record = hd.read_reference(key=f"4.{line}")["reference_details"]["record"]
    assert record["source_line_heading"] == heading == fact["source_line_heading"]
    assert record["source_layout_block_sha256"] == fact["source_layout_block_sha256"]
    assert (
        record["source_pdf_page_one_based"] == fact["source_pdf_page_one_based"] == 13
    )
    assert record["source_polarity_planets"] == {
        "exaltation": [up],
        "detriment": [down],
    }
    assert up == fact["visually_observed_exaltation_planet"]
    assert down == fact["visually_observed_detriment_planet"]
    (qualifier,) = record["source_qualifiers"]
    assert qualifier["source_role"] == "introductory_qualifier"
    assert (
        qualifier["mechanical_predicate"]
        is qualifier["personal_condition_satisfied"]
        is None
    )
    assert qualifier["automatic_application"] is False
    assert qualifier["editorial_summary_zh"] in record["source_reading_notes"][0]
    assert record["source_conditions"] is record["source_context_annotations"] is None
    assert record["complete_line_meaning_accepted"] is False
    assert record["actual_fixing_state"] is record["selected_polarity"] is None
    assert "不等同事实" in record["source_reading_notes"][1]
    if line == 1:
        assert any("不是已计算的事件日期" in n for n in record["source_reading_notes"])
    else:
        pass
    if line == 3:
        assert any("then" in n for n in record["source_reading_notes"])
    else:
        pass
    if line == 4:
        assert any(
            "不用于判断当事人是否撒谎" in n for n in record["source_reading_notes"]
        )
    else:
        pass


def test_all384_rows_preserve_old_meanings_and_existing_context_annotations() -> None:
    for g in range(1, 65):
        for line in range(1, 7):
            key = f"{g}.{line}"
            old = base.read_reference(category="lines_v4", key=key)[
                "reference_details"
            ]["record"]
            new = hd.read_reference(key=key)["reference_details"]["record"]
            if g != 4:
                assert new == old
            else:
                pass
            assert (
                new["source_context_annotations"] == old["source_context_annotations"]
            )
            assert new["complete_line_meaning_accepted"] is False


@pytest.mark.parametrize(
    "key", ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "2.3", "64.6"]
)
def test_real_rest_mcp_cli_content_is_identical(
    key: str, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v5", "key": key},
        ["category", "key", "reference_details", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert cli["provenance"]["source_catalogue_version"] == 5
    assert (
        cli["reference_details"]["record"]["personal_applicability_assessed"] is False
    )


@pytest.mark.parametrize(
    "fault",
    [
        "claimed_acceptance",
        "personal_true",
        "wrong_version",
        "drop_qualifier",
        "made_up_date",
    ],
)
def test_forged_reference_differs_from_source_or_fails_runtime_identity_check(
    fault: str,
    monkeypatch: pytest.MonkeyPatch,
    rest,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    value = calculate_knowledge_read(
        domain="human_design", category="lines_v5", key="4.1"
    )
    record = value["reference_details"]["record"]
    if fault == "claimed_acceptance":
        record["complete_line_meaning_accepted"] = True
    else:
        pass
    if fault == "personal_true":
        record["source_qualifiers"][0]["personal_condition_satisfied"] = True
    else:
        pass
    if fault == "wrong_version":
        value["category"] = "lines_v4"
    else:
        pass
    if fault == "drop_qualifier":
        record["source_qualifiers"] = []
    else:
        pass
    if fault == "made_up_date":
        record["editorial_paraphrase"][
            "exaltation"
        ] = "Tomorrow is the guaranteed right time."
    else:
        pass
    expected = base.read_reference(category="lines_v5", key="4.1")
    assert any(value[field] != fact for field, fact in expected.items())
    if fault != "wrong_version":
        return
    else:
        pass
    execute = execution.execute_spec

    def forged(spec, request, **kwargs):
        if spec.key == "knowledge_read":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(value), (), {}))
        else:
            pass
        return execute(spec, request, **kwargs)

    monkeypatch.setattr(execution, "execute_spec", forged)
    response, code, _, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "human_design", "category": "lines_v5", "key": "4.1"},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code != 0 and mcp.is_error


@pytest.mark.parametrize("mode", ["read", "registry"])
def test_source_changed_after_load_is_detected_on_next_call(
    mode: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / hd.CATALOGUE_PATH.name
    path.write_bytes(hd.CATALOGUE_PATH.read_bytes())
    monkeypatch.setattr(hd, "CATALOGUE_PATH", path)
    method = "_catalogue" if mode == "read" else "_registry_category"
    original = getattr(hd, method)

    def changed(*args):
        result = original(*args)
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(hd, method, changed)
    assert hd.read_reference(key="4.1") if mode == "read" else base.build_registry()
    with pytest.raises(EphemerisSourceError) as caught:
        hd.read_reference(key="4.1") if mode == "read" else base.build_registry()
    assert caught.value.reason == "human_design_reference_invalid"


def test_every_declared_packet_replays_without_native_and_uses_its_own_chart(
    sources, packets
) -> None:
    seen, total = set(), 0
    with (
        patch(
            "fatebridge.core.astro.runtime.ephemeris_call",
            side_effect=AssertionError("native replay"),
        ),
        patch(
            "fatebridge.core.astro.native_execution.calculate",
            side_effect=AssertionError("native dispatch"),
        ),
    ):
        for key, source in sources.items():
            packet = packets[key]
            assert (
                verify_human_design_context_packet(
                    packet, source, reference_category="lines_v5"
                )["status"]
                == "verified_original_bound_context_line_packet"
            )
            for context in packet["contexts"]:
                rows = packet["line_reading_groups"][context["line_reading_group_id"]][
                    "rows"
                ]
                assert len(rows) == 26
                total += len(rows)
                for row in rows:
                    _, side, index = row["activation_path"].split(".")
                    actual = context["chart"]["activations"][side][int(index)]
                    assert (row["body"], row["gate"], row["line"]) == (
                        actual["body"],
                        actual["gate"],
                        actual["line"],
                    )
                    if row["gate"] == 4:
                        seen.add(row["reference_key"])
                        assert (
                            row["source_qualifiers"][0]["personal_condition_satisfied"]
                            is None
                        )
                        assert row["editorial_paraphrase"] is not None
                        assert "引导语局部转述" in row["reading"]
                    else:
                        pass
            assert (
                packet["complete384_line_semantics_accepted"]
                is packet["arbitrary_model_free_text_accepted"]
                is packet["real_world_prediction_validated"]
                is False
            )
    assert seen == {f"4.{i}" for i in range(1, 7)} and total > 26 * 15


@pytest.mark.parametrize(
    "fault", ["date", "fixing", "path", "omission", "personal", "context", "source"]
)
def test_external_original_binding_rejects_packet_substitution(
    fault: str, sources, packets
) -> None:
    key = next(
        key
        for key, source in sources.items()
        if any(
            row["gate"] == 4 for rows in source["activations"].values() for row in rows
        )
    )
    source = sources[key]
    value = deepcopy(packets[key])
    group = next(
        g
        for g in value["line_reading_groups"].values()
        if any(r["gate"] == 4 for r in g["rows"])
    )
    row = next(r for r in group["rows"] if r["gate"] == 4)
    if fault == "date":
        row["reading"] += "Tomorrow is guaranteed."
    else:
        pass
    if fault == "fixing":
        row["actual_fixing_state"] = "invented"
    else:
        pass
    if fault == "path":
        row["activation_path"] = "activations.personality.99"
    else:
        pass
    if fault == "omission":
        group["rows"].remove(row)
    else:
        pass
    if fault == "personal":
        row["source_qualifiers"][0]["personal_condition_satisfied"] = True
    else:
        pass
    if fault == "context":
        value["contexts"].pop()
    else:
        pass
    if fault == "source":
        value["nominal_packet_v1"]["original_result"][
            "birth_utc"
        ] = "2000-08-18T12:00:00+00:00"
    else:
        pass
    assert (
        verify_human_design_context_packet(
            value, source, reference_category="lines_v5"
        )["status"]
        == "rejected"
    )

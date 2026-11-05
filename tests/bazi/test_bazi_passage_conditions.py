"""Contradictory passage receipts fail; valid and partial source facts survive."""

import asyncio
import gzip
import json
from copy import deepcopy
from dataclasses import replace
from itertools import combinations, product
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.output_classical_passage import (
    ClassicalPassage,
    PassageNode,
    PassagePath,
)
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, GENERATION_CYCLE, STEM_ELEMENTS
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[2]


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def first():
    return json.loads((ROOT / "tests/data/bazi/passage-premises.json").read_text())


@pytest.mark.parametrize("index", range(17))
def test_all_seventeen_first_accepted_contradictions_are_now_rejected(index):
    case = json.loads((ROOT / "tests/data/bazi/passage-invalid.json").read_text())[
        index
    ]
    before = deepcopy(case)
    with pytest.raises(ValidationError):
        ClassicalPassage.model_validate(case)
    assert case == before


def test_every_parent_projection_subset_and_partial_items_remain_valid():
    value = first()["passage"]
    names = list(value)
    for size in range(len(names) + 1):
        for selected in combinations(names, size):
            payload = {name: deepcopy(value[name]) for name in selected}
            ClassicalPassage.model_validate(payload)
    for node in value["nodes"]:
        for key in node:
            PassageNode.model_validate({key: node[key]})
    for name in ("visible_paths", "all_hidden_paths", "mixed_paths"):
        for path in value[name]:
            for key in path:
                PassagePath.model_validate({key: path[key]})


def test_all_physical_stems_and_hidden_catalog_nodes_validate_without_mutation():
    for position in ("year", "month", "day", "hour"):
        for stem, (element, _) in STEM_ELEMENTS.items():
            node = dict(
                id=f"{position}:stem:{stem}",
                pillar=position,
                plane="stem",
                stem=stem,
                element=element.value,
                branch=None,
                hidden_rank=None,
            )
            PassageNode.model_validate(node)
        for branch, hidden in BRANCH_HIDDEN_STEMS.items():
            for rank, stem in enumerate(hidden):
                node = dict(
                    id=f"{position}:hidden:{stem}",
                    pillar=position,
                    plane="hidden",
                    stem=stem,
                    element=STEM_ELEMENTS[stem][0].value,
                    branch=branch,
                    hidden_rank=rank,
                )
                PassageNode.model_validate(node)
    with pytest.raises(ValidationError, match="五行"):
        PassageNode.model_validate(dict(id="year:stem:癸", element="火"))
    with pytest.raises(ValidationError, match="藏干序位"):
        PassageNode.model_validate(
            dict(id="month:hidden:辛", branch="酉", hidden_rank=2)
        )


def test_all_five_generating_intermediary_chains_accept_all_eight_plane_patterns():
    representative = {
        element: next(s for s, (e, _) in STEM_ELEMENTS.items() if e == element)
        for element in GENERATION_CYCLE
    }
    for start in GENERATION_CYCLE:
        middle = GENERATION_CYCLE[start]
        end = GENERATION_CYCLE[middle]
        for planes in product(("stem", "hidden"), repeat=3):
            refs = [
                f"{p}:{plane}:{representative[e]}"
                for p, plane, e in zip(
                    ("year", "month", "day"), planes, (start, middle, end)
                )
            ]
            path = dict(
                from_node=refs[0],
                via_node=refs[1],
                to_node=refs[2],
                elements=[e.value for e in (start, middle, end)],
                plane=planes[0] if len(set(planes)) == 1 else "mixed",
            )
            PassagePath.model_validate(path)
            rotated = GENERATION_CYCLE[end]
            wrong = [middle.value, end.value, rotated.value]
            with pytest.raises(ValidationError, match="节点引用"):
                PassagePath.model_validate({**path, "elements": wrong})


@pytest.mark.parametrize(
    "assessment,expected",
    [({}, None), ({"hidden_stem_ledger": [], "relations": []}, False)],
)
def test_unknown_root_receipt_and_supplied_empty_receipt_stay_distinct(
    assessment, expected
):
    pillars = first()["pillars"]
    value = build_passage_evidence(pillars, assessment)
    ClassicalPassage.model_validate(value)
    assert all(
        p["all_nodes_have_remaining_roots"] is expected for p in value["visible_paths"]
    )
    changed = deepcopy(value)
    changed["visible_paths"][0]["all_nodes_have_remaining_roots"] = True
    with pytest.raises(ValidationError, match="根预算"):
        ClassicalPassage.model_validate(changed)


def test_validation_never_calls_a_strength_or_passage_solver(monkeypatch):
    import fatebridge.core.classical_passage as passage
    from fatebridge.core.elements import ElementAnalysis

    def forbidden(*args, **kwargs):
        raise AssertionError("Output validation must only compare supplied facts")

    monkeypatch.setattr(ElementAnalysis, "analyze_day_master_strength", forbidden)
    monkeypatch.setattr(passage, "build_passage_evidence", forbidden)
    ClassicalPassage.model_validate(first()["passage"])


@pytest.mark.parametrize("topic", TOPICS)
def test_all_ten_tools_keep_valid_summary_only_projection(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    path = (
        prefix
        + (
            ".structure_profile.evidence_chain"
            if topic == "birth"
            else ".evidence_chain"
        )
        + ".classical_passage.summary.visible_path_count"
    )
    payload = inputs(spec)
    opts = dict(
        as_of=AS_OF, fields=[path], strict_fields=True, include_snapshot_text=False
    )
    http = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    spec.output_model.model_validate(business(cli))


@pytest.mark.parametrize("topic", TOPICS)
def test_all_ten_tools_reject_contradictory_nested_receipts_before_projection(
    topic, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    chain = "structure_profile" if topic == "birth" else None
    request = inputs(spec)
    original = execution.execute_spec

    def corrupt(actual, parsed):
        if actual.key != spec.key:
            return original(actual, parsed)
        result = original(actual, parsed)
        value = deepcopy(result)
        business_result = value[prefix]
        evidence = (business_result[chain] if chain else business_result)[
            "evidence_chain"
        ]
        evidence["classical_passage"]["summary"]["visible_path_count"] += 1
        fake = replace(actual, bind=lambda _: (lambda: value, (), {}))
        return original(fake, parsed)

    monkeypatch.setattr(execution, "execute_spec", corrupt)
    opts = dict(
        as_of=AS_OF,
        fields=["analysis_type"],
        strict_fields=True,
        include_snapshot_text=False,
    )
    http = rest.post(spec.rest_path, json=request, params=opts)
    protocol = asyncio.run(native(spec, request, **opts))
    code, cli = call_cli(
        spec,
        request,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"
    assert (
        business(protocol.structured_content)["error_code"]
        == http.json()["error_code"]
        == "internal_error"
    )

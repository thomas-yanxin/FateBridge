"""Versioned disclosure provenance preserves history and current-run guards."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.application.execution import validate_output
from fatebridge.application.projection import project_fields
from fatebridge.core import canping_schedule_basis as basis
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.output_canping_schedule import CanpingScheduleBasis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import NumerologySourceError

FIXTURE = Path(__file__).parents[1] / "fixtures/canping_scope_rendering_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
SPEC = next(spec for spec in CATALOG if spec.key == "canping")


@pytest.mark.parametrize(
    "case",
    [
        c
        for c in REFERENCE["reader_cases"]
        if "generic_regional_caveat_v1" not in json.dumps(c)
    ],
    ids=lambda c: c["id"],
)
def test_runtime_and_published_schema_match_predeclared_reader_contract(case):
    value = deepcopy(case["payload"])
    before = deepcopy(value)
    schema = CanpingScheduleBasis.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert (not list(Draft202012Validator(schema).iter_errors(value))) == case[
        "must_accept"
    ]
    if case["must_accept"]:
        parsed = CanpingScheduleBasis.model_validate(value)
        assert parsed.model_dump(exclude_unset=True) == value
    else:
        with pytest.raises(ValidationError):
            CanpingScheduleBasis.model_validate(value)
    assert value == before


def test_known_text_does_not_turn_an_extension_into_a_source_assertion():
    value = {
        "scope_statement": REFERENCE["revisions"][REFERENCE["current_revision"]],
        "scope_rendering": {"future_extension": "preserved as unknown"},
    }
    parsed = CanpingScheduleBasis.model_validate(value)
    assert parsed.model_dump(exclude_unset=True) == value
    CanpingScheduleBasis(scope_rendering=None)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        patch.setenv("SE_EPHE_PATH", str(tmp_path_factory.mktemp("scope-empty-ephe")))
        for key in ["FATEBRIDGE_JPL_FILE", "FATEBRIDGE_SOLAR_SPK_FILE"]:
            patch.delenv(key, raising=False)
        yield [
            build_canping_result(
                **REFERENCE["engineering_payload"], zone=zone, dayun_method=profile
            )
            for profile in REFERENCE["profiles"]
            for zone in REFERENCE["clocks"]
        ]


@pytest.mark.parametrize("index", range(6))
def test_current_output_binds_software_text_separately_from_original_book(
    generated, index
):
    output = deepcopy(generated[index])
    validate_output(SPEC, output)
    receipt = output["canping_timing"]["schedule_basis"]
    assert (
        receipt["scope_rendering"]
        == REFERENCE["receipts"][REFERENCE["current_revision"]]
    )
    assert (
        receipt["scope_statement"]
        == REFERENCE["revisions"][REFERENCE["current_revision"]]
    )
    assert receipt["scope_rendering"]["layer"] == "software_explanatory_scope"
    for flag in [
        "whole_book_alignment_established",
        "real_world_efficacy_validated",
        "datetime_mapping_is_original_source_formula",
        "target_excerpt_ten_year_step_explicitly_collated",
    ]:
        assert receipt[flag] is False
    for field in ["policy_id", "revision", "text_sha256", "layer"]:
        leaf = project_fields(
            output,
            ["canping_timing.schedule_basis.scope_rendering." + field],
            strict_fields=True,
        )
        SPEC.output_model.model_validate(leaf)
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(leaf)


def _synchronize(output):
    receipt = output["canping_timing"]["schedule_basis"]
    for row in output["numerology_evidence"]["rule_trace"]:
        if row["rule_id"] == basis.POLICY_ID:
            row["facts"] = deepcopy(receipt)
    marker = "[配运原典与日期映射]"
    text = output["snapshot_text"]
    start = text.index(marker)
    following = text.find("\n\n[", start)
    end = len(text) if following < 0 else following
    output["snapshot_text"] = (
        text[:start] + basis.schedule_basis_snapshot(receipt) + text[end:]
    )


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("fault", REFERENCE["live_faults"])
def test_forged_copies_cannot_change_actual_run_or_original_source(
    generated, index, fault
):
    output = deepcopy(generated[index])
    receipt = output["canping_timing"]["schedule_basis"]
    if fault == "legacy_consistent_copies":
        old = "generic_regional_caveat_v1"
        receipt["scope_statement"] = REFERENCE["revisions"][old]
        receipt["scope_rendering"] = deepcopy(REFERENCE["receipts"][old])
        with pytest.raises(ValidationError):
            CanpingScheduleBasis.model_validate(receipt)
    elif fault == "unknown_text":
        receipt["scope_statement"] = "全书与现实预测均已验证。"
    elif fault == "wrong_revision":
        receipt["scope_rendering"]["revision"] = "generic_regional_caveat_v1"
    elif fault == "wrong_digest":
        receipt["scope_rendering"]["text_sha256"] = "0" * 64
    elif fault == "wrong_layer":
        receipt["scope_rendering"]["layer"] = "original_book_quote"
    elif fault == "missing_receipt":
        del receipt["scope_rendering"]
    elif fault == "original_book_hash":
        receipt["sources"]["heluo_najda"]["pdf_sha256"] = "0" * 64
    elif fault == "quote_rewrite":
        receipt["clauses"][0]["text"] += "原典已认证"
    _synchronize(output)
    with pytest.raises(NumerologySourceError):
        validate_output(SPEC, output)

"""Versioned disclosure provenance preserves history and current-run guards."""

import hashlib
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
from tests.canping_scope_fixture_compat import (
    rewind_scope_receipt_checked,
    upgrade_scope_receipt_checked,
)

FIXTURE = Path(__file__).parent / "fixtures/canping_scope_rendering_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
SPEC = next(spec for spec in CATALOG if spec.key == "canping")


def test_preedit_reference_and_original_source_identities_are_retained():
    seal = json.loads((FIXTURE / "reference-seal.json").read_bytes())
    assert (
        hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
        == seal["sha256"]
    )
    assert REFERENCE["frozen_before_production_edits"]
    assert REFERENCE["not_a_blind_holdout"]
    assert (
        hashlib.sha256(
            (FIXTURE / "original-canping-golden.json").read_bytes()
        ).hexdigest()
        == REFERENCE["golden"]["sha256"]
    )
    for source in REFERENCE["primary_sources"]:
        assert (
            hashlib.sha256((FIXTURE / source["path"]).read_bytes()).hexdigest()
            == source["sha256"]
        )


@pytest.mark.parametrize("case", REFERENCE["reader_cases"], ids=lambda c: c["id"])
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


def test_historical_full_and_leaf_reading_preserves_literal_without_new_metadata():
    raw = (FIXTURE / "original-canping-golden.json").read_bytes()
    value = json.loads(raw)
    value.pop("run_metadata", None)
    for body in [
        value,
        project_fields(
            value, ["canping_timing.schedule_basis.scope_statement"], strict_fields=True
        ),
    ]:
        before = deepcopy(body)
        SPEC.output_model.model_validate(body)
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(body)
        assert body == before
        assert "scope_rendering" not in body["canping_timing"]["schedule_basis"]
    assert (FIXTURE / "original-canping-golden.json").read_bytes() == raw


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
        # Reading known historical text is different from producing it as the
        # renderer for this new execution.
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


def test_migration_removes_only_independently_verified_new_metadata(generated):
    current = deepcopy(generated[0])
    before = rewind_scope_receipt_checked(current)
    assert upgrade_scope_receipt_checked(before) == current
    before["dayun"][0]["index"] = 999
    assert (
        rewind_scope_receipt_checked(upgrade_scope_receipt_checked(before))["dayun"][0][
            "index"
        ]
        == 999
    )


def test_current_control_comparison_requires_both_new_receipt_copies(generated):
    output = deepcopy(generated[0])
    del output["canping_timing"]["schedule_basis"]["scope_rendering"]
    for row in output["numerology_evidence"]["rule_trace"]:
        if row["rule_id"] == basis.POLICY_ID:
            del row["facts"]["scope_rendering"]
    assert rewind_scope_receipt_checked(output) == output
    with pytest.raises(AssertionError):
        rewind_scope_receipt_checked(output, require_present=True)


@pytest.mark.parametrize("where", ["basis", "trace", "both"])
def test_migration_does_not_hide_forged_new_receipts(generated, where):
    output = deepcopy(generated[0])
    values = [output["canping_timing"]["schedule_basis"]]
    trace = next(
        r["facts"]
        for r in output["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == basis.POLICY_ID
    )
    if where == "trace":
        values = [trace]
    elif where == "both":
        values.append(trace)
    for receipt in values:
        receipt["scope_rendering"]["text_sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        rewind_scope_receipt_checked(output)

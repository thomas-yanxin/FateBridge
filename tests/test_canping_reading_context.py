"""Actual profile/clock conditions and joined primary-source citations."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.projection import project_fields
from fatebridge.core import canping_schedule_basis as basis
from fatebridge.core.canping_schedule_validation import require_schedule_binding
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.output_canping_schedule import CanpingScheduleBasis
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parent / "fixtures/canping_reading_context_v1"
REFERENCE = json.loads((ROOT / "reference-v2.json").read_bytes())
PROFILES = list(REFERENCE["roles_by_profile"])


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


def actual(profile, clock):
    return build_canping_result(
        **REFERENCE["engineering_payload"], zone=clock["zone"], dayun_method=profile
    )


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("clock", REFERENCE["clock_cases"], ids=lambda r: r["zone"])
def test_snapshot_conditions_follow_actual_mapping_not_a_generic_warning(
    profile, clock
):
    out = actual(profile, clock)
    snapshot = out["snapshot_text"]
    assert "未来地区规则有条件" not in snapshot
    if profile == basis.LEGACY:
        assert "没有已核的实际起止日期" in snapshot
    elif clock["kind"] == "fixed":
        assert "显式固定偏移" in snapshot and "固定偏移假设" in snapshot
    else:
        assert clock["zone"] in snapshot and "将来立法" in snapshot


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("clock", REFERENCE["clock_cases"], ids=lambda r: r["zone"])
def test_reading_context_binds_actual_profile_clock_books_pages_and_roles(
    profile, clock
):
    out = actual(profile, clock)
    b = out["canping_timing"]["schedule_basis"]
    context = b["reading_context"]
    assert context["profile_id"] == profile == out["canping_timing"]["profile_id"]
    assert context["timezone_spec"] == clock["zone"] == b["timezone_spec"]
    assert context["future_clock_policy"] == clock["policy"] == b["future_clock_policy"]
    citations = context["source_citations"]
    assert [c["source_id"] for c in citations] == list(REFERENCE["books"])
    for c in citations:
        expected = REFERENCE["books"][c["source_id"]]
        assert {k: c[k] for k in expected} == expected
        assert c["pdf_pages"] == REFERENCE["pdf_pages"][c["source_id"]]
        assert c["roles"] == REFERENCE["roles_by_profile"][profile][c["source_id"]]
        assert c["edition"] in out["snapshot_text"]
    assert out["canping_timing"]["first_row"] == out["dayun"][0]
    assert out["canping_timing"]["selected"] is None
    if profile == basis.LEGACY:
        assert out["canping_timing"]["first_period"] is None
    else:
        assert out["canping_timing"]["first_period"] == out["dayun"][0]
    assert b["whole_book_alignment_established"] is False
    assert b["real_world_efficacy_validated"] is False
    require_schedule_binding(out)


@pytest.mark.parametrize(
    "fault", ["book", "pages", "role", "profile", "clock", "statement"]
)
def test_forged_context_cannot_agree_with_itself_and_bypass_the_actual_run(fault):
    out = actual(basis.APPENDIX, REFERENCE["clock_cases"][0])
    context = out["canping_timing"]["schedule_basis"]["reading_context"]
    if fault == "book":
        context["source_citations"][1]["edition"] = "unregistered printing"
    elif fault == "pages":
        context["source_citations"][1]["pdf_pages"] = [105, 106]
    elif fault == "role":
        context["source_citations"][1]["roles"] = ["applied_rule"]
    elif fault == "profile":
        context["profile_id"] = basis.LEGACY
    elif fault == "clock":
        context["future_clock_policy"] = REFERENCE["clock_cases"][1]["policy"]
    else:
        context["date_mapping_statement"] = (
            "All future legal times have been certified."
        )
    # Synchronize the trace too; matching two forged copies is insufficient.
    for row in out["numerology_evidence"]["rule_trace"]:
        if row["rule_id"] == basis.POLICY_ID:
            row["facts"] = deepcopy(out["canping_timing"]["schedule_basis"])
    with pytest.raises(NumerologySourceError):
        require_schedule_binding(out)


@pytest.mark.parametrize("field", ["date_mapping_statement", "source_citations"])
def test_real_partial_projection_retains_requested_context_without_guessing_omitted_fields(
    field,
):
    out = actual(basis.CONTINUOUS, REFERENCE["clock_cases"][1])
    selected = project_fields(
        out, [f"canping_timing.schedule_basis.reading_context.{field}"]
    )
    b = selected["canping_timing"]["schedule_basis"]
    assert set(b) == {"reading_context"}
    assert set(b["reading_context"]) == {field}
    assert (
        b["reading_context"][field]
        == out["canping_timing"]["schedule_basis"]["reading_context"][field]
    )
    CanpingScheduleBasis.model_validate(b)


def test_frozen_original_source_file_is_not_rewritten_to_make_the_join_pass():
    assert (
        hashlib.sha256(basis.COLLATION_PATH.read_bytes()).hexdigest()
        == REFERENCE["source_file_sha256"]
    )
    original = ROOT / "reference.json"
    assert json.loads(original.read_bytes())["frozen_before_production_edits"]
    assert (
        hashlib.sha256(original.read_bytes()).hexdigest()
        == REFERENCE["initial_reference_sha256"]
    )


def test_registered_citations_remain_checked_in_a_source_only_projection():
    out = actual(basis.LEGACY, REFERENCE["clock_cases"][0])
    b = {
        "reading_context": {
            "source_citations": deepcopy(
                out["canping_timing"]["schedule_basis"]["reading_context"][
                    "source_citations"
                ]
            )
        }
    }
    CanpingScheduleBasis.model_validate(b)
    b["reading_context"]["source_citations"][0]["pdf_sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        CanpingScheduleBasis.model_validate(b)


def test_internally_synchronized_fake_clock_still_compares_actual_birth_rules():
    out = actual(basis.APPENDIX, REFERENCE["clock_cases"][0])
    b = out["canping_timing"]["schedule_basis"]
    b["timezone_rules"] = {"database": "explicit_fixed_offset"}
    b["future_clock_policy"] = REFERENCE["clock_cases"][1]["policy"]
    b["timezone_spec"] = "+00:00"
    b["reading_context"] = basis.build_reading_context(
        b["profile_id"], b["future_clock_policy"], b["timezone_spec"]
    )
    CanpingScheduleBasis.model_validate(b)
    for row in out["numerology_evidence"]["rule_trace"]:
        if row["rule_id"] == basis.POLICY_ID:
            row["facts"] = deepcopy(b)
    marker = "[配运原典与日期映射]"
    start = out["snapshot_text"].index(marker)
    end = out["snapshot_text"].find("\n\n[", start)
    assert end > start
    out["snapshot_text"] = (
        out["snapshot_text"][:start]
        + basis.schedule_basis_snapshot(b)
        + out["snapshot_text"][end:]
    )
    assert out["numerology_evidence"]["birth_clock"]["timezone_spec"] == "Europe/London"
    with pytest.raises(NumerologySourceError):
        require_schedule_binding(out)

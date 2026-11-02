"""Synthetic plan/selection attacks: do not mistake these for real outcomes."""

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.validation.qimen_study import QimenCommitment, audit_study
from tests.test_qimen_study import AS_OF, frozen_study, outcomes, packet  # noqa: F401


@pytest.mark.parametrize(
    "field,value",
    [
        ("baseline_probability", 0.99),
        ("decision_threshold", 0.9),
        ("minimum_evaluable", 1000),
        ("minimum_brier_skill", 0.9),
        ("confidence_level", 0.8),
        ("planned_evaluations", 10),
        ("window_start", "2027-01-02T00:00:00Z"),
        ("window_end", "2027-01-20T00:00:00Z"),
        ("preregistered_at", "2025-01-02T00:00:00Z"),
        ("registration_reference", "changed-after-outcomes"),
        ("baseline_frozen_at", "2024-01-01T00:00:00Z"),
        ("training_subject_ids", ["undeclared-extra-training-subject"]),
        ("study_id", "changed-study-id"),
    ],
)
def test_sealed_plan_fields_cannot_change_without_changing_evidence(
    packet, field, value
):
    # Also audit the unmodified packet so an unrelated engine error cannot
    # make a rejection test pass for the wrong reason.
    assert audit_study(packet, outcomes(), as_of=AS_OF)["registered_count"] == 3
    raw = packet.model_dump(mode="json")
    raw["study"]["plan"][field] = value
    with pytest.raises(ValueError, match="研究输入|封存|未绑定"):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=AS_OF)


def test_abstention_cannot_be_removed_from_every_list_to_fake_full_coverage(packet):
    raw = packet.model_dump(mode="json")
    raw["study"]["plan"]["baseline_probability"] = 0.99
    raw["study"]["plan"]["cohort"] = [
        r for r in raw["study"]["plan"]["cohort"] if r["case_id"] != "jia"
    ]
    raw["study"]["castings"] = [
        r for r in raw["study"]["castings"] if r["case_id"] != "jia"
    ]
    raw["forecasts"] = [r for r in raw["forecasts"] if r["case_id"] != "jia"]
    raw["evidence"].pop("jia")
    assert all(
        r
        == next(
            f
            for f in packet.model_dump(mode="json")["forecasts"]
            if f["case_id"] == r["case_id"]
        )
        for r in raw["forecasts"]
    )
    with pytest.raises(ValueError, match="研究输入|封存|未绑定"):
        audit_study(
            QimenCommitment.model_validate(raw),
            [o for o in outcomes() if o.case_id != "jia"],
            as_of=AS_OF,
        )


def test_target_cannot_be_relabelled_consistently_in_plan_and_policy(packet):
    from fatebridge.validation.qimen_study import FrozenQimenPolicy, policy_fingerprint

    raw = packet.model_dump(mode="json")
    raw["study"]["plan"][
        "target_definition"
    ] = "A different target selected after seeing outcomes"
    raw["study"]["policy"]["target_definition"] = raw["study"]["plan"][
        "target_definition"
    ]
    policy = FrozenQimenPolicy.model_validate(raw["study"]["policy"])
    raw["study"]["plan"]["interpretation_policy_sha256"] = policy_fingerprint(policy)
    # No existing forecast/evidence hashes were updated.
    with pytest.raises(ValueError, match="研究输入|封存|未绑定"):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=AS_OF)


def test_new_packet_binds_the_same_complete_input_in_every_case(packet):
    from fatebridge.validation.qimen_study import study_input_fingerprint

    assert packet.format == "qimen_forecast_commitment_v3"
    expected = study_input_fingerprint(packet.study)
    assert packet.study_input_sha256 == expected
    assert all(e["study_input_sha256"] == expected for e in packet.evidence.values())
    assert set(packet.evidence) == {m.case_id for m in packet.study.plan.cohort}


def test_updating_only_the_new_header_hash_still_fails_old_per_case_receipts(packet):
    from fatebridge.validation.qimen_study import StudyInput, study_input_fingerprint

    raw = packet.model_dump(mode="json")
    raw["study"]["plan"]["baseline_probability"] = 0.99
    raw["study_input_sha256"] = study_input_fingerprint(
        StudyInput.model_validate(raw["study"])
    )
    with pytest.raises(ValueError, match="未绑定"):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=AS_OF)


def test_changing_only_envelope_hash_without_updating_forecasts_fails(packet):
    from fatebridge.validation.qimen_study import StudyInput, study_input_fingerprint

    raw = packet.model_dump(mode="json")
    raw["study"]["plan"]["baseline_probability"] = 0.99
    raw["study_input_sha256"] = study_input_fingerprint(
        StudyInput.model_validate(raw["study"])
    )
    for e in raw["evidence"].values():
        e["study_input_sha256"] = raw["study_input_sha256"]
    with pytest.raises(ValueError, match="未绑定"):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=AS_OF)


def test_whole_packet_reseal_is_rejected_against_independently_kept_original_digest(
    packet,
):
    from fatebridge.validation.qimen_study import commitment_fingerprint, seal_forecasts
    from tests.test_qimen_study import ISSUED

    original_digest = commitment_fingerprint(packet)
    study = packet.study.model_copy(deep=True)
    study.plan.baseline_probability = 0.99
    replacement = seal_forecasts(study, at=ISSUED)
    assert commitment_fingerprint(replacement) != original_digest
    with pytest.raises(ValueError, match="事前独立保存"):
        audit_study(
            replacement,
            outcomes(),
            as_of=AS_OF,
            expected_commitment_sha256=original_digest,
        )


def test_full_cohort_deletion_and_reseal_cannot_replace_the_anchored_packet(packet):
    from fatebridge.validation.qimen_study import (
        StudyInput,
        commitment_fingerprint,
        seal_forecasts,
    )
    from tests.test_qimen_study import ISSUED

    original_digest = commitment_fingerprint(packet)
    study = packet.study.model_dump(mode="json")
    study["plan"]["baseline_probability"] = 0.99
    study["plan"]["cohort"] = [
        m for m in study["plan"]["cohort"] if m["case_id"] != "jia"
    ]
    study["castings"] = [c for c in study["castings"] if c["case_id"] != "jia"]
    replacement = seal_forecasts(StudyInput.model_validate(study), at=ISSUED)
    with pytest.raises(ValueError, match="事前独立保存"):
        audit_study(
            replacement,
            [o for o in outcomes() if o.case_id != "jia"],
            as_of=AS_OF,
            expected_commitment_sha256=original_digest,
        )


def test_data_kind_is_part_of_the_bound_study_input(packet):
    raw = packet.model_dump(mode="json")
    raw["study"]["plan"]["data_kind"] = "real_world_submission"
    with pytest.raises(ValueError, match="研究输入"):
        QimenCommitment.model_validate(raw)


def test_issue_time_edit_is_caught_by_the_original_packet_anchor(packet):
    from fatebridge.validation.qimen_study import commitment_fingerprint

    original_digest = commitment_fingerprint(packet)
    raw = packet.model_dump(mode="json")
    raw["forecasts"][0]["issued_at"] = "2026-12-30T12:00:00Z"
    changed = QimenCommitment.model_validate(raw)
    with pytest.raises(ValueError, match="事前独立保存"):
        audit_study(
            changed, outcomes(), as_of=AS_OF, expected_commitment_sha256=original_digest
        )


@pytest.mark.parametrize(
    "value", ["0" * 64, "ABC", "a" * 63, "A" * 64, "a" * 64 + "\n"]
)
def test_wrong_or_malformed_expected_packet_digest_is_rejected(packet, value):
    with pytest.raises(ValueError, match="指纹|SHA256"):
        audit_study(packet, outcomes(), as_of=AS_OF, expected_commitment_sha256=value)


def test_digest_ignores_json_whitespace_and_key_order_but_does_not_authenticate_registration(
    packet,
):
    from fatebridge.validation.qimen_study import commitment_fingerprint

    expected = commitment_fingerprint(packet)
    raw = json.loads(
        json.dumps(packet.model_dump(mode="json"), indent=4, sort_keys=True)
    )
    normalized = QimenCommitment.model_validate(raw)
    assert commitment_fingerprint(normalized) == expected
    report = audit_study(
        normalized, outcomes(), as_of=AS_OF, expected_commitment_sha256=expected
    )
    anchor = report["qimen_commitment_anchor"]
    assert anchor["status"] == "supplied_expected_digest_matched"
    assert not anchor["expected_digest_provenance_authenticated"]
    assert not anchor["external_registration_authenticated"]
    assert not report["validated_qimen_predictor"] and not report["authority_certified"]


def test_model_copy_bypass_is_revalidated_at_the_audit_boundary(packet):
    changed = packet.model_copy(deep=True)
    changed.study.plan.baseline_probability = 0.99
    with pytest.raises(ValueError, match="研究输入"):
        audit_study(changed, outcomes(), as_of=AS_OF)


def test_legacy_format_is_not_silently_upgraded_or_rehashed(packet):
    raw = packet.model_dump(mode="json")
    raw["format"] = "qimen_forecast_commitment_v1"
    raw.pop("study_input_sha256")
    with pytest.raises(ValueError, match="原固定环境"):
        QimenCommitment.model_validate(raw)


def test_real_submission_requires_independently_kept_digest_even_if_locally_consistent(
    packet, monkeypatch
):
    # Injected clocks and fictional subjects solely exercise the real-data
    # branch; this fixture is never empirical evidence.
    from fatebridge.validation import qimen_study as research
    from tests.test_qimen_study import ISSUED

    class Clock(datetime):
        current = ISSUED

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz or timezone.utc)

    monkeypatch.setattr(research, "datetime", Clock)
    study = packet.study.model_copy(deep=True)
    study.plan.data_kind = "real_world_submission"
    real_branch_packet = research.seal_forecasts(study)
    relabelled = real_branch_packet.model_dump(mode="json")
    relabelled["study"]["plan"]["data_kind"] = "synthetic"
    with pytest.raises(ValueError, match="研究输入"):
        QimenCommitment.model_validate(relabelled)
    Clock.current = AS_OF
    with pytest.raises(ValueError, match="真实研究须提供事前"):
        audit_study(real_branch_packet, outcomes(), as_of=AS_OF)
    expected = research.commitment_fingerprint(real_branch_packet)
    report = audit_study(
        real_branch_packet, outcomes(), as_of=AS_OF, expected_commitment_sha256=expected
    )
    assert (
        report["qimen_commitment_anchor"]["status"]
        == "supplied_expected_digest_matched"
    )
    assert not report["qimen_commitment_anchor"]["external_registration_authenticated"]
    assert not report["validated_qimen_predictor"]


def test_cli_emits_seal_digest_and_accepts_only_the_matched_expected_packet(
    packet, tmp_path, capsys
):
    from fatebridge.validation.qimen_study import commitment_fingerprint
    from tests.test_qimen_study import ISSUED

    spec = importlib.util.spec_from_file_location(
        "qimen_v2_cli", Path(__file__).parents[1] / "scripts/audit_qimen_study.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    source, sealed, labels, report, rejected = [
        tmp_path / n
        for n in [
            "study.json",
            "packet.json",
            "outcomes.json",
            "report.json",
            "rejected.json",
        ]
    ]
    source.write_text(packet.study.model_dump_json())
    labels.write_text("[]")
    assert (
        cli.main(
            [
                "seal",
                "--study",
                str(source),
                "--synthetic-at",
                ISSUED.isoformat(),
                "--output",
                str(sealed),
            ]
        )
        == 0
    )
    sealed_summary = json.loads(capsys.readouterr().out)
    expected = sealed_summary["commitment_sha256"]
    assert expected == commitment_fingerprint(
        QimenCommitment.model_validate_json(sealed.read_text())
    )
    args = [
        "evaluate",
        "--commitment",
        str(sealed),
        "--outcomes",
        str(labels),
        "--as-of",
        AS_OF.isoformat(),
    ]
    assert (
        cli.main(
            [*args, "--expected-commitment-sha256", expected, "--output", str(report)]
        )
        == 0
    )
    assert (
        json.loads(report.read_text())["qimen_commitment_anchor"]["status"]
        == "supplied_expected_digest_matched"
    )
    with pytest.raises(ValueError, match="事前独立保存"):
        cli.main(
            [*args, "--expected-commitment-sha256", "0" * 64, "--output", str(rejected)]
        )
    assert not rejected.exists()

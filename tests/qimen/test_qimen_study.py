"""Synthetic attacks on evidence binding, never efficacy samples."""

import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.validation import qimen_study as research
from fatebridge.validation.predictions import Outcome, digest
from fatebridge.validation.qimen_study import (
    Condition,
    FrozenQimenPolicy,
    QimenCasting,
    QimenCommitment,
    StudyInput,
    apply_policy,
    audit_study,
    engine_fingerprint,
    policy_fingerprint,
    seal_forecasts,
)

ISSUED = datetime(2026, 12, 31, tzinfo=timezone.utc)
AS_OF = datetime(2027, 3, 1, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def frozen_study():
    policy = FrozenQimenPolicy(
        policy_id="synthetic-adversarial-fixture-not-a-predictor",
        target_definition="Synthetic binary event, never an empirical sample",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="use_declared_rules",
        rules=[
            {
                "rule_id": "test-only-not-calibrated",
                "all_of": [
                    {
                        "feature": "pattern_present",
                        "pattern": "hidden_day_stem",
                        "equals": False,
                    }
                ],
                "probability": 0.8,
            }
        ],
        fallback_probability=0.2,
    )
    casts = [
        {
            "case_id": "literal",
            "subject_id": "synthetic-1",
            "casting_at": "2026-01-15T16:00:00+08:00",
            "timezone_name": "Asia/Hong_Kong",
            "longitude": 114.17,
        },
        {
            "case_id": "jia",
            "subject_id": "synthetic-2",
            "casting_at": "2026-01-20T16:00:00+08:00",
            "timezone_name": "Asia/Hong_Kong",
            "longitude": 114.17,
        },
        {
            "case_id": "fold",
            "subject_id": "synthetic-3",
            "casting_at": "2026-11-01T05:30:00Z",
            "timezone_name": "America/New_York",
            "longitude": -74.0,
        },
    ]
    for c in casts:
        c.update(
            {
                "recorded_at": "2026-12-30T00:00:00Z",
                "question_record_sha256": "a" * 64,
                "question_record_reference": "synthetic question only",
            }
        )
    study = StudyInput.model_validate(
        {
            "plan": {
                "study_id": "synthetic-qimen-replay",
                "data_kind": "synthetic",
                "preregistered_at": "2025-01-01T00:00:00Z",
                "registration_reference": "synthetic-registration-not-a-real-registry",
                "window_start": "2027-01-01T00:00:00Z",
                "window_end": "2027-02-01T00:00:00Z",
                "target_definition": policy.target_definition,
                "model_sha256": engine_fingerprint(),
                "interpretation_policy_sha256": policy_fingerprint(policy),
                "baseline_frozen_at": "2025-01-01T00:00:00Z",
                "baseline_probability": 0.5,
                "minimum_evaluable": 1,
                "training_subject_ids": [],
                "cohort": [
                    {"case_id": c["case_id"], "subject_id": c["subject_id"]}
                    for c in casts
                ],
            },
            "policy": policy.model_dump(mode="json"),
            "castings": casts,
        }
    )
    return seal_forecasts(study, at=ISSUED)


@pytest.fixture
def packet(frozen_study):
    return QimenCommitment.model_validate(frozen_study.model_dump(mode="json"))


def outcomes():
    return [
        Outcome(
            case_id=c,
            occurred=False,
            recorded_at="2027-02-02T00:00:00Z",
            source_sha256="f" * 64,
            source_reference="synthetic outcome only",
        )
        for c in ("literal", "jia", "fold")
    ]


def test_actual_replay_retains_unknowns_and_resolves_known_fold(packet):
    literal = packet.evidence["literal"]
    assert literal["result"]["qimen"]["time_ganzhi"] == "壬申"
    assert literal["result"]["qimen"]["source_disagreements"]
    assert literal["decision"]["probability"] == 0.8
    assert packet.evidence["jia"]["result"]["qimen"]["day_ganzhi"].startswith("甲")
    assert (
        packet.evidence["jia"]["decision"]["reason"]
        == "unknown_potentially_matching_rule"
    )
    folded = packet.evidence["fold"]["result"]["qimen"]
    resolution = folded["calendar_policy"]["civil_clock_resolution"]
    assert resolution["instant_utc"] == "2026-11-01T05:30:00+00:00"
    assert resolution["fold"] == 0
    assert folded["calendar_policy"]["timezone"] == "America/New_York"
    report = audit_study(packet, outcomes(), as_of=AS_OF)
    assert report["registered_count"] == 3 and report["evaluable_count"] == 2
    assert report["coverage"] == pytest.approx(2 / 3)
    assert report["calculation_error_case_ids"] == []
    assert not report["preregistered_performance_gate_met"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not report["validated_qimen_predictor"] and not report["authority_certified"]


def test_dependency_failure_remains_in_ledger(packet, monkeypatch):
    # Injected failure verifies the protocol; it is not an observed bad chart
    # or a replacement for the now-valid original fold case.
    def unavailable(**kwargs):
        return {
            "error": "synthetic injected dependency failure",
            "error_code": "calculation_error",
        }

    monkeypatch.setattr(research, "calculate_qimen_analysis", unavailable)
    replacement = seal_forecasts(packet.study, at=ISSUED)
    report = audit_study(replacement, outcomes(), as_of=AS_OF)
    assert report["registered_count"] == 3 and report["evaluable_count"] == 0
    assert report["calculation_error_case_ids"] == ["literal", "jia", "fold"]
    assert all(
        e["decision"]["reason"] == "calculation_error"
        for e in replacement.evidence.values()
    )


@pytest.mark.parametrize(
    "casting_fold,record_fold,valid", [(0, 1, True), (1, 0, False)]
)
def test_question_record_order_uses_actual_fold(
    packet, casting_fold, record_fold, valid
):
    zone = ZoneInfo("America/New_York")
    data = packet.study.castings[-1].model_dump(mode="python")
    data.update(
        casting_at=datetime(
            2026,
            11,
            1,
            1,
            45 if casting_fold == 0 else 15,
            tzinfo=zone,
            fold=casting_fold,
        ),
        recorded_at=datetime(
            2026,
            11,
            1,
            1,
            15 if record_fold == 1 else 45,
            tzinfo=zone,
            fold=record_fold,
        ),
    )
    if valid:
        casting = QimenCasting.model_validate(data)
        assert casting.casting_at.fold == 0 and casting.recorded_at.fold == 1
    else:
        with pytest.raises(ValidationError, match="记录"):
            QimenCasting.model_validate(data)


@pytest.mark.parametrize("case", ["literal", "jia", "fold"])
@pytest.mark.parametrize("probability", [None, 0.95])
def test_changed_probability_or_abstention_rejected(packet, case, probability):
    forecast = next(f for f in packet.forecasts if f.case_id == case)
    forecast.probability = 0.05 if forecast.probability == probability else probability
    with pytest.raises(ValueError, match="概率或弃权"):
        audit_study(packet, outcomes(), as_of=AS_OF)


@pytest.mark.parametrize(
    "field,value",
    [
        ("casting_at", "2026-01-15T17:00:00+08:00"),
        ("timezone_name", "+08:00"),
        ("longitude", 120.0),
        ("question_record_sha256", "b" * 64),
        ("question_record_reference", "changed"),
    ],
)
def test_changed_casting_rejected_even_when_decision_unchanged(packet, field, value):
    raw = packet.model_dump(mode="json")
    raw["study"]["castings"][0][field] = value
    with pytest.raises(ValueError, match="证据未绑定"):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=AS_OF)


@pytest.mark.parametrize("part", ["castings", "forecasts", "evidence"])
def test_cannot_delete_failed_rows(packet, part):
    raw = packet.model_dump(mode="json")
    if part == "castings":
        raw["study"][part].pop()
    elif part == "forecasts":
        raw[part].pop()
    else:
        raw[part].pop("fold")
    with pytest.raises(ValueError):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=AS_OF)


def test_forged_board_rejected_even_with_rehashed_receipt(packet):
    e = packet.evidence["literal"]
    e["result"]["qimen"]["palaces"][0]["door"] = "生门"
    packet.forecasts[0].evidence_sha256 = digest(e)
    with pytest.raises(ValueError, match="证据未绑定"):
        audit_study(packet, outcomes(), as_of=AS_OF)


def test_policy_and_engine_changes_rejected(packet, monkeypatch):
    changed = packet.model_dump(mode="json")
    changed["study"]["policy"]["god_profile"] = "yanyi_diagrams"
    with pytest.raises(ValueError, match="解释策略"):
        QimenCommitment.model_validate(changed)
    actual = research.engine_manifest()
    monkeypatch.setattr(
        research, "engine_manifest", lambda: {**actual, "new_version": True}
    )
    with pytest.raises(ValueError, match="引擎指纹"):
        audit_study(packet, outcomes(), as_of=AS_OF)


def test_mid_calculation_changes_rejected(packet, monkeypatch):
    actual = research.engine_manifest()
    calls = iter([actual, {**actual, "changed": True}])
    monkeypatch.setattr(research, "engine_manifest", lambda: next(calls))
    with pytest.raises(ValueError, match="计算期间"):
        seal_forecasts(packet.study, at=ISSUED)


def test_unknown_is_not_false_and_unrelated_layers_remain_usable(packet):
    board = packet.evidence["jia"]["result"]["qimen"]
    policy = packet.study.policy.model_copy(deep=True)
    assert apply_policy(board, policy)["probability"] is None
    policy.rules[0].all_of.append(
        Condition(
            feature="five_not_meet", equals=not board["structure"]["five_not_meet"]
        )
    )
    assert apply_policy(board, policy)["probability"] == 0.2
    policy.rules[0].all_of = [
        Condition(feature="door", trigram="坎", equals=board["palaces"][0]["door"])
    ]
    assert apply_policy(board, policy)["probability"] == 0.8


def test_qualifications_not_inferred_from_pattern_name(packet):
    board = deepcopy(packet.evidence["literal"]["result"]["qimen"])
    policy = packet.study.policy.model_copy(deep=True)
    policy.rules[0].all_of = [
        Condition(feature="pattern_present", pattern="door_pressure", equals=True)
    ]
    evidence = apply_policy(board, policy)["rules"][0]["conditions"][0]["evidence"]
    assert evidence["patterns"] and all(
        p["traditional_meaning"] for p in evidence["patterns"]
    )
    policy.rules[0].all_of = [
        Condition(
            feature="pattern_conditions_observed",
            pattern="door_pressure",
            equals=False,
        )
    ]
    assert apply_policy(board, policy)["probability"] == 0.2
    # Emulate an older/incomplete evidence producer on an isolated copy.
    # The presence of a pattern name must never reconstruct missing conditions.
    for pattern in board["patterns"]:
        if pattern["rule_id"] == "door_pressure":
            pattern.pop("qualification", None)
    assert apply_policy(board, policy)["probability"] is None


def test_source_conflict_abstention_policy_is_frozen(packet):
    policy = packet.study.policy.model_copy(deep=True)
    policy.source_disagreement_action = "abstain"
    decision = apply_policy(packet.evidence["literal"]["result"]["qimen"], policy)
    assert decision["probability"] is None
    assert decision["reason"] == "declared_source_disagreement_abstention"
    assert policy_fingerprint(policy) != policy_fingerprint(packet.study.policy)


@pytest.mark.parametrize(
    "condition",
    [
        {"feature": "door", "equals": "生门"},
        {"feature": "door", "equals": "生门", "trigram": "中"},
        {"feature": "stars_fuyin", "equals": 1},
        {"feature": "stars_fuyin", "equals": "true"},
        {"feature": "stars_fuyin", "equals": True, "trigram": "坎"},
        {
            "feature": "pattern_present",
            "pattern": "unimplemented_year_stem",
            "equals": False,
        },
        {"feature": "pattern_present", "equals": False},
        {"feature": "outcomes.occurred", "equals": True},
        {"feature": "door", "trigram": "坎", "equals": "生"},
        {"feature": "hour_void_scope", "trigram": "坎", "equals": "maybe"},
    ],
)
def test_no_arbitrary_paths_fake_center_or_type_coercion(condition):
    with pytest.raises(ValidationError):
        Condition.model_validate(condition)


@pytest.mark.parametrize(
    "field,value",
    [
        ("casting_at", "2026-01-15T16:00:01+08:00"),
        ("casting_at", "2026-01-15T16:00:00.001+08:00"),
        ("casting_at", "2026-01-15T16:00:00"),
        ("recorded_at", "2026-01-01T00:00:00Z"),
        ("timezone_name", "not/a/zone"),
        ("longitude", 181.0),
    ],
)
def test_no_clock_guessing_or_silent_truncation(packet, field, value):
    casting = packet.study.castings[0].model_dump(mode="json")
    casting[field] = value
    with pytest.raises(ValueError):
        QimenCasting.model_validate(casting)


def test_training_declaration_and_model_copy_bypass(packet):
    study = packet.study.model_copy(deep=True)
    study.plan.training_subject_ids = None
    with pytest.raises(ValueError, match="训练主体"):
        seal_forecasts(study, at=ISSUED)
    packet.forecasts[0] = packet.forecasts[0].model_copy(update={"probability": 1.5})
    with pytest.raises(ValueError):
        audit_study(packet, outcomes(), as_of=AS_OF)


def test_real_submission_cannot_backdate(packet):
    study = packet.study.model_copy(deep=True)
    study.plan.data_kind = "real_world_submission"
    with pytest.raises(ValueError, match="回溯发布"):
        seal_forecasts(study, at=ISSUED)


@pytest.mark.parametrize(
    "end", ["2026-12-30T23:59:59+00:00", "2027-01-01T00:00:00+00:00"]
)
def test_cannot_backfill_start_time_after_window_opens_or_clock_reverses(
    packet, monkeypatch, end
):
    moments = iter([ISSUED, datetime.fromisoformat(end)])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(moments)

    study = packet.study.model_copy(deep=True)
    study.plan.data_kind = "real_world_submission"
    monkeypatch.setattr(research, "datetime", Clock)
    with pytest.raises(ValueError, match="时钟倒退|窗口已开始"):
        seal_forecasts(study)


def test_json_manifest_is_canonical_and_ephemeris_changes_invalidate_replay(
    packet, monkeypatch
):
    manifest = research.engine_manifest()
    assert json.loads(json.dumps(manifest)) == manifest
    changed = {**manifest, "ephemeris_inventory": [{"same-name.se1": "a" * 64}]}
    monkeypatch.setattr(research, "engine_manifest", lambda: changed)
    with pytest.raises(ValueError, match="引擎指纹"):
        audit_study(packet, outcomes(), as_of=AS_OF)


def test_missing_feature_is_unknown_and_early_match_has_priority(packet):
    board = packet.evidence["literal"]["result"]["qimen"]
    policy = packet.study.policy.model_copy(deep=True)
    policy.rules[0].all_of = [
        Condition(feature="door", trigram="坎", equals=board["palaces"][0]["door"])
    ]
    later = policy.rules[0].model_copy(deep=True)
    later.rule_id = "later"
    later.probability = 0.1
    policy.rules.append(later)
    assert apply_policy(board, policy)["probability"] == 0.8
    del board["palaces"][0]["door"]
    assert apply_policy(board, policy)["probability"] is None


@pytest.mark.parametrize("malformed", ["false", 0, [], {}])
def test_malformed_boolean_evidence_is_unknown_not_a_false_condition(packet, malformed):
    board = packet.evidence["literal"]["result"]["qimen"]
    policy = packet.study.policy.model_copy(deep=True)
    policy.rules[0].all_of = [Condition(feature="five_not_meet", equals=True)]
    board["structure"]["five_not_meet"] = malformed
    decision = apply_policy(board, policy)
    assert decision["probability"] is None
    assert decision["reason"] == "unknown_potentially_matching_rule"


def test_all_abstain_is_zero_evidence(packet):
    study = packet.study.model_copy(deep=True)
    study.policy.rules = []
    study.policy.fallback_probability = None
    study.plan.interpretation_policy_sha256 = policy_fingerprint(study.policy)
    report = audit_study(seal_forecasts(study, at=ISSUED), outcomes(), as_of=AS_OF)
    assert report["coverage"] == 0 and report["evaluable_count"] == 0
    assert report["real_world_efficacy"] == "not_tested"
    assert not report["authority_certified"]


def test_cli_round_trip(packet, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "qimen_study_cli",
        Path(__file__).parents[2] / "scripts/qimen/audit_qimen_study.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    source, receipt, labels, report = [
        tmp_path / name
        for name in ("input.json", "packet.json", "outcomes.json", "report.json")
    ]
    source.write_text(packet.study.model_dump_json())
    labels.write_text("[]")
    args = [
        "seal",
        "--study",
        str(source),
        "--synthetic-at",
        ISSUED.isoformat(),
        "--output",
        str(receipt),
    ]
    assert cli.main(args) == 0
    assert (
        cli.main(
            [
                "evaluate",
                "--commitment",
                str(receipt),
                "--outcomes",
                str(labels),
                "--as-of",
                AS_OF.isoformat(),
                "--output",
                str(report),
            ]
        )
        == 0
    )
    actual = json.loads(report.read_text())
    assert actual["registered_count"] == 3 and actual["evaluable_count"] == 0
    assert not actual["authority_certified"]
    with pytest.raises(FileExistsError):
        cli.main(args)

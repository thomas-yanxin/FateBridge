"""Run an explicitly synthetic, all-abstaining Qimen study workflow."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from fatebridge.validation.qimen_study import (
    FrozenQimenPolicy,
    StudyInput,
    audit_study,
    commitment_fingerprint,
    engine_fingerprint,
    policy_fingerprint,
    seal_forecasts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--baseline-kind",
        choices=["constant", "per-case"],
        default="constant",
        help="Synthetic references only; never actual forecast evidence",
    )
    args = parser.parse_args()
    policy = FrozenQimenPolicy(
        policy_id="synthetic-all-abstain-no-validated-probabilities",
        target_definition="Synthetic demonstration only; no real-world event or result",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="abstain",
        rules=[],
        fallback_probability=None,
    )
    castings = []
    for case, moment, zone, longitude in [
        (
            "synthetic-source-conflict",
            "2026-01-15T16:00:00+08:00",
            "Asia/Hong_Kong",
            114.17,
        ),
        (
            "synthetic-jia-identity",
            "2026-01-20T16:00:00+08:00",
            "Asia/Hong_Kong",
            114.17,
        ),
        ("synthetic-offset-fold", "2026-11-01T05:30:00Z", "America/New_York", -74.0),
    ]:
        castings.append(
            {
                "case_id": case,
                "subject_id": case,
                "casting_at": moment,
                "timezone_name": zone,
                "longitude": longitude,
                "recorded_at": "2026-12-30T00:00:00Z",
                "question_record_sha256": "0" * 64,
                "question_record_reference": "SYNTHETIC: no human subject or original question",
            }
        )
    study = StudyInput.model_validate(
        {
            "policy": policy.model_dump(mode="json"),
            "castings": castings,
            "plan": {
                "study_id": "synthetic-qimen-no-outcomes",
                "data_kind": "synthetic",
                "preregistered_at": "2025-01-01T00:00:00Z",
                "window_start": "2027-01-01T00:00:00Z",
                "window_end": "2027-02-01T00:00:00Z",
                "target_definition": policy.target_definition,
                "model_sha256": engine_fingerprint(),
                "interpretation_policy_sha256": policy_fingerprint(policy),
                "baseline_frozen_at": "2025-01-01T00:00:00Z",
                "baseline_probability": 0.5,
                "training_subject_ids": [],
                "cohort": [
                    {"case_id": c["case_id"], "subject_id": c["subject_id"]}
                    for c in castings
                ],
            },
        }
    )
    baseline_artifacts = {}
    if args.baseline_kind == "per-case":
        raw = study.model_dump(mode="json")
        raw["plan"]["baseline_probability"] = None
        baselines = []
        for casting in castings:
            name = f"baseline-{casting['case_id']}.json"
            artifact = {
                "data_kind": "synthetic",
                "case_id": casting["case_id"],
                "probability": 0.5,
                "issued_at": raw["plan"]["preregistered_at"],
                "target_definition": raw["plan"]["target_definition"],
                "window_start": raw["plan"]["window_start"],
                "window_end": raw["plan"]["window_end"],
                "note": "Synthetic reference artifact; no real forecast or outcome",
            }
            baseline_artifacts[name] = artifact
            artifact_bytes = (
                json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode()
            baselines.append(
                {k: v for k, v in artifact.items() if k not in {"data_kind", "note"}}
                | {
                    "source_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    "source_reference": "SYNTHETIC local artifact: " + name,
                }
            )
        raw["plan"]["baseline_forecasts"] = baselines
        study = StudyInput.model_validate(raw)
    commitment = seal_forecasts(
        study, at=datetime.fromisoformat("2026-12-31T00:00:00+00:00")
    )
    packet_hash = commitment_fingerprint(commitment)
    receipt = {
        "format": "qimen_local_seal_receipt_v1",
        "commitment_sha256": packet_hash,
        "study_input_sha256": commitment.study_input_sha256,
        "digest_scope": "canonical_validated_model_json_not_raw_file_bytes",
        "external_registration_authenticated": False,
        "note": "合成演示的本地收据；未取得外部登记或可信时间戳",
    }
    report = audit_study(
        commitment,
        [],
        as_of=datetime.fromisoformat("2027-03-01T00:00:00+00:00"),
        expected_commitment_sha256=packet_hash,
    )
    outputs = {
        **baseline_artifacts,
        "policy.json": policy.model_dump(mode="json"),
        "study.json": study.model_dump(mode="json"),
        "commitment.json": commitment.model_dump(mode="json"),
        "seal-receipt.json": receipt,
        "outcomes.json": [],
        "report.json": report,
    }
    if any((args.output_dir / name).exists() for name in outputs):
        raise FileExistsError("示例输出已存在；使用新目录保留旧封存记录")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        with (args.output_dir / name).open("x", encoding="utf-8") as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "registered_count",
                    "evaluable_count",
                    "coverage",
                    "real_world_efficacy",
                    "authority_certified",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

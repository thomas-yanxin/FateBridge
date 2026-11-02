"""Replay independent dense observations and retain the incompatible control."""

import hashlib
import json
from pathlib import Path

from scripts.astrodice_interval_reference import replay_interval, system
from scripts.astrodice_reference_infeasibility import verify_incompatibility
from scripts.audit_astrodice_local_reference import replay

FIXTURE = Path(__file__).parent / "fixtures/astrodice-grid5-reference-v2"


def test_frozen_dense_references_keep_all_parent_observations_and_first_outcomes():
    manifest = FIXTURE / "manifest.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "7d69cadeefc9d5621765c0dd509feefb52971afc4f951e93953557cf1e9572a2"
    )
    for name, digest in json.loads(manifest.read_text())["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    for name, expected in [("development", 2), ("fresh", 0)]:
        parent = (
            {
                k: FIXTURE / "parent" / v
                for k, v in {
                    "protocol": "protocol.json",
                    "reference": "reference.json",
                    "material": "raw",
                    "seal": "seal.json",
                }.items()
            }
            if name == "development"
            else None
        )
        result = replay(
            FIXTURE / (name + "-protocol.json"),
            FIXTURE / (name + "-reference.json"),
            FIXTURE / (name + "-raw"),
            FIXTURE / (name + "-reference-seal.json"),
            json.loads((FIXTURE / (name + "-first-certificates.json")).read_text()),
            parent_bundle=parent,
        )
        assert result == json.loads(
            (FIXTURE / (name + "-first-quality.json")).read_text()
        )
        assert result["exit_code"] == expected
        if name == "development":
            assert (
                result["rows"][0]["parent_preservation"]["matching_parent_observations"]
                == 289
            )
        else:
            assert len(result["rows"]) == 4


def test_all_actual_farkas_proofs_and_dense_interval_containments_are_exact():
    records = json.loads(
        (FIXTURE / "exact-incompatibility-diagnostic.json").read_text()
    )["records"]
    assert len(records) == 5
    for record in records:
        path = (
            "parent/reference.json"
            if record["dataset"] == "parent"
            else "development-reference.json"
        )
        row = next(
            r
            for r in json.loads((FIXTURE / path).read_text())["rows"]
            if r["id"] == record["case"]
        )
        a, b, _, _ = system(
            row,
            None,
            record["window_seconds"],
            record["odd_order"],
            record["axis"],
            step_seconds=record["grid_step_seconds"],
        )
        assert (
            str(verify_incompatibility(a, b, record["witness"]))
            == record["verified_contradiction"]
        )
    raw = json.loads((FIXTURE / "fresh-reference.json").read_text())["rows"]
    dense = json.loads((FIXTURE / "fresh-first-certificates.json").read_text())["rows"]
    coarse = json.loads((FIXTURE / "fresh-coarse-comparator.json").read_text())["rows"]
    checked = 0
    for row, d, k in zip(raw, dense, coarse):
        old = {
            **row,
            "samples": {t: v for t, v in row["samples"].items() if int(t) % 10 == 0},
        }
        for df, kf in zip(d["fits"], k["fits"]):
            if (
                df["status"]
                == kf["status"]
                == "exact_angular_interval_under_odd_polynomial_assumption"
            ):
                for (dl, dh), (kl, kh) in zip(
                    replay_interval(row, df, step_seconds=5), replay_interval(old, kf)
                ):
                    assert kl <= dl <= dh <= kh
                    checked += 1
    assert checked == 176

"""Frozen weather-study inputs shared by the prospective and trace tests."""

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from pydantic import JsonValue

from validation.meihua_weather_prospective import audit_prospective_weather_study

PROSPECTIVE_FIXTURE = Path(__file__).parents[2] / "fixtures/meihua-prospective-v1"
BEFORE_ANALYSIS = datetime.fromisoformat("2026-10-25T23:14:28+08:00")
AFTER_ANALYSIS = datetime.fromisoformat("2027-11-30T00:00:00+08:00")


class SyntheticObservations(TypedDict):
    observation_bytes: bytes
    source_receipt: dict[str, JsonValue]


def replay_prospective_study(
    as_of: datetime = BEFORE_ANALYSIS,
    directory: Path = PROSPECTIVE_FIXTURE,
    *,
    observation_bytes: bytes | None = None,
    source_receipt: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Replay the original ledger with an explicitly supplied study clock."""
    return audit_prospective_weather_study(
        directory / "study",
        directory / "attestation",
        as_of=as_of,
        observation_bytes=observation_bytes,
        source_receipt=source_receipt,
    )


def synthetic_observations() -> SyntheticObservations:
    """Read a fresh synthetic submission for tests that mutate its receipt."""
    return {
        "observation_bytes": (
            PROSPECTIVE_FIXTURE / "synthetic-five-rows.csv"
        ).read_bytes(),
        "source_receipt": json.loads(
            (PROSPECTIVE_FIXTURE / "synthetic-receipt.json").read_bytes()
        ),
    }

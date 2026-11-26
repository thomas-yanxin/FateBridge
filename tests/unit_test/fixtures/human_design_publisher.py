"""Complete publisher runs captured by the current native calculation."""

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import JsonValue

from validation.human_design_publisher import publisher_natal_checks


@dataclass(frozen=True, kw_only=True)
class PublisherCapture:
    runs: list[dict[str, JsonValue]]
    report: dict[str, JsonValue]


@pytest.fixture(scope="module")
def publisher_capture(tmp_path_factory: pytest.TempPathFactory) -> PublisherCapture:
    repository = Path(__file__).resolve().parents[3]
    capture_path = tmp_path_factory.mktemp("publisher-current") / "current-runs.json.gz"
    report = publisher_natal_checks(repository, capture=capture_path)
    runs = json.loads(gzip.decompress(capture_path.read_bytes()))
    return PublisherCapture(runs=runs, report=report)

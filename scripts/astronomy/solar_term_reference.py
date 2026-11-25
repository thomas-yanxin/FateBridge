"""Read the self-contained independent TT reference; no candidate imports."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

REFERENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests/data/solar_tt_de440_v1/reference.json.gz"
)
REFERENCE_SHA256 = "c549025496d0269cdd65532e4a2238f5c08a6aa4ab8376d379e2e33efd49c813"


class _FrozenReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class SolarTermRoot(_FrozenReference):
    year: int
    index: Annotated[int, Field(ge=0, le=23)]
    name: str
    jd_tt: float
    bracket_tt: tuple[float, float]


class SolarTermSource(_FrozenReference):
    kernel_url: str
    checksum_url: str
    kernel_md5: Literal["c9d581bfd84209dbeee8b1583939b148"]
    kernel_sha256: Literal[
        "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
    ]
    software_versions: dict[str, str]
    module_sha256: dict[str, str]
    producer_source: str
    producer_sha256: str
    method: str
    documentation_url: str
    bracket_policy: str
    maximum_bracket_seconds: float


class SolarTermReference(_FrozenReference):
    schema_id: Literal["solar_tt_de440_skyfield153_v1"] = Field(alias="schema")
    source: SolarTermSource
    first_year: Literal[1699]
    last_year: Literal[2301]
    public_packaged_input_years: tuple[int, int]
    adjacent_context_guard_years: tuple[int, int]
    production_imports: tuple[str, ...]
    scope: str
    rows: tuple[SolarTermRoot, ...]


def load_solar_term_reference(path: Path = REFERENCE_PATH) -> SolarTermReference:
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Independent solar TT reference identity changed")
    else:
        pass
    reference = SolarTermReference.model_validate_json(
        gzip.decompress(packed), strict=True
    )
    if reference.production_imports:
        raise ValueError("Independent solar TT reference imported the candidate")
    else:
        pass
    producer = reference.source.producer_source.encode("utf-8")
    if hashlib.sha256(producer).hexdigest() != reference.source.producer_sha256:
        raise ValueError("Independent solar TT producer source identity changed")
    else:
        pass
    expected = tuple(
        (year, index)
        for year in range(reference.first_year, reference.last_year + 1)
        for index in range(24)
    )
    if tuple((row.year, row.index) for row in reference.rows) != expected:
        raise ValueError("Every independent solar TT year needs all24 ordered terms")
    else:
        pass
    for row in reference.rows:
        low, high = row.bracket_tt
        if not low <= row.jd_tt <= high or (high - low) * 86400 > 0.001:
            raise ValueError("Independent solar TT root left its original bracket")
        else:
            pass
    if any(a.jd_tt >= b.jd_tt for a, b in zip(reference.rows, reference.rows[1:])):
        raise ValueError("Independent solar TT roots must remain strictly ordered")
    else:
        pass
    return reference

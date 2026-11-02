"""Projection-safe same-board heaven/earth rotation evidence."""

from typing import List, Optional

from .output_base import PartialOutput


class TaiyiShijiRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source: Optional[str] = None
    corroboration: Optional[str] = None
    source_manifest_sha256: Optional[str] = None


class TaiyiShijiPair(PartialOutput):
    step: Optional[int] = None
    heaven_spirit: Optional[str] = None
    earth_spirit: Optional[str] = None


class TaiyiShijiDerivation(PartialOutput):
    ruleset: Optional[TaiyiShijiRuleset] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    scope: Optional[str] = None
    wenchang: Optional[str] = None
    jishen: Optional[str] = None
    earth_anchor: Optional[str] = None
    direction: Optional[str] = None
    step_count: Optional[int] = None
    pairs: Optional[List[TaiyiShijiPair]] = None
    derived_shiji: Optional[str] = None
    wenchang_path: Optional[str] = None
    jishen_path: Optional[str] = None
    actual_path: Optional[str] = None
    actual_shiji: Optional[str] = None
    matches_actual: Optional[bool] = None

"""Projection-safe same-board heaven/earth rotation evidence."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiShijiRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    corroboration: str | None = None


class TaiyiShijiPair(PartialOutput):
    step: int | None = None
    heaven_spirit: str | None = None
    earth_spirit: str | None = None


class TaiyiYinShijiVariant(PartialOutput):
    ju: int | None = None
    profile: str | None = None
    shiji: str | None = None
    shiji_literal: str | None = None
    guest_count: int | None = None
    source: str | None = None


class TaiyiShijiDerivation(PartialOutput):
    ruleset: TaiyiShijiRuleset | None = None
    shiji_profile: str | None = None
    requested_shiji_profile: str | None = None
    selected_source: str | None = None
    guest_count_basis: str | None = None
    status: str | None = None
    reason: str | None = None
    scope: str | None = None
    wenchang: str | None = None
    jishen: str | None = None
    earth_anchor: str | None = None
    direction: str | None = None
    step_count: int | None = None
    pairs: list[TaiyiShijiPair] | None = None
    derived_shiji: str | None = None
    wenchang_path: str | None = None
    jishen_path: str | None = None
    actual_path: str | None = None
    actual_shiji: str | None = None
    matches_actual: bool | None = None
    yin_37_43_44_variants: list[TaiyiYinShijiVariant] | None = None

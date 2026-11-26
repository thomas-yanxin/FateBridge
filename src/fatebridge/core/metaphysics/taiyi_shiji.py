"""Compatibility facade for taiyi.core shiji helpers."""

from fatebridge.core.metaphysics.taiyi.core import (
    DEFAULT_SHIJI_PROFILE,
    SHIJI_PROFILES,
    TaiyiShijiProfile,
    resolve_shiji_variant,
    rotate_shiji,
    shiji_derivation,
    shiji_derivation_text,
)

__all__ = [
    "DEFAULT_SHIJI_PROFILE",
    "SHIJI_PROFILES",
    "TaiyiShijiProfile",
    "resolve_shiji_variant",
    "rotate_shiji",
    "shiji_derivation",
    "shiji_derivation_text",
]

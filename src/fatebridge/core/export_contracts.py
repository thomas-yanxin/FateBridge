"""Export settings and technique registry construction."""

from collections.abc import Mapping
from typing import TypedDict

from pydantic import JsonValue

from fatebridge.core.export_presets import (
    AI_EXPORT_FORBIDDEN_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
    AI_EXPORT_TECHNIQUES,
    JIEQI_SETTING_PRESETS,
)

__all__ = [
    "AI_EXPORT_SETTINGS_VERSION",
    "AI_EXPORT_TECHNIQUES",
    "ExportRegistry",
    "NormalizedSettings",
    "TechniqueInfo",
    "build_export_registry",
    "get_technique_info",
    "normalize_astro_meaning_setting",
    "normalize_planet_info_setting",
    "normalize_section_title",
    "unique_list",
]


AI_EXPORT_SETTINGS_KEY = "fatebridge.ai.export.settings.v1"
AI_EXPORT_SETTINGS_VERSION = 6
MODULE_SNAPSHOT_PREFIX = "fatebridge.ai.snapshot.module.v1."
AI_EXPORT_PLANET_INFO_DEFAULT = {"showHouse": 1, "showRuler": 1}
AI_EXPORT_ASTRO_MEANING_DEFAULT = {"enabled": 0}

AI_EXPORT_PLANET_INFO_TECHNIQUES = {
    "astrochart",
    "indiachart",
    "astrochart_like",
    "relative",
    "primarydirect",
    "primarydirchart",
    "zodialrelease",
    "firdaria",
    "profection",
    "solararc",
    "solarreturn",
    "lunarreturn",
    "transit",
    "givenyear",
    "decennials",
    "jieqi",
    "jieqi_meta",
    "jieqi_chunfen",
    "jieqi_xiazhi",
    "jieqi_qiufen",
    "jieqi_dongzhi",
    "sanshiunited",
    "guolao",
    "germany",
}

AI_EXPORT_ASTRO_MEANING_TECHNIQUES = {
    *AI_EXPORT_PLANET_INFO_TECHNIQUES,
    "otherbu",
    "qimen",
    "liureng",
}

AI_EXPORT_HOVER_MEANING_TECHNIQUES = {"qimen", "liureng", "sanshiunited"}


class TechniqueSettingsTemplate(TypedDict):
    sections: list[str]
    planetInfo: dict[str, int] | None
    astroMeaning: dict[str, int] | None


class TechniqueInfo(TypedDict):
    key: str
    label: str
    preset_sections: list[str]
    forbidden_sections: list[str]
    supports_planet_info: bool
    planet_info_default: dict[str, int] | None
    supports_astro_meaning: bool
    supports_hover_meaning: bool
    astro_meaning_default: dict[str, int] | None
    astro_meaning_title: str
    astro_meaning_checkbox: str
    settings_template: TechniqueSettingsTemplate


class NormalizedSettings(TypedDict):
    version: int
    sections: dict[str, list[str]]
    planetInfo: dict[str, dict[str, int]]
    astroMeaning: dict[str, dict[str, int]]


class ExportRegistry(TypedDict):
    source_of_truth: str
    settings_key: str
    settings_version: int
    module_snapshot_prefix: str
    jieqi_split_keys: list[str]
    planet_info_default: dict[str, int]
    astro_meaning_default: dict[str, int]
    default_normalized_settings: NormalizedSettings
    techniques: list[TechniqueInfo]
    selected_technique: TechniqueInfo | None


def normalize_planet_info_setting(
    raw: Mapping[str, JsonValue] | None,
) -> dict[str, int]:
    value = raw or {}
    return {
        "showHouse": (1 if value.get("showHouse") in {1, True} else 0),
        "showRuler": (1 if value.get("showRuler") in {1, True} else 0),
    }


def normalize_astro_meaning_setting(
    raw: Mapping[str, JsonValue] | None,
) -> dict[str, int]:
    value = raw or {}
    return {"enabled": 1 if value.get("enabled") in {1, True} else 0}


def normalize_section_title(title: str | None) -> str:
    text = f"{title or ''}".strip()
    if not text:
        return ""
    else:
        pass
    if text.startswith("基于") and text.endswith("推运"):
        return "基于X点推运"
    else:
        pass
    if text.startswith("基于") and text.endswith("起运"):
        return "基于X起运"
    else:
        pass
    return text


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = f"{item or ''}".strip()
        if value and value not in seen:
            seen.add(value)
            output.append(value)
        else:
            pass
    return output


def get_meaning_setting_meta(key: str) -> dict[str, str]:
    if key in AI_EXPORT_HOVER_MEANING_TECHNIQUES:
        return {
            "title": "悬浮注释（仅AI导出）：",
            "checkbox": "在对应分段输出六壬/遁甲/占星悬浮注释",
        }
    else:
        pass
    if key in AI_EXPORT_ASTRO_MEANING_TECHNIQUES:
        return {
            "title": "占星注释（仅AI导出）：",
            "checkbox": "在对应分段输出星/宫/座/相/希腊点释义",
        }
    else:
        pass
    return {"title": "", "checkbox": ""}


def get_technique_info(key: str) -> TechniqueInfo | None:
    base = next((item for item in AI_EXPORT_TECHNIQUES if item["key"] == key), None)
    if base is None:
        return None
    else:
        pass
    meaning_meta = get_meaning_setting_meta(key)
    has_planet_info = key in AI_EXPORT_PLANET_INFO_TECHNIQUES
    has_astro_meaning = key in AI_EXPORT_ASTRO_MEANING_TECHNIQUES
    has_hover_meaning = key in AI_EXPORT_HOVER_MEANING_TECHNIQUES
    return {
        "key": base["key"],
        "label": base["label"],
        "preset_sections": AI_EXPORT_PRESET_SECTIONS.get(key, []).copy(),
        "forbidden_sections": AI_EXPORT_FORBIDDEN_SECTIONS.get(key, []).copy(),
        "supports_planet_info": has_planet_info,
        "planet_info_default": (
            AI_EXPORT_PLANET_INFO_DEFAULT.copy() if has_planet_info else None
        ),
        "supports_astro_meaning": has_astro_meaning,
        "supports_hover_meaning": has_hover_meaning,
        "astro_meaning_default": (
            AI_EXPORT_ASTRO_MEANING_DEFAULT.copy()
            if (has_astro_meaning or has_hover_meaning)
            else None
        ),
        "astro_meaning_title": meaning_meta["title"],
        "astro_meaning_checkbox": meaning_meta["checkbox"],
        "settings_template": {
            "sections": AI_EXPORT_PRESET_SECTIONS.get(key, []).copy(),
            "planetInfo": (
                AI_EXPORT_PLANET_INFO_DEFAULT.copy() if has_planet_info else None
            ),
            "astroMeaning": (
                AI_EXPORT_ASTRO_MEANING_DEFAULT.copy()
                if (has_astro_meaning or has_hover_meaning)
                else None
            ),
        },
    }


def build_export_registry(*, technique: str | None = None) -> ExportRegistry:
    techniques: list[TechniqueInfo] = []
    for technique_label in AI_EXPORT_TECHNIQUES:
        technique_info = get_technique_info(technique_label["key"])
        assert technique_info is not None
        techniques.append(technique_info)
    selected = get_technique_info(technique) if technique else None
    return {
        "source_of_truth": "FateBridge local export registry",
        "settings_key": AI_EXPORT_SETTINGS_KEY,
        "settings_version": AI_EXPORT_SETTINGS_VERSION,
        "module_snapshot_prefix": MODULE_SNAPSHOT_PREFIX,
        "jieqi_split_keys": list(JIEQI_SETTING_PRESETS.keys()),
        "planet_info_default": AI_EXPORT_PLANET_INFO_DEFAULT.copy(),
        "astro_meaning_default": AI_EXPORT_ASTRO_MEANING_DEFAULT.copy(),
        "default_normalized_settings": {
            "version": AI_EXPORT_SETTINGS_VERSION,
            "sections": {},
            "planetInfo": {},
            "astroMeaning": {},
        },
        "techniques": techniques,
        "selected_technique": selected,
    }

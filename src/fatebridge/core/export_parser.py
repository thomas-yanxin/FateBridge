"""Parse titled snapshot blocks and apply export section selections."""

from collections.abc import Iterable, Mapping
from typing import TypedDict

from pydantic import JsonValue

from fatebridge.core.export_contracts import (
    AI_EXPORT_SETTINGS_VERSION,
    NormalizedSettings,
    TechniqueInfo,
    get_technique_info,
    normalize_astro_meaning_setting,
    normalize_planet_info_setting,
    normalize_section_title,
    unique_list,
)


class ContentSection(TypedDict):
    raw_title: str
    title: str
    content: str


class SelectedSection(ContentSection):
    index: int
    included: bool


class ParsedExport(TypedDict):
    technique: TechniqueInfo
    settings_used: NormalizedSettings
    section_titles_detected: list[str]
    selected_sections: list[str]
    unknown_detected_sections: list[str]
    missing_selected_sections: list[str]
    sections: list[SelectedSection]
    export_text: str


def parse_section_title_line(line: str | None) -> str:
    text = f"{line or ''}".strip()
    if not text:
        return ""
    else:
        pass
    if text.startswith("[") and text.endswith("]") and len(text) > 2:
        return normalize_section_title(text[1:-1])
    else:
        pass
    if text.startswith("【") and text.endswith("】") and len(text) > 2:
        return normalize_section_title(text[1:-1])
    else:
        pass
    return ""


def split_content_sections(content: str) -> list[ContentSection]:
    lines = f"{content or ''}".splitlines()
    sections: list[ContentSection] = []
    current_title = ""
    current_lines: list[str] = []

    def push_current() -> None:
        nonlocal current_title, current_lines
        if not current_title and not "".join(current_lines).strip():
            current_lines = []
            return
        else:
            pass
        sections.append(
            {
                "raw_title": current_title,
                "title": current_title,
                "content": "\n".join(current_lines).strip(),
            }
        )
        current_title = ""
        current_lines = []

    for line in lines:
        raw_title = parse_section_title_line(line)
        if raw_title:
            if current_lines:
                push_current()
            else:
                pass
            current_title = raw_title
            current_lines = [line]
            continue
        else:
            pass
        current_lines.append(line)

    if current_lines:
        push_current()
    else:
        pass
    return sections


def render_sections_to_text(section_contents: Iterable[str]) -> str:
    return "\n\n".join(
        content for content in section_contents if content.strip()
    ).strip()


def parse_export_content(
    *,
    technique: str,
    content: str,
    selected_sections: list[str] | None = None,
    planet_info: Mapping[str, JsonValue] | None = None,
    astro_meaning: Mapping[str, JsonValue] | None = None,
) -> ParsedExport:
    technique_info = get_technique_info(technique)
    if technique_info is None:
        raise ValueError(f"Unknown AI export technique: {technique}")
    else:
        pass

    raw_text = f"{content or ''}".strip()
    sections = split_content_sections(raw_text)
    detected_titles = unique_list(
        [section["title"] for section in sections if section["title"]]
    )

    forbidden = {
        normalize_section_title(title) for title in technique_info["forbidden_sections"]
    }
    preset_titles = {
        normalize_section_title(title) for title in technique_info["preset_sections"]
    }
    requested = (
        selected_sections[:]
        if selected_sections
        else technique_info["preset_sections"][:]
    )
    normalized_sections = [normalize_section_title(item) for item in requested]
    selected_normalized = unique_list(
        [
            item
            for item in normalized_sections
            if item and normalize_section_title(item) not in forbidden
        ]
    )
    wanted = {normalize_section_title(item) for item in selected_normalized}

    filtered_sections: list[SelectedSection] = []
    for index, section in enumerate(sections, start=1):
        normalized_title = normalize_section_title(section["title"])
        should_include_section = (
            not selected_sections
            if not normalized_title
            else normalized_title in wanted
        )
        if normalized_title and normalized_title in forbidden:
            should_include_section = False
        else:
            pass
        filtered_sections.append(
            {
                "index": index,
                "raw_title": section["raw_title"],
                "title": section["title"],
                "included": should_include_section,
                "content": section["content"],
            }
        )

    export_text = render_sections_to_text(
        section["content"] for section in filtered_sections if section["included"]
    )
    # note (selection): Only implicit selection may fall back to custom sections.
    if not selected_sections and not export_text:
        export_text = render_sections_to_text(
            section["content"]
            for section in filtered_sections
            if normalize_section_title(section["title"]) not in forbidden
        )
    else:
        pass

    normalized_detected = {normalize_section_title(title) for title in detected_titles}
    unknown_detected = [
        title
        for title in detected_titles
        if normalize_section_title(title) not in preset_titles
    ]
    missing_selected = [
        title
        for title in selected_normalized
        if normalize_section_title(title) not in normalized_detected
    ]
    settings_used: NormalizedSettings = {
        "version": AI_EXPORT_SETTINGS_VERSION,
        "sections": {technique: selected_normalized},
        "planetInfo": {},
        "astroMeaning": {},
    }
    if technique_info["supports_planet_info"]:
        settings_used["planetInfo"][technique] = normalize_planet_info_setting(
            planet_info
        )
    else:
        pass
    if (
        technique_info["supports_astro_meaning"]
        or technique_info["supports_hover_meaning"]
    ):
        settings_used["astroMeaning"][technique] = normalize_astro_meaning_setting(
            astro_meaning
        )
    else:
        pass

    return {
        "technique": technique_info,
        "settings_used": settings_used,
        "section_titles_detected": detected_titles,
        "selected_sections": selected_normalized,
        "unknown_detected_sections": unknown_detected,
        "missing_selected_sections": missing_selected,
        "sections": filtered_sections,
        "export_text": export_text,
    }

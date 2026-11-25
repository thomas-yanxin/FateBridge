"""Public snapshot formatting and export contracts."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_knowledge import (
    AstroMeaningSetting,
    ExportTechnique,
    PlanetInfoSetting,
)


class NormalizedExportSettings(PartialOutput):
    version: int | None = None
    sections: dict[str, list[str]] | None = None
    planetInfo: dict[str, PlanetInfoSetting] | None = None
    astroMeaning: dict[str, AstroMeaningSetting] | None = None


class ExportSection(PartialOutput):
    index: int | None = None
    raw_title: str | None = None
    title: str | None = None
    content: str | None = None
    included: bool | None = None


class SnapshotExport(PartialOutput):
    technique: ExportTechnique | None = None
    settings_used: NormalizedExportSettings | None = None
    selected_sections: list[str] | None = None
    section_titles_detected: list[str] | None = None
    unknown_detected_sections: list[str] | None = None
    missing_selected_sections: list[str] | None = None
    sections: list[ExportSection] | None = None
    export_text: str | None = None

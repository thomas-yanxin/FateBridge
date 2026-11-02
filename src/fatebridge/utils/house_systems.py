"""Canonical house-system selection and aliases, without numerical geometry."""

import re
from typing import Dict, Optional, Tuple, TypedDict
from unicodedata import normalize

TWELVE_HOUSE_SYSTEM_NOTE = " Explicit values must be supported letters/names or integer codes0..8; unknown, blank, boolean and floating-point selections are rejected without substitution. Gauquelin (G) has36 clockwise sectors and is unavailable here."
INVALID_HOUSE_SYSTEM_MESSAGE = (
    "House system must be a supported letter, name, or integer code0..8."
)
INVALID_HOUSE_CODE_MESSAGE = (
    "hsys must be an integer code0..8; boolean and floating-point values are invalid."
)
OFFLINE_HOUSE_CODE_NOTE = " Explicit values must be integer codes0..8; boolean, floating-point, blank and out-of-range values are rejected."
GAUQUELIN_UNSUPPORTED_MESSAGE = "Gauquelin (G) uses 36 clockwise sectors and is unavailable in the twelve-house interface."
_GAUQUELIN_IDENTIFIERS = frozenset(
    {
        "g",
        "gauquelin",
        "gauquelinsector",
        "gauquelinsectors",
        "gauquelin分区",
        "高奎林",
        "高奎林分区",
        "高奎林宫制",
    }
)


class InvalidHouseSystemError(ValueError):
    """An explicit unknown selection cannot be replaced by a default chart."""


class InvalidHouseCodeError(ValueError):
    """Invalid numeric code, distinct from a missing optional override."""


class UnsupportedGauquelinError(InvalidHouseSystemError):
    """A known 36-sector request must never become an unrelated 12-house chart."""


def reject_gauquelin_house_system(value: object) -> None:
    """Reject known Gauquelin names without altering other legacy aliases."""
    if not isinstance(value, str):
        return
    token = "".join(normalize("NFKC", value).casefold().split())
    token = token.replace("_", "").replace("-", "")
    if token in _GAUQUELIN_IDENTIFIERS:
        raise UnsupportedGauquelinError(GAUQUELIN_UNSUPPORTED_MESSAGE)


# Swiss Ephemeris 宫位系统代码 ↔ 常见英文/中文别名
# Keys normalized via casefold + strip for lookup. Values are the
# single-letter codes accepted by swisseph / kerykeion.
_HOUSE_SYSTEM_ALIASES: Dict[str, str] = {
    # Placidus (default)
    "placidus": "P",
    "placidian": "P",
    "普拉西德": "P",
    "普拉西迪斯": "P",
    # Koch
    "koch": "K",
    "koh": "K",
    "柯赫": "K",
    "科赫": "K",
    # Equal house (A and E both map to Equal from Ascendant in swisseph)
    "equal": "A",
    "equalhouse": "A",
    "equal-house": "A",
    "equalasc": "A",
    "equal sign": "A",
    "等宫": "A",
    "等分制": "A",
    # Whole sign
    "whole": "W",
    "wholesign": "W",
    "whole-sign": "W",
    "whole_signs": "W",
    "whole signs": "W",
    "整宫": "W",
    "整宫制": "W",
    # Regiomontanus
    "regiomontanus": "R",
    "regio": "R",
    "雷乔蒙塔努斯": "R",
    # Campanus
    "campanus": "C",
    "坎帕努斯": "C",
    # Porphyry / Porphyrius
    "porphyry": "O",
    "porphyrius": "O",
    "波菲利": "O",
    # Alcabitius
    "alcabitus": "B",
    "alcabitius": "B",
    "alchabitius": "B",
    "alchabitus": "B",
    "阿卡比特斯": "B",
    # Morinus
    "morinus": "M",
    "莫里努斯": "M",
    # Topocentric / Polich-Page
    "topocentric": "T",
    "polich": "T",
    "polichpage": "T",
    "polich-page": "T",
    "polich page": "T",
    # Horizontal / Azimuthal
    "horizontal": "H",
    "azimuthal": "H",
    # Axial rotation / Meridian
    "axial": "X",
    "meridian": "X",
    "axial rotation": "X",
    # Vehlow Equal
    "vehlow": "V",
    "vehlowequal": "V",
    "vehlow equal": "V",
    # Equal anchored on the MC (10th cusp = MC; the core chart's equal_mc / code 8)
    "equalmc": "D",
    "equalmidheaven": "D",
    "天顶为第10宫宫头的等宫制": "D",
    # Historical mislabel retained only as an input alias.
    "天顶为10宫中点等宫制": "D",
    # Sripati (core chart code 7) — was missing, so "sripati" fell back to P
    "sripati": "S",
    # APC / Krusinski
    "apc": "Y",
    "krusinski": "U",
}

# Integer house-system codes (the ``hsys`` convention used by the core/relative
# chart family) mapped to the Swiss Ephemeris letters the western family uses.
# Mirrors RELATIVE_HOUSE_SYSTEM_SPECS in core/astrology.py so a single integer
# code means the same system on every surface.
_HOUSE_SYSTEM_CODE_TO_LETTER: Dict[int, str] = {
    0: "W",  # whole_sign
    1: "B",  # Alcabitus
    2: "R",  # Regiomontanus
    3: "P",  # Placidus
    4: "K",  # Koch
    5: "V",  # Vehlow Equal
    6: "T",  # Polich Page / Topocentric
    7: "S",  # Sripati
    8: "D",  # equal_mc
}

# Swiss Ephemeris letter -> (integer code or None, key, Chinese label). The
# label/key for the 0..8 codes mirror RELATIVE_HOUSE_SYSTEM_SPECS so the western
# tools report a house system the same way the core/relative charts do. Letters
# without a 0..8 code (Campanus, Porphyry, ...) still get a readable key+label
# with code=None.
_HOUSE_SYSTEM_LETTER_INFO: Dict[str, Tuple[Optional[int], str, str]] = {
    "W": (0, "whole_sign", "整宫制"),
    "B": (1, "alcabitus", "Alcabitus"),
    "R": (2, "regiomontanus", "Regiomontanus"),
    "P": (3, "placidus", "Placidus"),
    "K": (4, "koch", "Koch"),
    "V": (5, "vehlow_equal", "Vehlow Equal"),
    "T": (6, "polich_page", "Polich Page"),
    "S": (7, "sripati", "Sripati"),
    "D": (8, "equal_mc", "天顶为第10宫宫头的等宫制"),
    "A": (None, "equal", "等宫制（上升起点）"),
    "C": (None, "campanus", "Campanus"),
    "O": (None, "porphyry", "Porphyry"),
    "M": (None, "morinus", "Morinus"),
    "H": (None, "horizontal", "Horizontal"),
    "X": (None, "meridian", "Meridian"),
    "Y": (None, "apc", "APC"),
    "U": (None, "krusinski", "Krusinski"),
    "F": (None, "carter_poli_equatorial", "Carter poli-equatorial"),
    "I": (None, "sunshine", "Sunshine"),
    "i": (None, "sunshine_alternative", "Sunshine/alt."),
    "L": (None, "pullen_sd", "Pullen SD"),
    "N": (None, "equal_aries", "Equal/1=Aries"),
    "Q": (None, "pullen_sr", "Pullen SR"),
}


class HouseSystemFields(TypedDict):
    house_system: str
    house_system_code: Optional[int]
    house_system_label_zh: str


def house_system_fields(house_system: object, default: str = "P") -> HouseSystemFields:
    """Describe a house system the same way on every surface.

    Returns a dict with the resolved Swiss Ephemeris ``house_system`` letter plus
    a numeric ``house_system_code`` (0..8, or ``None`` for letters outside that
    set) and a Chinese ``house_system_label_zh`` — mirroring the core/relative
    chart ``chart_profile`` keys so an agent reading any western result knows
    exactly which system produced it, regardless of how it was requested
    (integer code, SE letter, or key).
    """
    letter = normalize_house_system(house_system, default=default)
    code, _key, label_zh = _HOUSE_SYSTEM_LETTER_INFO.get(letter, (None, letter, letter))
    return {
        "house_system": letter,
        "house_system_code": code,
        "house_system_label_zh": label_zh,
    }


# Valid single-letter codes per kerykeion.schemas.kr_literals.HousesSystemIdentifier
_VALID_HOUSE_SYSTEM_CODES = frozenset(
    {
        "A",
        "B",
        "C",
        "D",
        "F",
        "H",
        "I",
        "i",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
        "T",
        "U",
        "V",
        "W",
        "X",
        "Y",
    }
)


def _alias_key(value: str) -> str:
    return (
        "".join(normalize("NFKC", value).casefold().split())
        .replace("_", "")
        .replace("-", "")
    )


def _build_alias_index() -> Dict[str, str]:
    entries = list(_HOUSE_SYSTEM_ALIASES.items())
    for code, (_, key, label) in _HOUSE_SYSTEM_LETTER_INFO.items():
        entries.extend([(key, code), (label, code)])
    result: Dict[str, str] = {}
    for name, code in entries:
        token = _alias_key(name)
        if token in result and result[token] != code:
            raise RuntimeError("Conflicting house-system alias definitions")
        result[token] = code
    return result


_NORMALIZED_HOUSE_ALIASES = _build_alias_index()


def parse_house_code(value: object) -> int:
    """Strict0..8 selector; digit strings retain existing transport compatibility."""
    if type(value) is int:
        code = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        try:
            code = int(value.strip())
        except ValueError:
            raise InvalidHouseCodeError(INVALID_HOUSE_CODE_MESSAGE) from None
    else:
        raise InvalidHouseCodeError(INVALID_HOUSE_CODE_MESSAGE)
    if code not in _HOUSE_SYSTEM_CODE_TO_LETTER:
        raise InvalidHouseCodeError(INVALID_HOUSE_CODE_MESSAGE)
    return code


def _resolve_house_identifier(value: object) -> str:
    if type(value) is int:
        try:
            return _HOUSE_SYSTEM_CODE_TO_LETTER[parse_house_code(value)]
        except InvalidHouseCodeError:
            raise InvalidHouseSystemError(INVALID_HOUSE_SYSTEM_MESSAGE) from None
    if not isinstance(value, str):
        raise InvalidHouseSystemError(INVALID_HOUSE_SYSTEM_MESSAGE)
    token = normalize("NFKC", value).strip()
    reject_gauquelin_house_system(token)
    # Swiss E and A share Equal from Ascendant; the subject binding exposes A.
    if token in {"E", "e"}:
        return "A"
    # Preserve the backend's distinct Sunshine I and alternative i definitions.
    if token in _VALID_HOUSE_SYSTEM_CODES:
        return token
    if len(token) == 1 and token.upper() in _VALID_HOUSE_SYSTEM_CODES:
        return token.upper()
    if re.fullmatch(r"[+-]?[0-9]+", token):
        try:
            return _HOUSE_SYSTEM_CODE_TO_LETTER[parse_house_code(token)]
        except InvalidHouseCodeError:
            raise InvalidHouseSystemError(INVALID_HOUSE_SYSTEM_MESSAGE) from None
    resolved = _NORMALIZED_HOUSE_ALIASES.get(_alias_key(token))
    if resolved is None:
        raise InvalidHouseSystemError(INVALID_HOUSE_SYSTEM_MESSAGE)
    return resolved


def normalize_house_system(house_system: object, default: str = "P") -> str:
    """Resolve a known identifier; only a missing override selects the default.

    An explicit unknown/blank value, bool or float never selects another chart.
    Defaults are themselves validated; no lenient-fallback escape hatch exists.
    """
    resolved_default = _resolve_house_identifier(default)
    return (
        resolved_default
        if house_system is None
        else _resolve_house_identifier(house_system)
    )

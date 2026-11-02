"""Terms reported in Robbins' Tetrabiblos I.20-21, not a dignity score.

The printed Greek/English tables (pp. 96-97, 106-107) are the selected
edition. In particular Libra's last Ptolemaic term is Mars, not the second
Saturn in the LacusCurtius HTML transcription. Manuscript variants in the
printed apparatus are not silently merged into the selected main tables.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astrology_tables import EGYPTIAN_BOUNDS_BY_SIGN, SIGNS

SCAN_URL = (
    "https://commons.wikimedia.org/wiki/File:Loeb_435_-_Ptolemy_-_"
    "Tetrabiblos_by_Robbins_(1940).pdf"
)
TERM_POLICY = (
    "Robbins 1940 printed main tables pp.96-97,106-107 and I.21 Chaldaean "
    "sequence; degrees counted from 0; intervals [start,end); Chaldaean "
    "Saturn/Mercury order follows the explicitly computed chart sect; "
    "reported systems kept separate; no dignity points or event judgement inferred"
)
TRANSCRIPTION_NOTE = (
    "Robbins printed pp.106-107: Libra Ptolemaic terms end with Mars 6 degrees "
    "(24-30). LacusCurtius HTML repeats Saturn in that cell. The printed main "
    "table is selected; the edition's manuscript variants remain variants. "
    "Manual scan comparison is not an independent critical edition."
)

# Successive lengths, not cumulative endpoints. Egyptian lengths/order in
# astrology_tables match Robbins pp.96-97 and retain the eclectic layer's API.
_PTOLEMAIC_LENGTHS = (
    (("Jupiter", 6), ("Venus", 8), ("Mercury", 7), ("Mars", 5), ("Saturn", 4)),
    (("Venus", 8), ("Mercury", 7), ("Jupiter", 7), ("Saturn", 2), ("Mars", 6)),
    (("Mercury", 7), ("Jupiter", 6), ("Venus", 7), ("Mars", 6), ("Saturn", 4)),
    (("Mars", 6), ("Jupiter", 7), ("Mercury", 7), ("Venus", 7), ("Saturn", 3)),
    (("Jupiter", 6), ("Mercury", 7), ("Saturn", 6), ("Venus", 6), ("Mars", 5)),
    (("Mercury", 7), ("Venus", 6), ("Jupiter", 5), ("Saturn", 6), ("Mars", 6)),
    (("Saturn", 6), ("Venus", 5), ("Mercury", 5), ("Jupiter", 8), ("Mars", 6)),
    (("Mars", 6), ("Venus", 7), ("Jupiter", 8), ("Mercury", 6), ("Saturn", 3)),
    (("Jupiter", 8), ("Venus", 6), ("Mercury", 5), ("Saturn", 6), ("Mars", 5)),
    (("Venus", 6), ("Mercury", 6), ("Jupiter", 7), ("Saturn", 6), ("Mars", 5)),
    (("Saturn", 6), ("Mercury", 6), ("Venus", 8), ("Jupiter", 5), ("Mars", 5)),
    (("Venus", 8), ("Jupiter", 6), ("Mercury", 6), ("Mars", 5), ("Saturn", 5)),
)


def terms_at(longitude: float, chart_sect: str) -> dict[str, dict[str, Any]]:
    """Classify an unrounded tropical longitude in all three named systems.

    A degree exactly on a cumulative endpoint belongs to the following term;
    30 degrees belongs to the next sign. This half-open implementation policy
    maps the source's numbered degrees to continuous astronomical longitude.
    """
    if chart_sect not in {"day", "night"}:
        raise ValueError("Chaldaean terms require an explicit day or night condition")
    longitude = normalize_angle(longitude)
    index = int(longitude // 30)
    degree = longitude % 30
    pair = ("Saturn", "Mercury") if chart_sect == "day" else ("Mercury", "Saturn")
    groups = (("Jupiter",), ("Venus",), pair, ("Mars",))
    start_group = index % 4
    order = [p for i in range(4) for p in groups[(start_group + i) % 4]]
    chaldaean = tuple(zip(order, (8, 7, 6, 5, 4)))
    tables = {
        "egyptian": (
            [
                (p, int(end - start))
                for p, start, end in EGYPTIAN_BOUNDS_BY_SIGN[SIGNS[index]]
            ],
            "I.20; printed pp.96-97",
        ),
        "chaldaean": (chaldaean, "I.21; printed pp.98-101"),
        "ptolemaic": (_PTOLEMAIC_LENGTHS[index], "I.21; printed pp.106-107"),
    }
    result = {}
    for system, (segments, chapter) in tables.items():
        start = 0
        for lord, length in segments:
            end = start + length
            if start <= degree < end:
                result[system] = {
                    "lord": lord,
                    "start_degree": start,
                    "end_degree": end,
                    "chapter_ref": chapter,
                }
                break
            start = end
    return result

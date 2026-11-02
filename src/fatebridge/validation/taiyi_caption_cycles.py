"""Test a declared 60/72/Jiazi1 caption hypothesis, never repair the caption."""

from __future__ import annotations

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
GANZHI = tuple(STEMS[n % 10] + BRANCHES[n % 12] for n in range(60))


def caption_candidates(
    *,
    ji60: int | None = None,
    yuan72: int | None = None,
    ju: int | None = None,
    ganzhi: str | None = None,
) -> list[int]:
    """Return every state satisfying the supplied explicit coordinate clauses.

    The assumptions are one-based ji60/yuan72 and a shared Jiazi1 origin for
    the supplied day/hour token. The function does not certify those premises
    for every textual use of 紀, nor does it choose an alternative by fit.
    """
    if all(value is None for value in (ji60, yuan72, ju, ganzhi)):
        raise ValueError("At least one explicit caption constraint required")
    for value, limit in ((ji60, 6), (yuan72, 5), (ju, 72)):
        if value is not None and (type(value) is not int or not 1 <= value <= limit):
            raise ValueError(
                "Caption cycle coordinates must be explicit valid integers"
            )
    if ganzhi is not None and ganzhi not in GANZHI:
        raise ValueError("Caption requires a valid sexagenary token")
    return [
        n
        for n in range(1, 361)
        if (ji60 is None or (n - 1) // 60 + 1 == ji60)
        and (yuan72 is None or (n - 1) // 72 + 1 == yuan72)
        and (ju is None or (n - 1) % 72 + 1 == ju)
        and (ganzhi is None or GANZHI[(n - 1) % 60] == ganzhi)
    ]

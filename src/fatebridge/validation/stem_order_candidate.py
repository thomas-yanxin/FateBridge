"""Isolated month/hour-link hypothesis; never enabled by the production engine.

The selected 子平真诠 PDF48 explicitly discusses 年甲月癸日丙时戊.
This validates a source-local combination observation, not the binding amount,
transformation, whole-chart strength or the safety of numerical adoption.
"""

from typing import Collection, Mapping, Sequence

ORDER = ("year", "month", "day", "hour")


def extend_non_day_links(
    stems: Mapping[str, str],
    original: Sequence[tuple[str, str]],
    pairs: Collection[frozenset[str]],
) -> list[tuple[str, str]]:
    """Keep every original link, then add unique adjacent non-day links.

    Day-master links are retained for the original competition/review logic.
    No branch, root, birthday, force coefficient or named case is inferred.
    """
    result = list(original)
    names = [name for name in ORDER if name != "day" and name in stems]
    for left, right in zip(names, names[1:]):
        pair = (left, right)
        if frozenset((stems[left], stems[right])) in pairs and pair not in result:
            result.append(pair)
    return result

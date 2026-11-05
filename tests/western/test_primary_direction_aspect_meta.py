"""Characterization tests for primary_direction_aspect_meta.

This locks the exact (key, label) mapping so the O(n) linear-scan implementation
can be replaced by an O(1) dict lookup without behavior change. The function is
called thousands of times per primary-directions request, so the scan was pure
waste — but the output contract must stay byte-identical.
"""

from __future__ import annotations

import pytest

from fatebridge.core.predictive.primary_directions import primary_direction_aspect_meta


@pytest.mark.parametrize(
    "degree, expected",
    [
        (0, ("conjunction", "合相")),
        (60, ("sextile", "六合")),
        (90, ("square", "刑")),
        (120, ("trine", "拱")),
        (180, ("opposition", "冲")),
    ],
)
def test_known_aspect_degrees_map_to_their_meta(degree, expected):
    assert primary_direction_aspect_meta(degree) == expected


def test_unknown_aspect_degree_falls_back_to_generic_label():
    assert primary_direction_aspect_meta(45) == ("45deg", "45°")
    assert primary_direction_aspect_meta(150) == ("150deg", "150°")

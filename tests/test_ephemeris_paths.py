"""Search-root identity must agree with the native platform path grammar."""

import pytest

from fatebridge.core import ephemeris_paths


@pytest.mark.parametrize(
    "separator,search_path,expected",
    [
        (":", "first;second:third", ["first", "second", "third"]),
        (";", r"C:\ephe;D:\other", [r"C:\ephe", r"D:\other"]),
        (":", ";first::first", [".", "first", "first"]),
        (";", ";first;;first", [".", "first", "first"]),
        (":", "first::", ["first", "/"]),
        (";", "first;;", ["first", "\\"]),
        (":", "a;" * 21 + "last", ["a"] * 19 + ["a;a;last"]),
        (":", None, []),
        (";", "", []),
    ],
)
def test_search_order_and_platform_separators(
    separator, search_path, expected, monkeypatch
):
    monkeypatch.setattr(ephemeris_paths.os, "pathsep", separator)
    monkeypatch.setattr(ephemeris_paths.os, "sep", "\\" if separator == ";" else "/")
    assert [
        str(directory)
        for directory in ephemeris_paths.ephemeris_search_directories(search_path)
    ] == expected

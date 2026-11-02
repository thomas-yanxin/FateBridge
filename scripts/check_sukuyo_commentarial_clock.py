"""Check selected source bytes and quotations, never infer an ancient clock."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/fatebridge/data/sukuyo_commentarial_boundaries.json"
FIXTURE = ROOT / "tests/fixtures/sukuyo-commentarial-clock-primary.json"


def check_literal_days(source: dict[str, Any]) -> None:
    """Bind the executable controls to the actual selected quotation."""
    digits = "一二三四五六七八九"
    numerals = {value: index for index, value in enumerate(digits, 1)}
    numerals.update({"正": 1, "十": 10, "二十": 20, "三十": 30})
    numerals.update({"十" + digit: 10 + index for index, digit in enumerate(digits, 1)})
    numerals.update(
        {"二十" + digit: 20 + index for index, digit in enumerate(digits, 1)}
    )
    selected = next(row for row in source["sources"] if row["id"] == "T2216")
    quotation = selected["selected_quotations"][0]["literal"]
    parsed = [
        {"month": numerals[month], "day": numerals[day]}
        for month, day in re.findall(
            r"([正一二三四五六七八九十]+)月([一二三四五六七八九十]+)日", quotation
        )
    ]
    if parsed != source["monthly_pushya_reference"]["literal_days"]:
        raise ValueError("月日控制未绑定所选原引日号")


def source_lines(raw: bytes, kind: str) -> dict[str, str]:
    """Preserve visible text; do not complete glyphs or resolve apparatus."""
    if kind == "SAT_HTML":
        text = raw.decode("utf-8")
        markers = list(re.finditer(r"T2216_\.59\.(\d{4}[abc]\d{2}): </span>", text))
        return {
            match[1]: unescape(
                re.sub(
                    r"<[^>]*>",
                    "",
                    text[match.end() : markers[i + 1].start()],
                )
            )
            for i, match in enumerate(markers[:-1])
        }
    if kind != "CBETA_TEI":
        raise ValueError("未知来源格式")
    tree = ElementTree.fromstring(raw)
    ns = "{http://www.tei-c.org/ns/1.0}"
    body = tree.find(f".//{ns}body")
    if body is None:
        raise ValueError("缺少TEI正文")
    result: dict[str, str] = {}
    current: str | None = None

    def visit(node: ElementTree.Element) -> None:
        nonlocal current
        if node.tag == ns + "lb" and node.get("ed") == "T":
            current = node.attrib["n"]
            result.setdefault(current, "")
        if node.text and current is not None:
            result[current] += node.text
        for child in node:
            # Apparatus belongs to the back matter; retain only inline notes
            # if a source places a note inside its selected body passage.
            if child.tag != ns + "note" or child.get("place") == "inline":
                visit(child)
            if child.tail and current is not None:
                result[current] += child.tail

    visit(body)
    return result


def verify_primary(captures: dict[str, Path] | None = None) -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    source = json.loads(raw)
    expected = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != expected["source_bundle_sha256"]:
        raise ValueError("来源资料与事前记录指纹不一致")
    if source["monthly_pushya_reference"]["literal_days"] != expected["literal_days"]:
        raise ValueError("所引月日与读录不一致")
    check_literal_days(source)
    checked = []
    sources = {row["id"]: row for row in source["sources"]}
    for name, path in (captures or {}).items():
        if name not in sources:
            raise ValueError("未登记来源")
        data = path.read_bytes()
        row = sources[name]
        if hashlib.sha256(data).hexdigest() != row["capture_sha256"]:
            raise ValueError("原始来源字节指纹不一致")
        lines = source_lines(data, row["format"])
        for quote in row["selected_quotations"]:
            window = "".join(
                text
                for key, text in sorted(lines.items())
                if quote["first_line"] <= key <= quote["last_line"]
            )
            window = re.sub(r"\s+", "", window)
            if quote["literal"] not in window:
                raise ValueError(f"所选引文与来源行不一致：{quote['locator']}")
        checked.append(name)
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "literal_month_day_controls": len(expected["literal_days"]),
        "literal_controls_bound_to_selected_quotation": True,
        "actual_capture_bytes_rechecked": checked,
        "all_three_actual_captures_rechecked": set(checked) == set(sources),
        "independent_manuscript_collation": False,
        "historical_clock_mapping_established": False,
        "hinoo_half_mapping_established": False,
        "leap_short_month_priority_established": False,
        "calendar_algorithm_changed": False,
        "scope": "Selected publisher text and captured bytes only; not independent originals of works quoted by T2216.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[], metavar="ID=PATH")
    args = parser.parse_args()
    captures = {}
    for argument in args.capture:
        name, path = argument.split("=", 1)
        if name in captures:
            raise ValueError("重复来源")
        captures[name] = Path(path)
    print(json.dumps(verify_primary(captures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

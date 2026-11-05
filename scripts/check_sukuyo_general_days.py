"""Compare complete day classifications against pinned prose enumerations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))
from fatebridge.core.sukuyo_general_days import general_day_evidence


def _numbers(text: str) -> list[int]:
    digits = {word: number for number, word in enumerate("零一二三四五六七八九")}
    result = []
    # The lower conditional list has the printed punctuation 二十四、日.
    for word in re.findall(r"([一二三四五六七八九十]+)[、]?日", text):
        if "十" in word:
            first, last = word.split("十")
            result.append(digits.get(first, 1) * 10 + digits.get(last, 0))
        else:
            result.append(digits[word])
    return result


def _half_month_list(text: str, *, favorable: bool) -> list[int]:
    if favorable:
        white, black = text.split("每月白月", 1)[1].split("，黑月", 1)
    else:
        white, black = text.split("又白月", 1)[1].split("又黑月", 1)
    return sorted(_numbers(white) + [15 + day for day in _numbers(black)])


def verify_general_days(xml_path: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(
        (ROOT / "tests/data/sukuyo-general-day-lists-primary.json").read_bytes()
    )
    fragments = fixture["raw_selected_xml_paragraphs"]
    text = {
        identifier: "".join(ET.fromstring(raw).itertext()).replace("\n", "")
        for identifier, raw in fragments.items()
    }
    if xml_path is not None:
        raw = xml_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != fixture["source_xml_sha256"]:
            raise ValueError("General-day full source bytes changed")
        full = raw.decode()
        if any(fragment not in full for fragment in fragments.values()):
            raise ValueError("General-day paragraph missing from full source")
    expected = {
        "upper_prose": (
            _half_month_list(text["pT21p0393a0101"], favorable=True),
            _half_month_list(text["pT21p0393a0901"], favorable=False),
        ),
        "lower_prose": (
            sorted(_numbers(text["pT21p0394a0101"])),
            sorted(_numbers(text["pT21p0394a1101"])),
        ),
    }
    errors = []
    reference = general_day_evidence(1)["reference"]
    if reference["source_xml_sha256"] != fixture["source_xml_sha256"]:
        errors.append("source_xml_digest")
    for witness in reference["witnesses"]:
        name = witness["witness"]
        favorable, conditional = expected[name]
        if witness["favorable_lunar_days"] != favorable:
            errors.append([name, "favorable_list"])
        if witness["conditional_lunar_days"] != conditional:
            errors.append([name, "conditional_list"])
        for section in ("favorable_source_paragraphs", "conditional_source_paragraphs"):
            for paragraph in witness[section]:
                if paragraph["text"] != text[paragraph["xml_id"]]:
                    errors.append([name, paragraph["xml_id"], "source_text"])
        for row in witness["all_thirty_classifications"]:
            day = row["lunar_day"]
            assessment = (
                "favorable"
                if day in favorable
                else "conditional" if day in conditional else "unlisted"
            )
            if row["assessment"] != assessment:
                errors.append([name, day, "classification"])
    return {
        "format": "sukuyo_general_day_source_check_v1",
        "source_xml_sha256": fixture["source_xml_sha256"],
        "source_bundle_sha256": reference["source_bundle_sha256"],
        "selected_paragraphs_checked": len(fragments),
        "day_classifications_checked": 60,
        "full_xml_bytes_and_fragments_checked": xml_path is not None,
        "raw_source_enumerations_independently_parsed": True,
        "facsimile_or_full_classical_collation": False,
        "general_list_does_not_override_phase_or_activity_conditions": True,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_general_days(args.xml_path)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())

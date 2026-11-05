"""Check the complete captured month-duty texts without adopting their tables."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/bazi_month_duty_sources_v1"
DATA = ROOT / "src/fatebridge/data/bazi_month_duty_sources_v1.json"
MONTHS = "寅卯辰巳午未申酉戌亥子丑"
NUMBERS = dict(zip("一二三四五六七八九", range(1, 10)))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(text: str) -> int:
    if "十" not in text:
        return NUMBERS[text]
    before, after = text.split("十")
    return (NUMBERS[before] if before else 1) * 10 + (NUMBERS[after] if after else 0)


def transcribe(text: str, *, prose: bool) -> list[dict[str, Any]]:
    if prose:
        text = text.split("此十二支", 1)[0]
    pattern = r"(十二|十一|十|正|二|三|四|五|六|七|八|九)月"
    pattern += r"[，,\s]*建" if prose else r"[：:\s]*"
    starts = list(re.finditer(pattern + r"([寅卯辰巳已午未申酉戌亥子丑])", text))
    if len(starts) != 12:
        raise ValueError("All twelve literal month sections must be present")
    if [m[1] for m in starts] != [
        "正",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
    ]:
        raise ValueError("Literal month order changed")
    entries = re.compile(
        r"([甲乙丙丁戊己庚辛壬癸艮坤已][木火土金水]?)"
        r"[^甲乙丙丁戊己庚辛壬癸艮坤已一二三四五六七八九十]{0,12}"
        r"([一二三四五六七八九十]+)日"
    )
    result = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        claims = [
            {"source_name": m[1], "days": number(m[2])}
            for m in entries.finditer(text[match.end() : end])
        ]
        result.append(
            {"branch": MONTHS[index], "literal_branch": match[2], "claims": claims}
        )
    return result


def audit() -> dict[str, Any]:
    data = json.loads(DATA.read_text())
    paragraphs = json.loads((FIXTURE / "digital-paragraphs.json").read_text())
    if len(paragraphs) != 13:
        raise ValueError("Full captured chapter must retain all thirteen paragraphs")
    raw_router = json.loads((FIXTURE / "digital-router.json").read_text())
    html = (FIXTURE / "digital-source.html").read_text()
    marker = re.search(r"window\._ROUTER_DATA\s*=\s*", html)
    if (
        marker is None
        or json.JSONDecoder().raw_decode(html[marker.end() :])[0] != raw_router
    ):
        raise ValueError("Captured router data differs from its original HTML")
    router = raw_router["loaderData"]["__session/(lang$)/book/$"]
    rebuilt = [
        {
            "paragraph_id": p["paragraphId"],
            "chapter_order": p["chapterOrder"],
            "in_chapter_order": p["inChapterOrder"],
            "start_page_id": p["startPageId"],
            "end_page_id": p["endPageId"],
            "volume_version": p["volumeVersion"],
            "text": "".join(
                line["content"] for line in json.loads(p["content"])["lines"]
            ),
        }
        for p in router["paragraphList"]
    ]
    if rebuilt != paragraphs:
        raise ValueError(
            "Source paragraphs do not reconstruct from captured router data"
        )
    chapters = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("chapterId") == "1kf5v6o9by5o3" and "paragraphCount" in value:
                chapters.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(router["bookInfo"]["catalog"])
    if (
        len(chapters) != 1
        or chapters[0]["paragraphCount"] != len(paragraphs)
        or [p["in_chapter_order"] for p in paragraphs]
        != list(range(1, len(paragraphs) + 1))
    ):
        raise ValueError(
            "Captured chapter is incomplete against its own source catalog"
        )
    if (
        data["profiles"][0]["source_text"] != paragraphs[1]["text"]
        or data["profiles"][1]["source_text"]
        != "\n".join(p["text"] for p in paragraphs[2:12])
        or data["sanming_critique"]["source_text"] != paragraphs[12]["text"]
    ):
        raise ValueError("A whole source paragraph was changed or omitted")
    if data["sanming_critique"]["anchor"] not in paragraphs[12]["text"]:
        raise ValueError("Critique anchor differs from captured original")
    rows = []
    for index, profile in enumerate(data["profiles"]):
        for parsed in transcribe(profile["source_text"], prose=index == 0):
            supplied = profile["months"][parsed["branch"]]
            for claim in supplied["claims"]:
                first = claim["source_name"][0]
                expected_stem = first if first in "甲乙丙丁戊己庚辛壬癸" else None
                expected_status = (
                    "explicit_stem"
                    if expected_stem
                    else "unresolved_literal_soil_identity"
                )
                if (
                    claim["canonical_stem"] != expected_stem
                    or claim["identity_status"] != expected_status
                ):
                    raise ValueError("Literal stem identity was silently normalized")
            selected = [
                {k: r[k] for k in ("source_name", "days")} for r in supplied["claims"]
            ]
            if (
                parsed["claims"] != selected
                or parsed["literal_branch"] != supplied["literal_branch_glyph"]
            ):
                raise ValueError(
                    "Literal month transcription differs: "
                    + profile["id"]
                    + parsed["branch"]
                )
            rows.append(
                {
                    "profile": profile["id"],
                    **parsed,
                    "literal_duration_sum": sum(c["days"] for c in selected),
                    "all_transcribed_claims_match_captured_text": True,
                }
            )
    annual = data["annual_literal_claim"]
    for group in annual["groups"]:
        match = re.search(
            re.escape("、".join(group["source_names"]))
            + r"各([一二三四五六七八九十]+)日",
            paragraphs[1]["text"],
        )
        if match is None or number(match[1]) != group["each_days"]:
            raise ValueError("Annual literal duration differs from the captured text")
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_sha256": digest(DATA),
        "source_paragraphs": len(paragraphs),
        "source_month_rows": len(rows),
        "duration_claims": sum(len(r["claims"]) for r in rows),
        "rows": rows,
        "nominal_month_totals_not_thirty": [
            r for r in rows if r["literal_duration_sum"] != 30
        ],
        "annual_computed_literal_sum": sum(
            len(g["source_names"]) * g["each_days"] for g in annual["groups"]
        ),
        "annual_stated_sum": annual["stated_total_days"],
        "source_transcription_check_passed": True,
        "source_scan_collation_for_digital_text": "not_completed",
        "independent_expert_review": "pending",
        "duty_calendar_profile_adopted": False,
        "production_strength_policy_changed": False,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    sidecar = Path(str(output) + ".sha256")
    if output.exists() or sidecar.exists():
        raise SystemExit("Output exists; preserve first results")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    sidecar.write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "source_paragraphs",
                    "source_month_rows",
                    "duration_claims",
                    "annual_computed_literal_sum",
                    "annual_stated_sum",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

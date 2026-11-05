"""Verify a complete frozen scanned-witness transcription without fixing its sums."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.audit_bazi_month_duty_sources import number, transcribe

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/bazi_month_duty_scan_v1"
DATA = ROOT / "src/fatebridge/data/bazi_month_duty_scan_v1.json"
MONTHS = "寅卯辰巳午未申酉戌亥子丑"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_claims(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    profile: str,
    branch: str,
    pages: list[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retain witnessed differences; agreement is never a publication gate."""
    if len(previous) != len(current):
        raise ValueError("A paired claim count changed; a new alignment is required")
    durations, glyphs = [], []
    for rank, (old, claim) in enumerate(zip(previous, current, strict=True)):
        locator = dict(
            profile=profile, branch=branch, rank=rank, original_pdf_pages=pages
        )
        if claim["days"] != old["days"]:
            durations.append(
                dict(**locator, digital_days=old["days"], scanned_days=claim["days"])
            )
        if claim["source_name"] != old["source_name"]:
            glyphs.append(
                dict(
                    **locator,
                    digital=old["source_name"],
                    scanned_reading=claim["source_name"],
                    difference_kind=(
                        "yi_ji_scan_reading"
                        if old["source_name"].replace("已", "己")
                        == claim["source_name"]
                        else "other_source_reading_requires_review"
                    ),
                )
            )
    return durations, glyphs


def audit() -> dict[str, Any]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    source = data["source"]
    if digest(FIXTURE / "06066038.cn.pdf") != source["source_pdf_sha256"]:
        raise ValueError("Full original scanned PDF changed")
    extraction = json.loads(
        (FIXTURE / "extraction-manifest.json").read_text(encoding="utf-8")
    )
    if (
        extraction["source_sha256"] != source["source_pdf_sha256"]
        or digest(FIXTURE / "chapter66-74.pdf") != extraction["excerpt_sha256"]
    ):
        raise ValueError("Chapter excerpt binding changed")
    if [r["original_pdf_page"] for r in extraction["pages"]] != list(range(66, 75)):
        raise ValueError("Chapter or boundary page omitted")
    digital = json.loads(
        (ROOT / "src/fatebridge/data/bazi_month_duty_sources_v1.json").read_text()
    )
    rows = []
    glyph_differences = []
    duration_differences = []
    for index, profile in enumerate(data["profiles"]):
        if list(profile["months"]) != list(MONTHS):
            raise ValueError("All twelve source months and their order required")
        text = "\n".join(r["literal_quote"] for r in profile["months"].values())
        parsed = transcribe(text, prose=index == 0)
        for branch, literal in zip(MONTHS, parsed, strict=True):
            month = profile["months"][branch]
            claims = month["claims"]
            if literal["claims"] != [
                {"source_name": c["source_name"], "days": c["days"]} for c in claims
            ]:
                raise ValueError(
                    "Structured reading differs from its literal transcription"
                )
            if not month["original_pdf_pages"] or not set(
                month["original_pdf_pages"]
            ) <= set(range(66, 74)):
                raise ValueError("Reading lacks actual chapter page references")
            previous = digital["profiles"][index]["months"][branch]
            if len(claims) != len(previous["claims"]):
                raise ValueError("A digital claim disappeared from the comparison")
            durations, glyphs = compare_claims(
                previous["claims"],
                claims,
                profile=profile["id"],
                branch=branch,
                pages=month["original_pdf_pages"],
            )
            duration_differences.extend(durations)
            glyph_differences.extend(glyphs)
            for claim in claims:
                stem = claim["canonical_stem"]
                if stem is None:
                    if claim["source_name"] not in {"艮土", "坤土"}:
                        raise ValueError("Unclassified unknown stem")
                elif (
                    stem not in "甲乙丙丁戊己庚辛壬癸"
                    or stem != claim["source_name"][0]
                ):
                    raise ValueError("Canonical stem does not match explicit reading")
            total = sum(c["days"] for c in claims)
            rows.append(
                dict(
                    profile=profile["id"],
                    branch=branch,
                    duration_claims=len(claims),
                    literal_quote=month["literal_quote"],
                    original_pdf_pages=month["original_pdf_pages"],
                    literal_duration_sum=total,
                    all_duration_values_match_preserved_digital_witness=all(
                        a["days"] == b["days"]
                        for a, b in zip(claims, previous["claims"], strict=True)
                    ),
                )
            )
    annual = data["annual_literal_claim"]
    groups = re.findall(
        r"([甲乙丙丁戊己庚辛壬癸]+)各([一二三四五六七八九十]+)日",
        annual["literal_quote"],
    )
    if [(list(names), number(days)) for names, days in groups] != [
        (g["source_names"], g["each_days"]) for g in annual["groups"]
    ]:
        raise ValueError("Annual literal groups differ from structured readings")
    stated = re.search(r"共計([一二三四五六七八九十百]+)日", annual["literal_quote"])
    if stated is None:
        raise ValueError("Annual stated sum omitted")
    hundreds, remainder = stated[1].split("百")
    stated_number = number(hundreds) * 100 + (number(remainder) if remainder else 0)
    if stated_number != annual["stated_total_days"]:
        raise ValueError("Annual stated literal sum differs")
    annual_total = sum(
        len(g["source_names"]) * g["each_days"] for g in annual["groups"]
    )
    quote = data["closing_critique"]["literal_quote"]
    for anchor in [
        "醉醒子曰",
        "客無勝主之理",
        "初中末三氣之淺深",
        "又豈可以三五七日為限哉",
        "又支中所藏止以月論年日時不論人命重提綱厥有旨哉",
    ]:
        if anchor not in quote:
            raise ValueError("Closing critique or its limits omitted")
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        transcription_parser_sha256=digest(
            ROOT / "scripts/audit_bazi_month_duty_sources.py"
        ),
        witness_sha256=digest(DATA),
        source_pdf_sha256=source["source_pdf_sha256"],
        complete_chapter_pages_retained=list(range(66, 75)),
        month_rows=len(rows),
        duration_claims=sum(r["duration_claims"] for r in rows),
        rows=rows,
        glyph_reading_differences=glyph_differences,
        duration_value_differences=duration_differences,
        nominal_month_totals_not_thirty=[
            r for r in rows if r["literal_duration_sum"] != 30
        ],
        annual_computed_literal_sum=annual_total,
        annual_stated_sum=annual["stated_total_days"],
        original_digital_data_unchanged=True,
        scope="Hashes and parsing verify the frozen developer transcription and its archived page bindings; they do not independently recognize scan characters. All pages were visually read by the same developer; exact identity with the Shidian underlying copy is not established.",
        independent_expert_acceptance="not_completed",
        duty_calendar_profile_adopted=False,
        new_classical_correct_cases_credited=0,
        new_model_executions=0,
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or Path(str(output) + ".sha256").exists():
        raise SystemExit("Preserve first results")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    Path(str(output) + ".sha256").write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "month_rows",
                    "duration_claims",
                    "annual_computed_literal_sum",
                    "annual_stated_sum",
                    "full_goal_complete",
                )
            }
        )
    )


if __name__ == "__main__":
    main()

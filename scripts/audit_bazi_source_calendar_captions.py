"""Audit printed calendar constraints without reconstructing anyone's birth date.

This checks source consistency under an explicitly frozen editorial profile. It
neither calls FateBridge's calendar nor scores body strength or predictive power.
"""

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDY = ROOT / "docs/validation/bazi-source-calendar-caption-constraints-v1"
ALIASES = {"惊蛰": "驚蟄", "芒种": "芒種"}
DIGITS = {c: n for n, c in enumerate("零一二三四五六七八九")}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bound(path):
    if sha(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen input changed: {path.name}")
    return json.loads(path.read_text())


def number(text):
    """Deliberately limited grammar; unsupported numerals stay unparsed."""
    if re.fullmatch(r"[0-9]+", text):
        return int(text)
    if text in DIGITS:
        return DIGITS[text]
    match = re.fullmatch(r"([一二三四五六七八九]?)十([一二三四五六七八九]?)", text)
    if match:
        return DIGITS.get(match[1], 1) * 10 + DIGITS.get(match[2], 0)
    return None


def parse_relative(text, terms):
    names = sorted(set(terms) | set(ALIASES), key=len, reverse=True)
    pattern = (
        "(" + "|".join(names) + r")([前後后])([0-9零一二三四五六七八九十]+)(日|天)"
    )
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        return {"status": "unparsed", "reason": "not_one_simple_relative_caption"}
    match = matches[0]
    # 後七日前 and 後八日十日內 cannot become a simple positive offset.
    tail = text[match.end() :]
    if re.match(
        r"[前後后內内至到半許许餘余或零一二三四五六七八九十0-9]|左右|以上|以下", tail
    ):
        return {"status": "unparsed", "reason": "compound_or_range_suffix"}
    count = number(match[3])
    if count is None or count <= 0:
        return {"status": "unparsed", "reason": "nonpositive_or_unsupported_count"}
    # Reject fractional offsets hidden by a substring match, or a second range.
    if re.search(r"[半點点分之./]", match[0]) or re.match(r"[.,．·][0-9]", tail):
        return {"status": "unparsed", "reason": "fractional_or_compound_offset"}
    return {
        "status": "parsed_strict_relative_order",
        "literal": match[0],
        "term": ALIASES.get(match[1], match[1]),
        "side": "before" if match[2] == "前" else "after",
        "positive_day_count_as_printed": count,
        "day_count_interpretation": "strict side only; duration/inclusive counting unresolved",
    }


def month_constraint(month, parsed, profile):
    if parsed["status"] == "unparsed":
        return {"status": "unparsed", "reason": parsed["reason"]}
    if (
        not isinstance(month, str)
        or len(month) != 2
        or month[1] not in profile["branches"]
    ):
        return {"status": "unadjudicated", "reason": "missing_or_unknown_month_branch"}
    index = profile["branches"].index(month[1])
    start, end = profile["start_terms"][index], profile["start_terms"][(index + 1) % 12]
    term, side = parsed["term"], parsed["side"]
    conflict = (term == start and side == "before") or (term == end and side == "after")
    endpoint = term in {start, end}
    return {
        "status": (
            "direct_order_contradiction"
            if conflict
            else "no_direct_endpoint_contradiction" if endpoint else "unadjudicated"
        ),
        "literal_month_retained": month,
        "declared_month_interval": {
            "start": start,
            "end": end,
            "closure": "[start,end)",
        },
        "relative_order": f"t {'<' if side == 'before' else '>'} {term}",
        "full_month_membership_proved": False,
        "corrected_month": None,
        "modern_birth_instant": None,
    }


def plain_text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip()


def reference_cycle(study, receipts, profile, root):
    by_id = {r["id"]: r for r in receipts}
    for receipt in receipts:
        path = root / receipt["path"]
        if sha(path) != receipt["sha256"] or path.stat().st_size != receipt["bytes"]:
            raise ValueError("Primary reference lost byte binding")
    content = (root / by_id["hko-cycle"]["path"]).read_text()
    tables = re.findall(
        r'<table\b[^>]*title="六十干支表"[^>]*>(.*?)</table>', content, re.S
    )
    if not tables:
        raise ValueError("No HKO sexagenary table")
    # Read the 60 printed cells in their actual row order, not a production epoch.
    cycle = re.findall(
        r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]",
        plain_text(" ".join(tables)),
    )
    if len(cycle) != 60 or len(set(cycle)) != 60 or cycle[0] != "甲子":
        raise ValueError("Independent cycle table incomplete")
    for anchor in profile["museum_year_anchors"]:
        text = (root / by_id[anchor["reference_id"]]["path"]).read_text()
        title = plain_text(re.search(r"<title[^>]*>(.*?)</title>", text, re.S)[1])
        match = re.search(
            r"乾隆([零一二三四五六七八九十0-9]+)年([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])",
            title,
        )
        if (
            not match
            or number(match[1]) != anchor["year"]
            or match[2] != anchor["ganzhi"]
        ):
            raise ValueError("Official collection title disagrees with frozen anchor")
        catalog = plain_text(text).split("典藏號", 1)[1].split("更多藏品", 1)[0]
        if str(anchor["associated_western_year"]) not in catalog:
            raise ValueError("Official collection western-year anchor changed")
    for a in profile["museum_year_anchors"]:
        for b in profile["museum_year_anchors"]:
            if (
                cycle[(cycle.index(a["ganzhi"]) + b["year"] - a["year"]) % 60]
                != b["ganzhi"]
            ):
                raise ValueError("Museum anchors disagree with independent cycle")
    return cycle


def era_constraint(caption, year_pillar, cycle, profile):
    match = re.fullmatch(r"乾隆([零一二三四五六七八九十0-9]+)年.+", caption or "")
    if not match or number(match[1]) is None:
        return {"status": "unparsed", "literal_caption_retained": caption}
    year = number(match[1])
    nominal = {
        cycle[(cycle.index(a["ganzhi"]) + year - a["year"]) % 60]
        for a in profile["museum_year_anchors"]
        if a["era"] == "乾隆"
    }
    if len(nominal) != 1:
        raise ValueError("Era-year references do not agree")
    ganzhi = nominal.pop()
    conservative = [cycle[(cycle.index(ganzhi) + delta) % 60] for delta in [-1, 0, 1]]
    return {
        "status": (
            "year_caption_contradiction_even_with_adjacent_years"
            if year_pillar not in conservative
            else "not_disproved_by_conservative_year_set"
        ),
        "literal_caption_retained": caption,
        "literal_year_pillar_retained": year_pillar,
        "nominal_era_year_ganzhi": ganzhi,
        "conservative_previous_nominal_next_year_candidates": conservative,
        "birth_calendar_conversion_performed": False,
        "corrected_caption": None,
        "corrected_year_pillar": None,
        "modern_birth_instant": None,
    }


def audit(study=DEFAULT_STUDY, root=ROOT):
    protocol = read_bound(study / "protocol-first.json")
    before = read_bound(study / "census-before-first.json")
    selected = read_bound(study / "selection-first.json")
    profile = read_bound(study / "reference-profile-first.json")
    receipts = read_bound(study / "reference-receipts-first.json")
    claims, cases = before["resolved_source_claims"], before["resolved_source_cases"]
    fresh_selection = {
        key: value
        for key, value in claims.items()
        if re.search(
            selected["relative_term_selector"],
            value.get("anchor", "") + " " + value.get("retained_statement", ""),
        )
    }
    fresh_era = [
        c
        for c in cases
        if re.search(
            selected["era_selector"],
            json.dumps(c.get("source_metadata", {}), ensure_ascii=False),
        )
    ]
    if (
        selected["relative_claims"] != fresh_selection
        or selected["era_metadata_cases"] != fresh_era
    ):
        raise ValueError("Full frozen source selection changed")
    if (
        len(claims) != protocol["full_scope"]["source_claims"]
        or len(cases) != protocol["full_scope"]["literal_cases"]
    ):
        raise ValueError("Original full source denominator changed")
    cycle = reference_cycle(study, receipts, profile, root)
    relative = []
    for identity, claim in fresh_selection.items():
        text = claim["anchor"]
        if not re.search("|".join(profile["start_terms"]), text):
            text = claim["retained_statement"]
        parsed = parse_relative(text, profile["start_terms"])
        linked = [c for c in cases if identity in c["claim_ids"]]
        row = {
            "claim_id": identity,
            "first_claim_object": claim,
            "parse": parsed,
            "case_constraints": [
                {
                    "case_id": c["case_id"],
                    "first_case_object": c,
                    **month_constraint(
                        c["literal_pillars"].get("month"), parsed, profile
                    ),
                }
                for c in linked
            ],
        }
        if not linked:
            row["unbound_reason"] = "general_or_compound_rule_not_a_literal_birth_case"
        relative.append(row)
    era = [
        {
            "case_id": c["case_id"],
            "first_case_object": c,
            **era_constraint(
                c["source_metadata"].get("source_caption_as_printed"),
                c["literal_pillars"].get("year"),
                cycle,
                profile,
            ),
        }
        for c in fresh_era
    ]
    return {
        "protocol_sha256": sha(study / "protocol-first.json"),
        "reference_profile_sha256": sha(study / "reference-profile-first.json"),
        "runner_sha256": sha(Path(__file__)),
        "all_source_claims_scanned": len(claims),
        "all_literal_cases_scanned": len(cases),
        "relative_term_rows": relative,
        "era_caption_rows": era,
        "source_questions_closed": 0,
        "original26_disagreements_closed": 0,
        "calendar_or_pillar_repair_performed": False,
        "source_strength_labels_changed": False,
        "source_is_conflict_free_calendar_oracle": False,
        "force_candidate_evaluation_allowed": False,
        "new_model_executions": 0,
        "independent_annotation_review": "not_certified",
        "full_goal_complete": False,
        "original_gates_superseded": False,
        "overall_score": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.study)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Audit output is append-only; select a new path")
        args.output.write_text(rendered)
    else:
        print(rendered, end="")

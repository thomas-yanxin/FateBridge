"""金锁银匙 / 邵子参评数：起数、命宫顺排、条文 O(1) 检索与精简证据。"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import get_nayin
from fatebridge.utils.errors import NumerologySourceError

BRANCHES: tuple[str, ...] = (
    "子",
    "丑",
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
)
BRANCH_NUM: dict[str, int] = {
    branch: index + 1 for index, branch in enumerate(BRANCHES)
}

# 明法（胖胖熊）：月支(月建/八字月支)反向取日宫支。
MONTH_TO_DAY_PALACE: dict[str, str] = {
    "寅": "亥",
    "卯": "戌",
    "辰": "酉",
    "巳": "申",
    "午": "未",
    "未": "午",
    "申": "巳",
    "酉": "辰",
    "戌": "卯",
    "亥": "寅",
    "子": "丑",
    "丑": "子",
}

# 水火 +27、土 +50、木金 +0；水1 火2 木3 金4 土5。
ELEMENT_ADD: dict[str, int] = {"水": 27, "火": 27, "土": 50, "木": 0, "金": 0}
ELEMENT_PEI: dict[str, int] = {"水": 1, "火": 2, "木": 3, "金": 4, "土": 5}
PART_NAMES: dict[str, str] = {
    "水": "水部",
    "火": "火部",
    "木": "木部",
    "金": "金部",
    "土": "土部",
}
GANS: tuple[str, ...] = (
    "甲",
    "乙",
    "丙",
    "丁",
    "戊",
    "己",
    "庚",
    "辛",
    "壬",
    "癸",
)
CYCLE_SET = frozenset(GANS[i % 10] + BRANCHES[i % 12] for i in range(60))

DATA_ROOT = Path(__file__).resolve().parents[2] / "data/canping"
INHERITED_PATH = DATA_ROOT / "canpingTiaowen.json"
COLLATION_PATH = DATA_ROOT / "text-collation-v1.json"
WITNESSES_PATH = DATA_ROOT / "text-witnesses-v1.json"
KINDS = {"male": "upper_male", "female": "middle_female", "luck": "lower_shared_luck"}


class LegacyLuckStep(TypedDict):
    index: int
    branch: str
    ageStart: int
    ageEnd: int


@lru_cache(maxsize=3)
def _loaded(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_bytes())
        if not isinstance(data, dict):
            raise ValueError("参评来源须为结构化对象。")
    except (OSError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_canping_text_source") from exc
    return data


def inherited_corpus() -> dict[str, Any]:
    """Return a detached comparison corpus without exposing the cached source."""
    return deepcopy(_loaded(INHERITED_PATH))


def text_available(text: str) -> bool:
    return bool(text) and any(c not in "○〇□ \n，。" for c in text)


@lru_cache(maxsize=1)
def _collation() -> dict[str, Any]:
    try:
        data = _loaded(COLLATION_PATH)
        additional = data.get("additional_rereading_witnesses", [])
        if not isinstance(additional, list):
            raise ValueError("参评复读见证须分别登记，不能覆盖先前见证。")
        witnesses = (
            [data["rereading_witness"]] if data.get("rereading_witness") else []
        ) + additional
        if any(
            not isinstance(w, dict)
            or not isinstance(w.get("fixture_id"), str)
            or not w["fixture_id"]
            for w in witnesses
        ) or len({w["fixture_id"] for w in witnesses}) != len(witnesses):
            raise ValueError("参评复读见证身份缺失或重复。")
        rereading_pages = {
            w["fixture_id"]: {p["pdf_page"] for p in w["pages"]} for w in witnesses
        }
        keys = [(e["element"], e["number"]) for e in data["entries"]]
        if len(keys) != len(set(keys)) or any(
            set(e["cells"]) - KINDS.keys() for e in data["entries"]
        ):
            raise ValueError("参评校勘索引重复或栏目无效。")
        entries_by_key = dict(zip(keys, data["entries"]))
        number_observations = data.get("number_reading_witness", {}).get("headers", [])
        observed_keys = [
            (r["element"], r["provisional_number"]) for r in number_observations
        ]
        if len(observed_keys) != len(set(observed_keys)) or set(observed_keys) - set(
            keys
        ):
            raise ValueError("参评编号原图证据重复或缺少对应条目。")
        for observed in number_observations:
            entry = entries_by_key[
                (observed["element"], observed["provisional_number"])
            ]
            if (
                observed.get("resolution_status") != "unresolved"
                or not isinstance(observed.get("observed_header"), str)
                or "□" not in observed["observed_header"]
                or observed.get("pdf_page") != entry["pdf_page"]
                or not entry.get("number_reading_uncertainties")
                or set(entry["cells"]) - entry.get("reading_uncertainties", {}).keys()
            ):
                raise ValueError(
                    "参评编号疑读原图仍有未定字，不得撤销编号疑读或提升任何一栏。"
                )
        for entry in data["entries"]:
            uncertain = entry.get("reading_uncertainties", {})
            revisions = entry.get("reading_revisions", {})
            if set(revisions) - entry["cells"].keys() or any(
                not isinstance(r, dict)
                or r.get("rereading_id") not in rereading_pages
                or r.get("source_pdf_page") != entry["pdf_page"]
                or r.get("source_pdf_page")
                not in rereading_pages.get(r.get("rereading_id"), set())
                or r.get("previous_cell_status") != "source_reading_uncertain"
                or not isinstance(r.get("previous_text"), str)
                or "□" not in r["previous_text"]
                or not isinstance(r.get("note"), str)
                or not r["note"]
                for r in revisions.values()
            ):
                raise ValueError("参评复读修订须保留原疑读、对应原页和复读见证。")
            number_uncertain = entry.get("number_reading_uncertainties")
            if number_uncertain is not None and (
                not isinstance(number_uncertain, list)
                or not number_uncertain
                or any(
                    not isinstance(note, str) or not note for note in number_uncertain
                )
                or set(entry["cells"]) - uncertain.keys()
            ):
                raise ValueError(
                    "参评编号疑读须说明原因，并将该行所有已录栏目保留未定。"
                )
            if set(uncertain) - entry["cells"].keys() or any(
                not isinstance(notes, list)
                or not notes
                or any(not isinstance(note, str) or not note for note in notes)
                for notes in uncertain.values()
            ):
                raise ValueError("参评疑读须对应具体栏目并说明原因。")
            if any(
                "□" in text and kind not in uncertain
                for kind, text in entry["cells"].items()
            ):
                raise ValueError("参评编辑方框必须明确标为疑读，不能冒充原页圈空。")
        return data
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_canping_text_collation") from exc


@lru_cache(maxsize=1)
def _witness_corpus() -> dict[str, Any]:
    try:
        data = _loaded(WITNESSES_PATH)
        keys = [(e["element"], e["number"], e["kind"]) for e in data["entries"]]
        unmatched = data.get("unmatched_observations", [])
        if not isinstance(unmatched, list):
            raise ValueError("参评未匹配原页观察须逐格登记。")
        unmatched_keys = [(e["element"], e["number"], e["kind"]) for e in unmatched]
        if len(unmatched_keys) != len(set(unmatched_keys)) or set(keys) & set(
            unmatched_keys
        ):
            raise ValueError("参评未匹配观察不可重复或冒充已绑定对读格。")
        for e in data["entries"] + unmatched:
            if (
                e["element"] not in {"水", "火", "木", "金", "土"}
                or type(e["number"]) is not int
                or e["kind"] not in KINDS
                or not isinstance(e["text"], str)
                or not e["pdf_pages"]
                or any(type(p) is not int or p < 1 for p in e["pdf_pages"])
                or e["body_pdf_page"] not in e["pdf_pages"]
            ):
                raise ValueError("参评对读须对应明确五行、编号、栏目与原页。")
            notes = e.get("reading_uncertainties")
            if ("□" in e["text"] and not notes) or (
                notes
                and (
                    not isinstance(notes, list)
                    or any(not isinstance(n, str) or not n for n in notes)
                )
            ):
                raise ValueError("参评对读编辑方框须明确标为疑读。")
            occurrence = e.get("source_occurrence_id")
            header_page = e.get("header_pdf_page")
            if (occurrence is not None or header_page is not None) and (
                not isinstance(occurrence, str)
                or not occurrence
                or type(header_page) is not int
                or header_page not in e["pdf_pages"]
            ):
                raise ValueError("参评原页条目身份须绑定实际编号所在页。")
        grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
        for key, entry in zip(keys, data["entries"]):
            grouped.setdefault(key, []).append(entry)
        for entries in grouped.values():
            if len(entries) > 1:
                occurrences = [e.get("source_occurrence_id") for e in entries]
                if any(not isinstance(o, str) or not o for o in occurrences) or len(
                    occurrences
                ) != len(set(occurrences)):
                    raise ValueError("参评对读格重复；同号原页须有不同的条目身份。")
        if any(
            e.get("matching_status")
            != "unmatched_observation_not_assigned_to_a_computed_key"
            or e.get("header_pdf_page") not in e["pdf_pages"]
            or not isinstance(e.get("reason"), str)
            or not e["reason"]
            for e in unmatched
        ):
            raise ValueError("参评未匹配观察须保留实际编号、原页及未绑定原因。")
        return data
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_canping_witness_collation") from exc


@lru_cache(maxsize=1)
def _collation_index() -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[int, dict[str, Any]],
    dict[tuple[str, int, str], list[dict[str, Any]]],
]:
    source = _collation()
    entries_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    retired_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for entry in source["entries"]:
        key = (entry["element"], entry["number"])
        entries_by_key[key] = entry
        if "inherited_wrong_number" in entry:
            retired_by_key[(entry["element"], entry["inherited_wrong_number"])] = entry
    headers_by_key = {
        (r["element"], r["provisional_number"]): r
        for r in source.get("number_reading_witness", {}).get("headers", [])
    }
    unapplied_by_num = {n["printed_number"]: n for n in source["unapplied_notes"]}

    witness_data = _witness_corpus()
    witnesses_by_key: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for entry in witness_data["entries"]:
        witnesses_by_key.setdefault(
            (entry["element"], entry["number"], entry["kind"]), []
        ).append(entry)
    for entries in witnesses_by_key.values():
        entries.sort(
            key=lambda e: (
                e.get("header_pdf_page", e["pdf_pages"][0]),
                e["body_pdf_page"],
                e.get("source_occurrence_id", ""),
            )
        )
    return (
        entries_by_key,
        retired_by_key,
        headers_by_key,
        unapplied_by_num,
        witnesses_by_key,
    )


def _comparisons(
    element: str, number: int, kind: str, text: str, state: str, inherited_text: str
) -> list[dict[str, Any]]:
    witness_data = _witness_corpus()
    _, _, _, _, witnesses_by_key = _collation_index()
    entries = witnesses_by_key.get((element, number, kind), [])
    if not entries:
        return []
    result = []
    for entry in entries:
        primary_uncertain = state == "source_reading_uncertain"
        witness_uncertain = bool(entry.get("reading_uncertainties"))
        relation = (
            "both_readings_uncertain"
            if primary_uncertain and witness_uncertain
            else (
                "selected_reading_uncertain"
                if primary_uncertain
                else (
                    "witness_reading_uncertain"
                    if witness_uncertain
                    else "same_text" if text == entry["text"] else "different_text"
                )
            )
        )
        status = (
            "source_reading_uncertain"
            if witness_uncertain
            else (
                "source_printed_blank"
                if not text_available(entry["text"])
                else (
                    "source_printed_partial_blank"
                    if any(c in entry["text"] for c in "○〇")
                    else "source_cell_visually_collated"
                )
            )
        )
        result.append(
            {
                **entry,
                "source_corpus_id": witness_data["corpus_id"],
                "text_status": status,
                "relation": relation,
                "replaces_selected_text": False,
                "inherited_reading_matches": inherited_text == entry["text"],
                **(
                    {
                        "number_occurrence_count": len(entries),
                        "number_occurrence_ambiguous": True,
                    }
                    if len(entries) > 1
                    else {}
                ),
            }
        )
    return result


def lookup_record(
    element: str,
    number: int,
    kind: str | None,
    *,
    include_witnesses: bool = True,
) -> dict[str, Any]:
    """O(1) indexed lookup in Canping collation and inherited tables."""
    if (
        not isinstance(element, str)
        or element not in {"水", "火", "木", "金", "土"}
        or type(number) is not int
    ):
        raise ValueError("参评选条须为明确五行及整数编号。")
    if kind is not None and (not isinstance(kind, str) or kind not in KINDS):
        raise ValueError("参评栏目仅支持male、female、luck或未选性别的None。")
    source = _collation()
    (
        entries_by_key,
        retired_by_key,
        headers_by_key,
        unapplied_by_num,
        _,
    ) = _collation_index()
    inherited_parts = _loaded(INHERITED_PATH)["parts"][element]
    row = inherited_parts.get(str(number))
    entry = entries_by_key.get((element, number))
    retired = retired_by_key.get((element, number))
    if entry and "inherited_wrong_number" in entry:
        row = inherited_parts.get(str(entry["inherited_wrong_number"]))
    selection: dict[str, Any] = {
        "element": element,
        "number": number,
        "kind": kind,
        "column": KINDS.get(kind) if kind is not None else None,
        "corpus_key": f"{element}.{number}.{kind}" if kind is not None else None,
        "row_status": "present" if row or entry else "absent_in_local_corpus",
        "cell_status": "inherited_transcription_unverified",
    }
    if retired:
        selection.update(
            row_status="retired_inherited_number",
            cell_status="retired_inherited_number",
            corrected_number=retired["number"],
        )
        return {"text": "", "selection": selection}
    if kind is None:
        selection["cell_status"] = "not_selected_missing_gender"
        return {"text": "", "selection": selection}
    if entry and kind in entry["cells"]:
        text = entry["cells"][kind]
        uncertain = entry.get("reading_uncertainties", {}).get(kind)
        selection.update(
            cell_status=(
                "source_reading_uncertain"
                if uncertain
                else (
                    "source_printed_blank"
                    if not text_available(text)
                    else (
                        "source_printed_partial_blank"
                        if any(c in text for c in "○〇")
                        else "source_cell_visually_collated"
                    )
                )
            ),
            collation_id=source["corpus_id"],
            source_pdf_page=entry["pdf_page"],
        )
        if uncertain:
            selection["reading_uncertainties"] = list(uncertain)
            if "□" in text:
                selection["editorial_unknown_marker"] = "□"
        if entry.get("number_reading_uncertainties"):
            selection["number_attribution_status"] = "provisional_inherited_key"
            if include_witnesses:
                selection["number_reading_uncertainties"] = list(
                    entry["number_reading_uncertainties"]
                )
                observed = headers_by_key.get((element, number))
                if observed:
                    selection["number_reading_evidence"] = {
                        **observed,
                        "witness_id": source["number_reading_witness"]["fixture_id"],
                        "body_evidence_basis": "prior_literal_transcription_not_new_body_collation",
                    }
                    selection["body_reading_status"] = (
                        "source_body_reading_uncertain"
                        if "□" in text
                        else (
                            "source_body_printed_blank"
                            if not text_available(text)
                            else (
                                "source_body_printed_partial_blank"
                                if any(c in text for c in "○〇")
                                else "source_body_visually_read"
                            )
                        )
                    )
        if include_witnesses:
            if entry.get("reading_notes"):
                selection["reading_notes"] = list(entry["reading_notes"])
            if kind in entry.get("reading_revisions", {}):
                selection["reading_revision"] = entry["reading_revisions"][kind]
            old_text = (row or {}).get(kind, "")
            if old_text != text or "inherited_wrong_number" in entry:
                selection["inherited_text"] = old_text
            if "inherited_wrong_number" in entry:
                selection["inherited_number"] = entry["inherited_wrong_number"]
    else:
        text = (row or {}).get(kind) or ""
        if not row:
            selection["cell_status"] = "row_absent_in_local_corpus"
        elif not text_available(text):
            selection["cell_status"] = "inherited_blank_or_placeholder_unverified"
    if include_witnesses:
        note = unapplied_by_num.get(number)
        if note:
            selection["unapplied_note"] = {
                k: note[k]
                for k in ("printed_number", "pdf_page", "status", "applied_to_lookup")
            }
        comparisons = _comparisons(
            element,
            number,
            kind,
            text,
            selection["cell_status"],
            (row or {}).get(kind, ""),
        )
        if comparisons:
            selection["witnesses"] = comparisons
    if not include_witnesses:
        compact_sel: dict[str, Any] = {
            "kind": kind,
            "cell_status": selection["cell_status"],
        }
        if selection.get("source_pdf_page") is not None:
            compact_sel["source_pdf_page"] = selection["source_pdf_page"]
        if selection.get("corrected_number") is not None:
            compact_sel["corrected_number"] = selection["corrected_number"]
        return {"text": text, "selection": compact_sel}
    return {"text": text, "selection": selection}


def pair_resolution(
    shun: dict[str, Any], ni: dict[str, Any], *, compact: bool = False
) -> dict[str, Any]:
    same = shun["selection"]["number"] == ni["selection"]["number"]
    present = (text_available(shun["text"]), text_available(ni["text"]))
    availability = {
        (True, True): "both_directions",
        (True, False): "shun_only",
        (False, True): "ni_only",
        (False, False): "neither_direction",
    }[present]
    if compact:
        return {"same_number": same, "local_text_availability": availability}
    return {
        "same_number": same,
        "distinct_numbers": 1 if same else 2,
        "local_text_availability": availability,
        "source_rule_pdf_page": _collation()["direction_rule_pdf_page"],
        "independent_evidence_count": None,
    }


def nayin_element(year_gz: str) -> str:
    """年干支 → 纳音五行（金/木/水/火/土）。"""
    if not isinstance(year_gz, str) or year_gz not in CYCLE_SET:
        return ""
    nayin = get_nayin(year_gz[0], year_gz[1])
    if not nayin or nayin == "未知纳音":
        return ""
    return nayin[-1]


def _branch_from_num(number: int) -> str:
    return BRANCHES[((number - 1) % 12 + 12) % 12]


def _branch_of(ganzhi_or_branch: str) -> str:
    text = ganzhi_or_branch or ""
    if len(text) >= 2 and text[1] in BRANCH_NUM:
        return text[1]
    if len(text) == 1 and text in BRANCH_NUM:
        return text
    return ""


def day_palace(month_branch: str, day_branch: str, method: str = "gu") -> str:
    """日宫支：明法用月支反向，古法直接用八字日支。"""
    if method == "gu":
        return day_branch
    if method == "ming":
        return MONTH_TO_DAY_PALACE[month_branch]
    raise ValueError("method 仅支持 gu（原典日支）或 ming（月支变法）。")


def ming_gong(day_palace_branch: str, hour_branch: str) -> str:
    """命宫：日宫支配卯时起，逆数至生时。"""
    mao_branch_number = BRANCH_NUM["卯"]
    day_palace_number = BRANCH_NUM[day_palace_branch]
    hour_branch_number = BRANCH_NUM[hour_branch]
    ming_gong_number = (
        (day_palace_number - (hour_branch_number - mao_branch_number) - 1) % 12 + 12
    ) % 12 + 1
    return _branch_from_num(ming_gong_number)


def compute_number(day_branch: str, hour_branch: str, element: str) -> dict[str, int]:
    """Calculate the forward and reverse Canping lookup numbers."""
    if element not in ELEMENT_ADD:
        raise ValueError("纳音五行必须是水、火、木、金、土。")
    day_branch_number = BRANCH_NUM[day_branch]
    hour_branch_number = BRANCH_NUM[hour_branch]
    forward_count = ((hour_branch_number - day_branch_number) % 12 or 12) + 1
    reverse_count = ((day_branch_number - hour_branch_number) % 12 or 12) + 1
    zi_origin_count = day_branch_number + hour_branch_number
    base_number = 2000 + zi_origin_count + ELEMENT_ADD[element] + ELEMENT_PEI[element]
    return {
        "shun": forward_count,
        "ni": reverse_count,
        "ziRound": zi_origin_count,
        "numShun": base_number + forward_count * 100,
        "numNi": base_number + reverse_count * 100,
    }


def _verses(
    element: str,
    numbers: dict[str, int],
    kind: str | None,
    *,
    compact: bool = False,
) -> dict[str, Any]:
    def status(text: str) -> str:
        if not text or all(c in "○〇□ \n，。" for c in text):
            return "unavailable_in_local_corpus"
        return (
            "incomplete_transcription"
            if any(c in text for c in "○〇□")
            else "unverified_transcription"
        )

    shun = lookup_record(
        element, numbers["numShun"], kind, include_witnesses=not compact
    )
    ni = lookup_record(element, numbers["numNi"], kind, include_witnesses=not compact)

    def selected_status(record: dict[str, Any]) -> str:
        state = record["selection"]["cell_status"]
        if state in {
            "source_cell_visually_collated",
            "source_printed_blank",
            "source_printed_partial_blank",
            "source_reading_uncertain",
            "not_selected_missing_gender",
        }:
            return str(state)
        return status(record["text"])

    if compact:
        return {
            "textShun": shun["text"],
            "textNi": ni["text"],
            "selectionShun": shun["selection"],
            "selectionNi": ni["selection"],
        }
    return {
        "numShun": numbers["numShun"],
        "numNi": numbers["numNi"],
        "textShun": shun["text"],
        "textNi": ni["text"],
        "statusShun": selected_status(shun),
        "statusNi": selected_status(ni),
        "selectionShun": shun["selection"],
        "selectionNi": ni["selection"],
        "pair_resolution": pair_resolution(shun, ni, compact=compact),
    }


def _kind_for_gender(gender: str | None) -> Literal["male", "female"] | None:
    if gender is None:
        return None
    if isinstance(gender, str):
        normalized_gender = normalize_gender(gender)
        if normalized_gender == "女":
            return "female"
        if normalized_gender == "男":
            return "male"
    raise ValueError("参评本命选栏需要明确男／女；未提供时可算数，但不能默认性别。")


def dayun_sequence(
    day_palace_branch: str,
    hour_branch: str,
    qiyun_age: int = 1,
    count: int = 9,
) -> tuple[list[LegacyLuckStep], str]:
    """Generate the legacy decade sequence forward from the Ming Gong branch."""
    ming_gong_branch = ming_gong(day_palace_branch, hour_branch)
    first_branch_number = BRANCH_NUM[ming_gong_branch]
    steps: list[LegacyLuckStep] = []
    for step_index in range(count):
        branch = _branch_from_num(first_branch_number + step_index)
        start_age_years = qiyun_age + 10 * step_index
        steps.append(
            {
                "index": step_index,
                "branch": branch,
                "ageStart": start_age_years,
                "ageEnd": start_age_years + 9,
            }
        )
    return steps, ming_gong_branch


def _year_ganzhi(year: int) -> str:
    return GANS[((year - 4) % 10 + 10) % 10] + BRANCHES[((year - 4) % 12 + 12) % 12]


def calculate(
    *,
    year_gz: str,
    month_branch: str,
    day_branch: str,
    hour_branch: str,
    gender: str | None = None,
    method: str = "gu",
    qiyun_age: int = 1,
    liunian_branch: str | None = None,
    active_dayun_branch: str | None = None,
    include_luck: bool = True,
    compact_verses: bool = False,
) -> dict[str, Any]:
    """本命 + 大运 (+ 可选单点流年) 起数与条文。"""
    kind_main = _kind_for_gender(gender)
    normalized_gender = (
        None if kind_main is None else ("女" if kind_main == "female" else "男")
    )
    element = nayin_element(year_gz)
    dp_branch = day_palace(month_branch, day_branch, method)

    benming = compute_number(dp_branch, hour_branch, element)
    benming_verses = _verses(element, benming, kind_main, compact=compact_verses)

    luck_steps, ming_gong_branch = (
        dayun_sequence(dp_branch, hour_branch, qiyun_age) if include_luck else ([], "")
    )
    dayun: list[dict[str, Any]] = []
    for step in luck_steps:
        info = compute_number(dp_branch, step["branch"], element)
        dayun.append(
            {
                **step,
                **info,
                "verses": _verses(element, info, "luck", compact=compact_verses),
            }
        )

    liunian: dict[str, Any] | None = None
    if liunian_branch:
        if active_dayun_branch is None or active_dayun_branch not in BRANCHES:
            raise ValueError("单点流年须明确active_dayun_branch，不能默认取第一运。")
        taisui_branch = _branch_of(liunian_branch)
        annual_numbers = compute_number(taisui_branch, active_dayun_branch, element)
        liunian = {
            "taisuiBranch": taisui_branch,
            "dayunBranch": active_dayun_branch,
            **annual_numbers,
            "verses": _verses(element, annual_numbers, "luck", compact=compact_verses),
        }

    return {
        "method": method,
        "gender": normalized_gender,
        "element": element,
        "partName": PART_NAMES.get(element, f"{element}部"),
        "fourPillars": {
            "yearGz": year_gz,
            "monthBranch": month_branch,
            "dayBranch": day_branch,
            "hourBranch": hour_branch,
        },
        "dayPalaceBranch": dp_branch,
        "mingGong": ming_gong_branch,
        "kindMain": kind_main,
        "benming": {**benming, "verses": benming_verses},
        "dayun": dayun,
        "liunian": liunian,
        "qiyunAge": qiyun_age if include_luck else None,
        "dayunPolicy": (
            "legacy_minggong_unverified_v1" if include_luck else "not_computed"
        ),
    }


def liunian_series(
    *,
    year_gz: str,
    month_branch: str,
    day_branch: str,
    hour_branch: str,
    gender: str | None = None,
    method: str = "gu",
    qiyun_age: int = 1,
    birth_year: int | None = None,
    start_age: int = 1,
    end_age: int = 120,
) -> dict[str, Any]:
    """按虚岁与实际大运支逐岁起数；保留紧凑结构。"""
    if (
        type(start_age) is not int
        or type(end_age) is not int
        or start_age < 1
        or end_age < start_age
    ):
        raise ValueError("年序年龄范围须为从1起的有序整数。")
    if type(qiyun_age) is not int or qiyun_age < 0:
        raise ValueError("起运年龄须为明确的非负整数。")
    if birth_year is not None and (type(birth_year) is not int or birth_year < 1):
        raise ValueError("公历年标签须为正整数；未知用None，不能用布尔值代替。")
    if birth_year is not None and _year_ganzhi(birth_year) != year_gz:
        raise ValueError("流年起始年标签须与出生年柱一致；立春前不能直接用公历出生年。")
    result = calculate(
        year_gz=year_gz,
        month_branch=month_branch,
        day_branch=day_branch,
        hour_branch=hour_branch,
        gender=gender,
        method=method,
        qiyun_age=qiyun_age,
        include_luck=False,
        compact_verses=True,
    )
    element = result["element"]
    cycle = tuple(GANS[i % 10] + BRANCHES[i % 12] for i in range(60))
    birth_cycle_index = cycle.index(year_gz)
    count = max(9, (end_age - qiyun_age) // 10 + 1)
    sequence, _ = dayun_sequence(
        result["dayPalaceBranch"], hour_branch, qiyun_age, count
    )
    dayun: list[dict[str, Any]] = []
    for step in sequence:
        info = compute_number(result["dayPalaceBranch"], step["branch"], element)
        dayun.append(
            {**step, **info, "verses": _verses(element, info, "luck", compact=True)}
        )

    def dayun_at(age: int) -> dict[str, Any] | None:
        k = (age - qiyun_age) // 10
        if k < 0:
            return None
        return dayun[k]

    rows: list[dict[str, Any]] = []
    for age in range(start_age, end_age + 1):
        year = birth_year + age - 1 if birth_year is not None else None
        ganzhi = cycle[(birth_cycle_index + age - 1) % 60]
        taisui = ganzhi[1]
        row: dict[str, Any] = {
            "age": age,
            "year": year,
            "ganzhi": ganzhi,
            "taisuiBranch": taisui,
        }
        dy = dayun_at(age)
        if dy is None:
            rows.append({**row, "status": "not_started"})
            continue
        info = compute_number(taisui, dy["branch"], element)
        row.update(
            {
                "status": "active",
                "dayunBranch": dy["branch"],
                "numShun": info["numShun"],
                "numNi": info["numNi"],
            }
        )
        rows.append(row)
    return {
        "element": element,
        "partName": result["partName"],
        "dayun": dayun,
        "rows": rows,
        "qiyunAge": qiyun_age,
        "birth_pillar_year": birth_year,
        "year_boundary": (
            "provided_year_labels_only"
            if birth_year is not None
            else "relative_ganzhi_year_labels_only"
        ),
        "age_policy": "relative_sexagenary_year_ordinal; no_actual_boundaries",
    }


def canping_evidence(calculation: dict[str, Any]) -> dict[str, Any]:
    """Build compact factual evidence for Canping without collation/prose bloat."""
    method = calculation["method"]
    collation = _collation()
    timing = calculation.get("timing")
    selected = timing.get("selected") if timing else None
    rulesets: list[dict[str, Any]] = [
        {
            "ruleset_id": (
                "jinsuo_day_branch_v1" if method == "gu" else "canping_month_variant_v1"
            ),
            "version": "1.0.0",
            "source_title": "河洛理數（史應選校訂本）",
            "source_status": "collated_subset",
        },
        {
            "ruleset_id": collation["corpus_id"],
            "version": collation["version"],
            "source_title": collation["source_title"],
            "source_status": collation["review_status"],
        },
    ]
    selected_texts: list[dict[str, Any]] = []
    rule_trace: list[dict[str, Any]] = [
        {
            "rule_id": "jinsuo_benming",
            "source_section": "卷六·金鎖銀匙",
            "facts": {
                "method": method,
                "day_palace_branch": calculation["dayPalaceBranch"],
                "nayin_element": calculation["element"],
                "kind": calculation["kindMain"],
                "numShun": calculation["benming"]["numShun"],
                "numNi": calculation["benming"]["numNi"],
            },
        }
    ]
    if timing and timing["profile_id"] != "legacy_minggong_v1":
        rulesets.append(
            {
                "ruleset_id": timing["ruleset_id"],
                "version": timing["ruleset_version"],
                "source_title": timing["source_title"],
                "source_status": timing["source_status"],
            }
        )
        if selected and selected.get("status") == "active":
            selected_texts.append(
                {
                    "phase": "liunian_segment",
                    "at": selected["at"],
                    "ganzhi": selected["ganzhi"],
                    "dayun_pillar": selected["dayun_pillar"],
                    "kind": "luck",
                    "verses": selected["verses"],
                }
            )
    return {
        "rulesets": rulesets,
        "selected_texts": selected_texts,
        "rule_trace": rule_trace,
    }

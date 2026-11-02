"""Column-specific partial Canping collation and explicit local missing rows.

The inherited corpus is retained. A missing local row, an observed printed
blank, and a gender column that was not selected are distinct facts.
"""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional

from fatebridge.utils.errors import NumerologySourceError

DATA_ROOT = Path(__file__).resolve().parents[1] / "data/canping"
INHERITED_PATH = DATA_ROOT / "canpingTiaowen.json"
COLLATION_PATH = DATA_ROOT / "text-collation-v1.json"
WITNESSES_PATH = DATA_ROOT / "text-witnesses-v1.json"
KINDS = {"male": "upper_male", "female": "middle_female", "luck": "lower_shared_luck"}
TEXT_CONTENT_SHA256 = "ca8fc561e948fc1c9e2db219cadf82fbd655c5471984839c4de0c5606301b45b"
WITNESS_CONTENT_SHA256 = (
    "a42cde9985fbdeb6b3142e4b7e0ba50717a23b5caeffc21215bb3f5ec440e9e4"
)


def _pin_reviewed_content(data: dict[str, Any], expected: str, reason: str) -> None:
    """Bind reviewed literal text AND metadata, independent of JSON formatting.

    A loaded-file hash records what was read; it cannot by itself establish
    that arbitrary new words were part of the reviewed partial collation.
    """
    try:
        digest = sha256(
            json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        if digest != expected:
            raise ValueError("参评所载原文或来源身份与已核修订不符。")
    except (TypeError, ValueError) as exc:
        raise NumerologySourceError(reason) from exc


@lru_cache(maxsize=3)
def _loaded(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("参评来源须为结构化对象。")
    except (OSError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_canping_text_source") from exc
    return {"data": data, "sha256": sha256(raw).hexdigest()}


def inherited_corpus() -> dict[str, Any]:
    """Return a detached comparison corpus without exposing the loaded source."""
    data: dict[str, Any] = _loaded(INHERITED_PATH)["data"]
    return deepcopy(data)


def _collation() -> dict[str, Any]:
    data: dict[str, Any] = _loaded(COLLATION_PATH)["data"]
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
    if len(observed_keys) != len(set(observed_keys)) or set(observed_keys) - set(keys):
        raise ValueError("参评编号原图证据重复或缺少对应条目。")
    for observed in number_observations:
        entry = entries_by_key[(observed["element"], observed["provisional_number"])]
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
            or any(not isinstance(note, str) or not note for note in number_uncertain)
            or set(entry["cells"]) - uncertain.keys()
        ):
            raise ValueError("参评编号疑读须说明原因，并将该行所有已录栏目保留未定。")
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
    _pin_reviewed_content(data, TEXT_CONTENT_SHA256, "invalid_canping_text_collation")
    return data


def _verified_source(*, comparison: bool = False) -> dict[str, Any]:
    """Classify source problems separately from invalid user lookup inputs."""
    try:
        return _witness_corpus() if comparison else _collation()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError(
            "invalid_canping_witness_collation"
            if comparison
            else "invalid_canping_text_collation"
        ) from exc


def source_readings(*, comparison: bool = False) -> dict[str, Any]:
    """Detached reference data; pending readings and witness roles stay intact."""
    return deepcopy(_verified_source(comparison=comparison))


def collation_summary() -> dict[str, Any]:
    data = _verified_source()
    examined = sum(len(e["cells"]) for e in data["entries"])
    uncertain = sum(len(e.get("reading_uncertainties", {})) for e in data["entries"])
    count = examined - uncertain
    parts = {}
    for element in ("水", "火", "木", "金", "土"):
        entries = [e for e in data["entries"] if e["element"] == element]
        part_examined = sum(len(e["cells"]) for e in entries)
        part_uncertain = sum(len(e.get("reading_uncertainties", {})) for e in entries)
        total = data["total_cells"] // 5
        parts[element] = {
            "total_cells": total,
            "visually_examined_cells": part_examined,
            "collated_cells": part_examined - part_uncertain,
            "unresolved_reading_cells": part_uncertain,
            "unexamined_cells": total - part_examined,
        }
    result = {
        **{
            k: data[k]
            for k in (
                "corpus_id",
                "version",
                "source_title",
                "source_url",
                "source_pdf_sha256",
                "review_status",
                "transcription_policy",
                "scope",
                "total_cells",
                "column_rule_pdf_pages",
                "direction_rule_pdf_page",
            )
        },
        "sha256": _loaded(COLLATION_PATH)["sha256"],
        "inherited_corpus_sha256": _loaded(INHERITED_PATH)["sha256"],
        "collated_cells": count,
        "pending_cells": data["total_cells"] - count,
        "visually_examined_cells": examined,
        "unresolved_reading_cells": uncertain,
        "unexamined_cells": data["total_cells"] - examined,
        "numbered_table_visual_review_complete": examined == data["total_cells"],
        "numbered_table_clear_readings_complete": count == data["total_cells"],
        "rereading_witness": data.get("rereading_witness"),
        "additional_rereading_witnesses": data.get(
            "additional_rereading_witnesses", []
        ),
        "number_reading_witness": data.get("number_reading_witness"),
        "comparison_witness": witness_summary(),
        "part_coverage": parts,
        "corrected_number_headers": [
            {
                "element": e["element"],
                "inherited": e["inherited_wrong_number"],
                "corrected": e["number"],
                "pdf_page": e["pdf_page"],
            }
            for e in data["entries"]
            if "inherited_wrong_number" in e
        ],
        "unapplied_printed_notes": [
            {
                k: e[k]
                for k in ("printed_number", "pdf_page", "status", "applied_to_lookup")
            }
            for e in data["unapplied_notes"]
        ],
    }
    return deepcopy(result)


def text_available(text: str) -> bool:
    return bool(text) and any(c not in "○〇□ \n，。" for c in text)


def _witness_corpus() -> dict[str, Any]:
    data: dict[str, Any] = _loaded(WITNESSES_PATH)["data"]
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
    _pin_reviewed_content(
        data, WITNESS_CONTENT_SHA256, "invalid_canping_witness_collation"
    )
    return data


def witness_summary() -> dict[str, Any]:
    data = _verified_source(comparison=True)
    registered = data["entries"]
    unmatched = data.get("unmatched_observations", [])
    observed = registered + unmatched
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for entry in registered:
        key = (entry["element"], entry["number"], entry["kind"])
        grouped.setdefault(key, []).append(entry)
    for entries in grouped.values():
        entries.sort(
            key=lambda e: (
                e.get("header_pdf_page", e["pdf_pages"][0]),
                e.get("source_occurrence_id", ""),
            )
        )
    ambiguities = [
        {
            "element": key[0],
            "number": key[1],
            "kind": key[2],
            "source_occurrence_ids": [e["source_occurrence_id"] for e in entries],
            "header_pdf_pages": sorted(e["header_pdf_page"] for e in entries),
            "attribution_resolved": False,
        }
        for key, entries in grouped.items()
        if len(entries) > 1
    ]
    uncertain = sum(bool(e.get("reading_uncertainties")) for e in observed)
    parts = {}
    for element in ("水", "火", "木", "金", "土"):
        selected = [e for e in registered if e["element"] == element]
        unbound = [e for e in unmatched if e["element"] == element]
        cells = selected + unbound
        unclear = sum(bool(e.get("reading_uncertainties")) for e in cells)
        parts[element] = {
            "cells_examined": len(cells),
            "registered_counterpart_cells": len(selected),
            "registered_counterpart_keys": sum(key[0] == element for key in grouped),
            "ambiguous_counterpart_keys": sum(
                a["element"] == element for a in ambiguities
            ),
            "unmatched_observed_cells": len(unbound),
            "clear_readings": len(cells) - unclear,
            "uncertain_readings": unclear,
        }
    return deepcopy(
        {
            **{k: v for k, v in data.items() if k != "entries"},
            "sha256": _loaded(WITNESSES_PATH)["sha256"],
            "cells_examined": len(observed),
            "registered_counterpart_cells": len(registered),
            "registered_counterpart_keys": len(grouped),
            "ambiguous_counterpart_keys": len(ambiguities),
            "number_occurrence_ambiguities": ambiguities,
            "unmatched_observed_cells": len(unmatched),
            "clear_readings": len(observed) - uncertain,
            "uncertain_readings": uncertain,
            "part_coverage": parts,
            "primary_collation_count_increase": 0,
        }
    )


def _comparisons(
    element: str, number: int, kind: str, text: str, state: str, inherited_text: str
) -> list[dict[str, Any]]:
    data = _verified_source(comparison=True)
    result = []
    entries = [
        e
        for e in data["entries"]
        if (e["element"], e["number"], e["kind"]) == (element, number, kind)
    ]
    entries.sort(
        key=lambda e: (
            e.get("header_pdf_page", e["pdf_pages"][0]),
            e["body_pdf_page"],
            e.get("source_occurrence_id", ""),
        )
    )
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
                **{k: v for k, v in entry.items()},
                "source_corpus_id": data["corpus_id"],
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


def lookup_record(element: str, number: int, kind: Optional[str]) -> dict[str, Any]:
    if (
        not isinstance(element, str)
        or element not in {"水", "火", "木", "金", "土"}
        or type(number) is not int
    ):
        raise ValueError("参评选条须为明确五行及整数编号。")
    if kind is not None and (not isinstance(kind, str) or kind not in KINDS):
        raise ValueError("参评栏目仅支持male、female、luck或未选性别的None。")
    source = _verified_source()
    row = _loaded(INHERITED_PATH)["data"]["parts"][element].get(str(number))
    entry = next(
        (
            e
            for e in source["entries"]
            if (e["element"], e["number"]) == (element, number)
        ),
        None,
    )
    retired = next(
        (
            e
            for e in source["entries"]
            if e["element"] == element and e.get("inherited_wrong_number") == number
        ),
        None,
    )
    if entry and "inherited_wrong_number" in entry:
        row = _loaded(INHERITED_PATH)["data"]["parts"][element].get(
            str(entry["inherited_wrong_number"])
        )
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
            selection["number_reading_uncertainties"] = list(
                entry["number_reading_uncertainties"]
            )
            selection["number_attribution_status"] = "provisional_inherited_key"
            observed = next(
                (
                    r
                    for r in source.get("number_reading_witness", {}).get("headers", [])
                    if (r["element"], r["provisional_number"]) == (element, number)
                ),
                None,
            )
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
        if entry.get("reading_notes"):
            selection["reading_notes"] = entry["reading_notes"][:]
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
    note = next(
        (n for n in source["unapplied_notes"] if n["printed_number"] == number), None
    )
    if note:
        selection["unapplied_note"] = {
            k: note[k]
            for k in ("printed_number", "pdf_page", "status", "applied_to_lookup")
        }
    comparisons = _comparisons(
        element, number, kind, text, selection["cell_status"], (row or {}).get(kind, "")
    )
    if comparisons:
        selection["witnesses"] = comparisons
    return {"text": text, "selection": deepcopy(selection)}


def pair_resolution(shun: dict[str, Any], ni: dict[str, Any]) -> dict[str, Any]:
    same = shun["selection"]["number"] == ni["selection"]["number"]
    present = (text_available(shun["text"]), text_available(ni["text"]))
    return {
        "same_number": same,
        "distinct_numbers": 1 if same else 2,
        "local_text_availability": {
            (True, True): "both_directions",
            (True, False): "shun_only",
            (False, True): "ni_only",
            (False, False): "neither_direction",
        }[present],
        "source_rule_pdf_page": _verified_source()["direction_rule_pdf_page"],
        "independent_evidence_count": None,
        "scope": "原书允许顺有逆无或逆有顺无；此处仅统计本地所选栏的可用文本。同号为同一行，圈空、疑读、未收录、未选性别分列，均不推现实吉凶。",
    }


def selection_snapshot(verses: dict[str, Any]) -> str:
    labels = {
        "male": "上层男命",
        "female": "中层女命",
        "luck": "下层共用岁运",
        None: "本命未选性别栏",
    }
    states = {
        "source_cell_visually_collated": "单格目校，待独立复核",
        "source_printed_blank": "已核原页圈空，不作现实断言",
        "source_printed_partial_blank": "已核原页局部圈空，不补字，不作现实断言",
        "source_reading_uncertain": "目读未定；□为编辑方框而非原页圈空，此格不计已确定校勘",
        "row_absent_in_local_corpus": "本地未收录此行，未证明原典空缺",
        "inherited_blank_or_placeholder_unverified": "继承圈缺，原页待核",
        "not_selected_missing_gender": "未选男女栏",
        "inherited_transcription_unverified": "继承转录，原页待核",
    }
    lines = []
    for key, label in (("selectionShun", "顺"), ("selectionNi", "逆")):
        row = verses.get(key)
        if row:
            state = states.get(row["cell_status"], row["cell_status"])
            if row.get("number_attribution_status") == "provisional_inherited_key":
                state = "编号遮损，暂按继承键定位，号文归属未定；此格不计已确定校勘"
                if row.get("editorial_unknown_marker"):
                    state += "；正文□为编辑方框而非原页圈空"
            page = (
                f"，PDF第{row['source_pdf_page']}页"
                if row.get("source_pdf_page")
                else ""
            )
            lines.append(
                f"{label}{row['number']}·{row['element']}部·{labels[row['kind']]}：{state}{page}。"
            )
            if row.get("reading_revision"):
                lines.append("同馆藏原图复读，旧疑读另存；同一审阅者复读仍待独立复核。")
            if row.get("number_reading_evidence"):
                body_state = {
                    "source_body_visually_read": "正文可读",
                    "source_body_printed_blank": "正文为原页全圈空",
                    "source_body_printed_partial_blank": "正文有原页局部圈空",
                    "source_body_reading_uncertain": "正文仍有编辑疑读",
                }[row["body_reading_status"]]
                lines.append(
                    f"暂定继承键行的{body_state}；原图编号仍未定，整格不计入已确定数。"
                )
            if any(
                w.get("number_occurrence_ambiguous") for w in row.get("witnesses", [])
            ):
                lines.append(
                    "同一文明書局本同号有多处正文，按原页并列；号文归属未裁定，不据第一条替换主选文。"
                )
            for witness in row.get("witnesses", []):
                pages = "、".join(str(p) for p in witness["pdf_pages"])
                relation = {
                    "same_text": "该格字面相同",
                    "different_text": "与主选文字面不同，差异归因待校定",
                    "selected_reading_uncertain": "主选文有疑读，不据对读补齐",
                    "witness_reading_uncertain": "对读文有疑读",
                    "both_readings_uncertain": "两版均有疑读，继续保留未决",
                }[witness["relation"]]
                lines.append(
                    f"文明書局本对读（单次目读，PDF第{pages}页）：{witness['text']}〔{relation}；未替换本次主选文〕"
                )
    if verses.get("pair_resolution", {}).get("same_number"):
        lines.append("顺逆同号，指向同一行，不是两条独立依据。")
    lines.append(
        "○为原页圈空，□为编辑目读未定，均不补字；疑读不计入已确定校勘，不作确定解读。"
    )
    lines.append(
        "原书明言可顺有逆无或逆有顺无；本地缺条、圈空与未选栏分别记录，不据此推断现实吉凶。"
    )
    return "\n".join(lines)

"""Verify all 17 retained windows and complete delivered context apparatus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as E

N = "{http://www.tei-c.org/ns/1.0}"
XI = "{http://www.w3.org/XML/1998/namespace}id"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/sukuyo-apparatus-before-production-v77.json"
SOURCE = ROOT / "src/fatebridge/data/sukuyo_apparatus_scope.json"
REFERENCE_SHA256 = "55cd0e1a524680a76bb6022837ed8c0bd6e9ec9547edd0ef277bdcdda01fb425"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def key(node):
    return node.tag.rsplit("}", 1)[-1], tuple(sorted(node.attrib.items()))


def collect_apparatus_scope(raw, edition, windows, context_ids, legacy_keys):
    """Resolve local TEI element spans, not clock intervals or witness identities.

    The whole selected body elements remain intact. Unsupported/unresolved input
    fails explicitly, including records outside the selected windows; an unknown
    association must not be reported as a verified zero.
    """
    tree = E.fromstring(raw)
    body = tree.find(".//" + N + "body")
    if body is None or not windows:
        raise ValueError("须有正文及完整的非空行窗口选择")
    ids = {}
    events = []
    ordinal = 0
    line = None

    def walk(node, inside_note=False):
        nonlocal ordinal, line
        start = ordinal
        ordinal += 1
        if node.tag == N + "lb" and node.get("ed") == edition:
            line = node.get("n")
            if not line or any(name == line for name, _ in events):
                raise ValueError("主版本行号缺失或重复")
            events.append((line, start))
        loc = {
            "start": start,
            "start_line": line,
            "tag": node.tag.rsplit("}", 1)[-1],
            "inside_note": inside_note,
            "xml_id": node.get(XI),
        }
        if node.get(XI):
            if node.get(XI) in ids:
                raise ValueError("重复正文xml:id：" + node.get(XI))
            ids[node.get(XI)] = loc
        for child in node:
            walk(child, inside_note or node.tag == N + "note")
        loc.update(end=ordinal, end_line=line)
        ordinal += 1

    walk(body)
    lines = {
        name: (at, events[i + 1][1] if i + 1 < len(events) else ordinal)
        for i, (name, at) in enumerate(events)
    }
    ranges = {}
    for name, (first, last) in windows.items():
        if first not in lines or last not in lines or lines[first][0] > lines[last][0]:
            raise ValueError("行窗口端点缺失或倒置：" + name)
        ranges[name] = (lines[first][0], lines[last][1])
    contexts = {}
    for ident in context_ids:
        if ident not in ids or ident in contexts:
            raise ValueError("上下文xml:id缺失或重复：" + ident)
        contexts[ident] = (ids[ident]["start"], ids[ident]["end"] + 1)
    back = tree.find(".//" + N + "back")
    records = (
        []
        if back is None
        else [n for n in back.iter() if n.tag in {N + "note", N + "app"}]
    )
    parents = {id(c): n for n in tree.iter() for c in n}
    observed = []
    unlinked = []
    for node in records:
        attrs = dict(node.attrib)
        if not any(attrs.get(k) for k in ("target", "from", "to")):
            unlinked.append(node)
            continue
        resolved = {}
        for attr in ("target", "from", "to"):
            resolved[attr] = []
            for ref in attrs.get(attr, "").split():
                if not ref.startswith("#") or ref[1:] not in ids:
                    raise ValueError("未解析或不支持的正文关联：" + ref)
                resolved[attr].append({"reference": ref, **ids[ref[1:]]})
        spans = []
        if "to" in attrs and not resolved["from"]:
            raise ValueError("to不能缺少from")
        if resolved["from"]:
            a = resolved["from"]
            b = resolved["to"] or a
            if len(a) != 1 or len(b) != 1 or a[0]["start"] > b[0]["end"]:
                raise ValueError("from/to须为单一本地元素且顺序有效")
            spans.append(
                (
                    a[0]["start"],
                    b[0]["end"] + 1,
                    "from_to" if resolved["to"] else "from_element",
                )
            )
        spans.extend(
            (v["start"], v["end"] + 1, "target_element") for v in resolved["target"]
        )
        if not spans:
            raise ValueError("空正文关联")
        hits = [
            {"window": k, "association": kind}
            for a, b, kind in spans
            for k, (l, r) in ranges.items()
            if a < r and l < b
        ]
        ctx = [
            {"xml_id": k, "association": kind}
            for a, b, kind in spans
            for k, (l, r) in contexts.items()
            if a < r and l < b
        ]
        legacy = key(node) in legacy_keys
        if legacy and not hits:
            raise ValueError("旧窗口记录未能关联，不能删除或改称通过子集")
        if hits or ctx or legacy:
            observed.append(
                {
                    "kind": key(node)[0],
                    "attributes": attrs,
                    "legacy_selected": legacy,
                    "window_associations": hits,
                    "context_block_associations": ctx,
                    "resolved_endpoints": resolved,
                    "literal_with_inline_content": "".join(
                        "".join(node.itertext()).split()
                    ),
                    "xml_element": E.tostring(node, encoding="unicode"),
                }
            )
    found_legacy = {
        (r["kind"], tuple(sorted(r["attributes"].items())))
        for r in observed
        if r["legacy_selected"]
    }
    if found_legacy != legacy_keys:
        raise ValueError("旧记录缺失或身份不符")
    selected = {(r["kind"], tuple(sorted(r["attributes"].items()))) for r in observed}
    embedded = []
    for node in unlinked:
        ancestor = parents.get(id(node))
        while ancestor is not None and not (
            ancestor.tag in {N + "note", N + "app"}
            and any(ancestor.get(k) for k in ("target", "from", "to"))
        ):
            ancestor = parents.get(id(ancestor))
        if ancestor is None:
            raise ValueError("无自身关联且无具关联父记录的校注，覆盖范围未定")
        if key(ancestor) in selected:
            embedded.append(
                {
                    "kind": key(node)[0],
                    "attributes": dict(node.attrib),
                    "direct_parent_record_kind": key(ancestor)[0],
                    "direct_parent_record_attributes": dict(ancestor.attrib),
                    "xml_element": E.tostring(node, encoding="unicode"),
                }
            )
    return {
        "legacy_count": len(legacy_keys),
        "window_new_count": sum(
            bool(r["window_associations"]) and not r["legacy_selected"]
            for r in observed
        ),
        "context_only_new_count": sum(
            bool(r["context_block_associations"])
            and not r["window_associations"]
            and not r["legacy_selected"]
            for r in observed
        ),
        "legacy_not_window_associated": [],
        "window_new": [
            r for r in observed if r["window_associations"] and not r["legacy_selected"]
        ],
        "context_only_new": [
            r
            for r in observed
            if r["context_block_associations"]
            and not r["window_associations"]
            and not r["legacy_selected"]
        ],
        "all_associated": observed,
        "all_unresolved_back_record_pointers": [],
        "complete_body_id_count": len(ids),
        "window_ranges_by_document_events": ranges,
        "context_block_ranges": contexts,
        "embedded_unlinked_records_inside_selected_parents": embedded,
        "detached_unlinked_records": [],
        "duplicate_body_ids": [],
    }


def verify(captures):
    raw = FIXTURE.read_bytes()
    if sha(raw) != REFERENCE_SHA256:
        raise ValueError("改码前校注范围参考改变")
    expected = json.loads(raw)["source_data"]
    if json.loads(SOURCE.read_bytes()) != expected:
        raise ValueError("运行资料与完整改码前参考不等")
    if set(captures) != {s["capture_file"] for s in expected["sources"]}:
        raise ValueError("须提供全部八份捕获，不接受通过子集")
    old = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_upstream_dawn_sources.json").read_bytes()
    )["sources"]
    prior = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_daybreak_sources.json").read_bytes()
    )["source_data"]["sources"]
    source_rows = {s["id"]: s for s in old + prior}
    for src in expected["sources"]:
        actual = captures[src["capture_file"]].read_bytes()
        if sha(actual) != src["sha256"] or len(actual) != src["bytes"]:
            raise ValueError("来源身份改变：" + src["source_id"])
        windows = {}
        for name, window in source_rows[src["source_id"]]["windows"].items():
            if "first_line" in window:
                windows[name] = window["first_line"], window["last_line"]
            else:
                windows[name] = tuple(window["locator"].split("_", 1)[1].split("-"))
        keys = {
            (r["kind"], tuple(sorted(r["attributes"].items())))
            for r in src["all_associated"]
            if r["legacy_selected"]
        }
        observed = collect_apparatus_scope(
            actual,
            src["source_id"][0],
            windows,
            list(src["context_block_ranges"]),
            keys,
        )
        # JSON equality normalizes tuples only; no evidence field is filtered.
        observed = json.loads(json.dumps(observed))
        if any(observed[k] != src[k] for k in observed):
            mismatch = [k for k in observed if observed[k] != src[k]]
            raise ValueError(
                "完整校注关联与改码前参考不符：" + src["source_id"] + str(mismatch)
            )
    return {
        "all_eight_captures_verified": True,
        "reference_sha256": REFERENCE_SHA256,
        "source_data_sha256": sha(SOURCE.read_bytes()),
        "counts": expected["counts"],
        "all_original_windows_and_records_retained": True,
        "physical_clock_or_priority_or_full_collation_accepted": False,
        "real_samples": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", required=True)
    args = parser.parse_args()
    captures = {}
    for pair in args.capture:
        name, path = pair.split("=", 1)
        if name in captures:
            raise ValueError("重复捕获")
        captures[name] = Path(path)
    print(json.dumps(verify(captures), ensure_ascii=False, indent=2))

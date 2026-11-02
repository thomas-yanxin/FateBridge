"""Search a frozen evidence baseline without certifying source novelty.

A URI mention is not an acquisition, and a new hash is not a new witness.
Binary archives are integrity checked but explicitly left unexpanded.
"""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".txt",
    ".log",
    ".xml",
    ".html",
    ".py",
    ".yaml",
    ".yml",
    ".jsonl",
}
DIGEST = re.compile(r"[0-9a-f]{64}")
TEXT_CODECS = frozenset(
    {
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "euc_jp",
        "shift_jis",
        "cp932",
        "big5",
    }
)


def search_sources(
    root: Path, baseline: dict[str, Any], candidates: list[dict[str, str]]
) -> dict[str, Any]:
    """Return exact identity signals; no result authorizes rule adoption."""
    if baseline.get("format") != "sukuyo_frozen_source_search_baseline_v1":
        raise ValueError("unsupported frozen baseline format")
    files = baseline.get("files_sha256")
    if not isinstance(files, dict) or not files:
        raise ValueError("baseline file list is required")
    if not candidates:
        raise ValueError("candidate list is required")
    declared = baseline.get("text_encodings", {})
    if not isinstance(declared, dict):
        raise ValueError("text encoding declarations must be a mapping")
    encodings = {}
    for name, label in declared.items():
        if (
            not isinstance(name, str)
            or name not in files
            or Path(name).suffix.lower() not in TEXT_SUFFIXES
            or not isinstance(label, str)
            or not label
        ):
            raise ValueError("text encoding declaration must bind a listed text file")
        try:
            codec = codecs.lookup(label).name
        except LookupError as error:
            raise ValueError("unknown text encoding declaration") from error
        if codec not in TEXT_CODECS:
            raise ValueError("unsupported text encoding declaration")
        encodings[name] = codec
    identities: dict[str, dict[str, str]] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    for row in candidates:
        cid, uri, fingerprint = (
            row.get("candidate_id"),
            row.get("uri"),
            row.get("sha256"),
        )
        if not isinstance(cid, str) or not cid.strip() or cid in identities:
            raise ValueError("candidate IDs must be nonempty and unique")
        if not isinstance(fingerprint, str) or not DIGEST.fullmatch(fingerprint):
            raise ValueError("candidate requires a canonical SHA256 fingerprint")
        if not isinstance(uri, str):
            raise ValueError("candidate URI is required")
        parsed = urlsplit(uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("candidate URI must identify a source")
        identities[cid] = {"uri": uri, "sha256": fingerprint}
        aliases[fingerprint].append(cid)
    matches: dict[str, dict[str, list[str]]] = {
        cid: {
            "exact_uri_text_matches": [],
            "fingerprint_text_matches": [],
            "direct_artifact_hash_matches": [],
        }
        for cid in identities
    }
    base = root.resolve()
    scanned, skipped = [], []
    decoding = {}
    for name, expected in sorted(files.items()):
        if (
            not isinstance(name, str)
            or not name
            or Path(name).is_absolute()
            or ".." in Path(name).parts
        ):
            raise ValueError("baseline path must stay inside its root")
        path = base / name
        if not path.resolve().is_relative_to(base):
            raise ValueError("baseline path resolves outside its root")
        if not isinstance(expected, str) or not DIGEST.fullmatch(expected):
            raise ValueError("baseline requires canonical file fingerprints")
        if not path.is_file():
            raise ValueError(f"baseline file missing: {name}")
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f"baseline file changed: {name}")
        for cid, identity in identities.items():
            if actual == identity["sha256"]:
                matches[cid]["direct_artifact_hash_matches"].append(name)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            skipped.append(name)
            continue
        try:
            codec = encodings.get(name, "utf-8")
            text = raw.decode(codec, errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"baseline text cannot decode as {codec}: {name}"
            ) from error
        scanned.append(name)
        decoding[name] = {
            "codec": codec,
            "errors": "strict",
            "explicit": name in encodings,
        }
        for cid, identity in identities.items():
            if identity["uri"] in text:
                matches[cid]["exact_uri_text_matches"].append(name)
            if identity["sha256"] in text:
                matches[cid]["fingerprint_text_matches"].append(name)
    states = {}
    for cid, source_matches in matches.items():
        if (
            source_matches["fingerprint_text_matches"]
            or source_matches["direct_artifact_hash_matches"]
        ):
            states[cid] = "fingerprint_previously_recorded"
        elif source_matches["exact_uri_text_matches"]:
            states[cid] = "uri_previously_referenced"
        else:
            states[cid] = "not_found_in_this_text_baseline"
    return {
        "verified_files": len(files),
        "text_files_scanned": scanned,
        "text_decoding": decoding,
        "binary_files_not_expanded": skipped,
        "archives_expanded": False,
        "match_paths": matches,
        "candidate_states": states,
        "identical_candidate_fingerprint_groups": sorted(
            sorted(ids) for ids in aliases.values() if len(ids) > 1
        ),
        "independent_witness_certified": False,
        "independent_observation_count": None,
        "rule_adoption_authorized": False,
        "scope": (
            "Exact URI strings and byte fingerprints in the declared frozen "
            "baseline only. Mention does not mean acquisition or adjudication; "
            "an unseen URI/hash does not establish novelty or independence. "
            "Binary contents, URI aliases and semantic equivalents are not "
            "searched. Same-byte labels do not certify physical identity, "
            "lineage, ancient clocks, calendar priority or prediction efficacy."
            " Text uses strict UTF8 unless an explicit supported per-file encoding "
            "is declared; decoding success does not authenticate that declaration."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    baseline_raw = args.baseline.read_bytes()
    candidate_raw = args.candidates.read_bytes()
    result = search_sources(
        args.root, json.loads(baseline_raw), json.loads(candidate_raw)
    )
    result["baseline_sha256"] = hashlib.sha256(baseline_raw).hexdigest()
    result["candidate_sha256"] = hashlib.sha256(candidate_raw).hexdigest()
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()

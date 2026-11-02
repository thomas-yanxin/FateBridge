"""Retrieve registered NAJDA native regions and verify their frozen byte identity.

This developer tool does not replace the historical PDF URL or edit readings.
No requests are made unless --fetch is supplied. A changed response is retained
as unverified evidence and causes a nonzero exit, never a new reference hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COLLATION = ROOT / "src/fatebridge/data/canping/text-collation-v1.json"
COLLATION_SHA256 = "adf90d081de2cda3639964f9e16d1d1138cc379a2d3f4bacc17aee6958e4e303"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
ITEM_URL = "https://www.digital.archives.go.jp/item/3671442"


def registered_regions(path: Path = COLLATION) -> list[dict]:
    """Read only the reviewed URLs and identities from the fixed collation."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COLLATION_SHA256:
        raise ValueError(
            "Primary collation identity changed; review it before retrieval."
        )
    data = json.loads(raw)
    witnesses = [
        data["rereading_witness"],
        data["number_reading_witness"],
        *data["additional_rereading_witnesses"],
    ]
    unique: dict[tuple[int, tuple[int, ...]], dict] = {}
    for witness in witnesses:
        if witness["source_item_url"] != ITEM_URL:
            raise ValueError("A witness belongs to another catalogue item.")
        for page in witness["pages"]:
            for region in page["regions"]:
                url = urlsplit(region["url"])
                if (
                    url.scheme != "https"
                    or url.netloc != "www.digital.archives.go.jp"
                    or url.query
                    or url.fragment
                    or not url.path.startswith("/api/content/pub/da12/")
                    or not url.path.endswith("/full/0/native.jpg")
                ):
                    raise ValueError("Unexpected registered image URL.")
                key = (page["pdf_page"], tuple(region["region"]))
                row = {
                    "pdf_page": key[0],
                    "region": list(key[1]),
                    "canvas_dimensions": page["canvas_dimensions"],
                    "url": region["url"],
                    "expected_sha256": region["sha256"],
                    "witness_fixture_ids": [witness["fixture_id"]],
                }
                previous = unique.get(key)
                if previous is None:
                    unique[key] = row
                elif any(
                    previous[k] != row[k] for k in row if k != "witness_fixture_ids"
                ):
                    raise ValueError("Conflicting registered region identities.")
                elif witness["fixture_id"] not in previous["witness_fixture_ids"]:
                    previous["witness_fixture_ids"].append(witness["fixture_id"])
    return [unique[k] for k in sorted(unique)]


def retrieve_region(row: dict, output: Path, timeout: float) -> dict:
    """Keep a single response, including failures; never retry or repin it."""
    result = dict(row)
    result["started_at_unix"] = time.time()
    try:
        response = urlopen(
            Request(row["url"], headers={"User-Agent": "FateBridge-source-audit/1.0"}),
            timeout=timeout,
        )
    except HTTPError as exc:
        response = exc
    except (URLError, TimeoutError, OSError) as exc:
        result.update(
            http_status=None,
            hash_verified=False,
            error=type(exc).__name__,
            error_message=str(exc),
        )
        return result
    try:
        with response:
            result.update(
                http_status=response.code,
                final_url=response.url,
                response_headers=dict(response.headers.items()),
            )
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (TimeoutError, OSError) as exc:
        result.update(
            hash_verified=False, error=type(exc).__name__, error_message=str(exc)
        )
        return result
    oversized = len(body) > MAX_RESPONSE_BYTES
    digest = hashlib.sha256(body).hexdigest()
    verified = (
        not oversized
        and result["http_status"] == 200
        and digest == row["expected_sha256"]
    )
    region_name = "-".join(str(i) for i in row["region"])
    filename = f"p{row['pdf_page']:03d}-{region_name}"
    filename += ".jpg" if verified else ".unverified.bin"
    with (output / filename).open("xb") as target:
        target.write(body)
    result.update(
        bytes=len(body),
        actual_sha256=digest,
        hash_verified=verified,
        body_path=filename,
        response_truncated_at_limit=oversized,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--page", type=int, action="append", help="Registered PDF page"
    )
    selection.add_argument("--all-registered", action="store_true")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--plan", action="store_true", help="Print the plan without network"
    )
    action.add_argument("--fetch", action="store_true")
    parser.add_argument(
        "--output", type=Path, help="A new output directory for --fetch"
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be greater than zero and at most 60 seconds")
    rows = registered_regions()
    if args.page:
        missing = set(args.page) - {row["pdf_page"] for row in rows}
        if missing:
            parser.error(f"Unregistered pages: {sorted(missing)}")
        rows = [row for row in rows if row["pdf_page"] in args.page]
    plan = {
        "collation_sha256": COLLATION_SHA256,
        "source_item_url": ITEM_URL,
        "regions": rows,
        "policy": "Frozen bytes only; no reading, numbering, calendar or certification change.",
    }
    if args.plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        parser.error("--fetch requires --output")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    )
    results = []
    for row in rows:
        result = retrieve_region(row, args.output, args.timeout)
        results.append(result)
        # An interrupted run has per-response receipts but no completed summary.
        receipt = args.output / f"response-{len(results):03d}.json"
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {
                    k: result.get(k)
                    for k in ("pdf_page", "region", "http_status", "hash_verified")
                }
            ),
            flush=True,
        )
    passed = sum(r["hash_verified"] for r in results)
    summary = {
        "completed": True,
        "requested_regions": len(rows),
        "verified_regions": passed,
        "unverified_regions": len(rows) - passed,
        "results": results,
        "new_independent_sources": 0,
        "reading_changes": 0,
        "authority_certified": False,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

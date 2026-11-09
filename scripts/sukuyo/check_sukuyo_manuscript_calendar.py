#!/usr/bin/env python3
"""Read-only literal cell audit; nonzero includes unresolved, not calendar error."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from fatebridge.validation import sukuyo_manuscript_calendar as audit
from fatebridge.validation.sukuyo_artifacts import Artifact, read_artifact


def _publish_output(path: Path, raw: bytes) -> None:
    """Publish only completed bytes, without replacing any existing path."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix="." + path.name + ".", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--input-version", required=True)
    parser.add_argument("--evaluate-conditional-adjacency", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        binding, input_bytes = read_artifact(
            Artifact(args.input, args.input_sha256, args.input_version)
        )
        rows = binding["value"]["literal_records"]["suspected_leap_insertions"]
        report = audit.audit_month_start_insertions(
            rows, evaluate_conditional_adjacency=args.evaluate_conditional_adjacency
        )
        result = {
            "input_binding": {
                **binding,
                "bytes": len(input_bytes),
                "raw_utf8_file_text": input_bytes.decode("utf-8"),
            },
            "audit_module_sha256": hashlib.sha256(
                Path(audit.__file__).read_bytes()
            ).hexdigest(),
            "report": report,
        }
        raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            _publish_output(args.output, raw.encode("utf-8"))
        else:
            print(raw, end="")
        return audit.audit_exit_code(report)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(f"原读审核输入／输出失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

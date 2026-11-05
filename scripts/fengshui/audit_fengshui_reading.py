"""Verify a fixed Feng Shui reading using a separately retained original receipt."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.fengshui_reading import verify_fengshui_reading


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--trusted-receipt", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        receipt = json.loads(args.trusted_receipt.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(receipt, dict):
            raise ValueError("输入须为JSON对象")
        if "run_metadata" not in payload and isinstance(payload.get("payload"), dict):
            payload = payload["payload"]
        receipt = receipt.get("run_metadata", receipt)
        if not isinstance(receipt, dict):
            raise ValueError("可信回执须为完整run_metadata对象")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    report = verify_fengshui_reading(payload, trusted_run_metadata=receipt)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["status"] == "verified_served_fixed_reading" else 1


if __name__ == "__main__":
    raise SystemExit(main())

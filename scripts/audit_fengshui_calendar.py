"""Audit all frozen Li Chun years without dropping degraded or failed rows."""

import hashlib
import json
from pathlib import Path

from fatebridge.validation.fengshui_calendar import audit_lichun_reference


def main() -> int:
    folder = Path(__file__).parents[1] / "tests/fixtures/fengshui_calendar_v10"
    manifest = json.loads((folder / "provenance.json").read_text())
    integrity = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest["files"].items()
    }
    if not all(integrity.values()):
        raise ValueError(
            "Frozen reference integrity failure; no numeric acceptance claimed"
        )
    report = audit_lichun_reference(
        json.loads((folder / "period-lichun-reference.json").read_text())
    )
    print(
        json.dumps(
            {"source_integrity": integrity, **report}, ensure_ascii=False, indent=2
        )
    )
    return 0 if report["all_scoped_tt_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the fixed full public-year calendar-consumer gate in a named configuration."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from fatebridge.validation.fengshui_calendar_consumers import (
    audit_calendar_consumers,
    load_consumer_protocol,
    load_literal_month_table,
)
from fatebridge.validation.fengshui_solar_terms import load_solar_terms_reference


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", choices=["de440", "moshier"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    protocol = load_consumer_protocol(
        root / "tests/fixtures/fengshui_calendar_consumers_v1/protocol.json"
    )
    reference = load_solar_terms_reference(
        root / "tests/fixtures/fengshui_all_terms_v1"
    )
    literal = load_literal_month_table(
        root / "tests/fixtures/fengshui_monthly_v1/reference.json"
    )
    keys = ["FATEBRIDGE_SOLAR_TERM_MODEL", "FATEBRIDGE_JPL_FILE", "SE_EPHE_PATH"]
    prior = {k: os.environ.get(k) for k in keys}
    try:
        with tempfile.TemporaryDirectory(
            prefix="fatebridge-consumer-control-"
        ) as empty:
            os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = (
                "de440" if args.configuration == "de440" else "native"
            )
            os.environ["SE_EPHE_PATH"] = empty
            os.environ.pop("FATEBRIDGE_JPL_FILE", None)
            with (args.output_dir / "observations.jsonl").open("w") as log:

                def output(value):
                    log.write(json.dumps(value, ensure_ascii=False) + "\n")

                def progress(value):
                    log.flush()
                    (args.output_dir / "progress.json").write_text(
                        json.dumps(value, indent=2) + "\n"
                    )

                result = audit_calendar_consumers(
                    reference,
                    protocol,
                    literal,
                    configuration=args.configuration,
                    output=output,
                    progress=progress,
                )
            (args.output_dir / "summary.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            )
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in result.items()
                        if k not in {"consumer_failures", "numeric_failures"}
                    }
                )
            )
            return 0 if result["all_numeric_and_consumer_checks_passed"] else 1
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())

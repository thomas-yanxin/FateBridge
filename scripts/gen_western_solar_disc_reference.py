"""Append an independent high-precision source-model cohort, never candidate data.

Use uv --no-project with mpmath==1.3.0 and pyswisseph==2.10.3.2. Reduction
functions are the unchanged earlier independent producer; they import no
FateBridge code. Raw physical/frame inputs are shared, not an independent
ephemeris. The protocol is a disclosed development set frozen before this
candidate implementation, not a retrospectively renamed blind test.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import mpmath as mp
import swisseph as swe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "native-source", "ephemeris", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Reference outputs are append-only"
    protocol = json.loads(args.protocol.read_text())
    assert protocol["expected_rows"] == len(protocol["cases"]) * len(protocol["frames"])
    source = args.native_source.read_bytes()
    assert hashlib.sha256(source).hexdigest() == protocol["native_source_sha256"]
    producer = Path(__file__).with_name("gen_western_retarded_model_reference.py")
    spec = importlib.util.spec_from_file_location("independent_reduction", producer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert swe.version == protocol["native_version"]
    assert (
        module.importlib.metadata.version("pyswisseph") == protocol["binding_version"]
    )
    assert mp.__version__ == "1.3.0"
    mp.mp.dps = protocol["precision_decimal_digits"]
    text = source.decode()
    start = text.index("eff_arr[]")
    table = text[start : text.index("static double meff(double r)", start)]
    mass = [
        (mp.mpf(a), mp.mpf(b))
        for a, b in module.re.findall(r"\{(\d+\.\d+),\s*(\d+\.\d+)\}", table)
    ]
    assert len(mass) == 101
    swe.set_ephe_path(str(args.ephemeris.resolve()))
    rows = []
    for case in protocol["cases"]:
        for frame in protocol["frames"]:
            estimates = []
            for step in protocol["physical_interpolation_steps_days"]:
                data = module.collect(case, frame, step, protocol)
                estimates.append(
                    {
                        "step_days": step,
                        "raw_samples": data,
                        **module.reduce(case, step, data, mass, protocol),
                    }
                )
            difference = (
                abs(
                    mp.mpf(estimates[0]["rate_degrees_per_day"])
                    - mp.mpf(estimates[1]["rate_degrees_per_day"])
                )
                * 3600
            )
            rows.append(
                {
                    **case,
                    "frame": frame,
                    "estimates": estimates,
                    "reference_disagreement_arcsec_per_day": float(difference),
                    "reference_converged": difference
                    <= protocol["reference_agreement_line_arcsec_per_day"],
                }
            )
    assert len(rows) == protocol["expected_rows"]
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    report = {
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "native_source_sha256": protocol["native_source_sha256"],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reduction_producer_sha256": hashlib.sha256(producer.read_bytes()).hexdigest(),
        "native_binary_sha256": hashlib.sha256(
            Path(swe.__file__).read_bytes()
        ).hexdigest(),
        "precision_decimal_digits": mp.mp.dps,
        "candidate_imports": False,
        "independent_ephemeris": False,
        "independent_model_reduction": True,
        "scope": protocol["purpose"],
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "reference_converged": sum(r["reference_converged"] for r in rows),
                "maximum_reference_disagreement_arcsec_per_day": max(
                    r["reference_disagreement_arcsec_per_day"] for r in rows
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

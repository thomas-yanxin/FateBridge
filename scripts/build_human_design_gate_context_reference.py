"""Independent source-table graph facts; no engine imports or online access."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/human_design/gate_context"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
plan_bytes = (FIXTURE / "plan.json").read_bytes()
plan = json.loads(plan_bytes)
raw = (ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == plan["primary_numeric_table_sha256"]
ref = json.loads(raw)
names = {
    "Head": "head",
    "Ajna": "ajna",
    "Throat": "throat",
    "G": "g",
    "Heart": "ego",
    "Spleen": "spleen",
    "Sacral": "sacral",
    "Solar Plexus": "solar_plexus",
    "Root": "root",
}
centers = {r["gate"]: names[r["center"]] for r in ref["gates"]}
pairs = sorted({tuple(sorted(p)) for r in ref["gates"] for p in r["channels"]})
assert len(pairs) == 36
rows = []
for c in plan["cases"]:
    p, d = set(c["personality"]), set(c["design"])
    active = p | d
    complete = [e for e in pairs if all(g in active for g in e)]
    defined = {centers[g] for e in complete for g in e}
    linked = {g for e in complete for g in e}
    unpaired = active - linked
    records = []
    for g in sorted(active):
        records.append(
            {
                "gate": g,
                "center": centers[g],
                "center_status": "defined" if centers[g] in defined else "undefined",
                "expression": (
                    "active_in_defined_center"
                    if centers[g] in defined
                    else "dormant_in_undefined_center"
                ),
                "channel_completion": (
                    "in_completed_channel" if g in linked else "unpaired"
                ),
                "source_sides": [
                    s for s, v in [("personality", p), ("design", d)] if g in v
                ],
                "completed_channel_pairs": [list(e) for e in complete if g in e],
                "uncompleted_channel_pairs": [
                    list(e) for e in pairs if g in e and e not in complete
                ],
            }
        )
    rows.append(
        {
            "id": c["id"],
            "activated_gates": sorted(active),
            "active_in_defined_centers": sorted(
                g for g in active if centers[g] in defined
            ),
            "dormant_in_undefined_centers": sorted(
                g for g in active if centers[g] not in defined
            ),
            "broad_unpaired_activated_gates": sorted(unpaired),
            "defined_center_hanging_gates": sorted(
                g for g in unpaired if centers[g] in defined
            ),
            "gates": records,
        }
    )
out = {
    "method_id": "source_table_channel_subset_gate_expression_reference_v1",
    "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
    "primary_numeric_table_sha256": hashlib.sha256(raw).hexdigest(),
    "reference_imports_fatebridge": False,
    "cases": rows,
}
encoded = (json.dumps(out, indent=2) + "\n").encode()
target = FIXTURE / "reference.json.gz"
if args.check:
    if gzip.decompress(target.read_bytes()) != encoded:
        raise SystemExit("Frozen independent graph reference differs")
else:
    target.write_bytes(gzip.compress(encoded, mtime=0))
print(
    json.dumps(
        {
            "cases": len(rows),
            "uncompressed_sha256": hashlib.sha256(encoded).hexdigest(),
            "checked": args.check,
        }
    )
)

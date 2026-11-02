"""Recover identical raw requests while keeping a rejected epoch unavailable."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.audit_astrodice_horizons_wide_reference import validate

FIXTURE = Path(__file__).parent / "fixtures/astrodice-local-interval-development-v1"


def test_real_out_of_budget_epoch_stays_missing_while_other_rows_are_reused(tmp_path):
    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    protocol.update(
        cases=[
            {
                "id": "recovery-control",
                "body": "Venus",
                "date_tt": "7750-12-31T12:03:34",
                "role": "known_control",
            }
        ],
        targets={"Venus": 299},
        steps_seconds={"Venus": [10, 20]},
        explicit_offsets_seconds={"Venus": list(range(-120, 121, 10))},
        retain_rejected_epoch_rows=True,
    )
    protocol["reference_parameters"]["TLIST_TYPE"] = "'JD'"
    (tmp_path / "protocol.json").write_text(json.dumps(protocol))
    reuse = tmp_path / "reuse"
    reuse.mkdir()
    entry = json.loads((FIXTURE / "jd-rejected-request.json").read_text())
    entry["raw_file"] = "original.json"
    (reuse / "requests.jsonl").write_text(json.dumps(entry) + "\n")
    (reuse / "original.json").write_bytes(
        (FIXTURE / "jd-rejected-epoch-raw.json").read_bytes()
    )
    runner = tmp_path / "run_recovery.py"
    runner.write_text("""import json,sys
sys.path.insert(0,sys.argv[2])
from pathlib import Path
from scripts.gen_astrodice_horizons_wide import collect
import urllib.request
class Missing:
    status=200
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return b'{"error":"synthetic unavailable final six probes"}'
calls=[]
def unavailable(*args,**kwargs):calls.append(1);return Missing()
urllib.request.urlopen=unavailable
p=Path(sys.argv[1]);collect(p/'protocol.json',p/'reference.json',p/'raw',p/'reuse')
assert len(calls)==1, 'Only the absent second request may reach the fake network'
""")
    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            str(tmp_path),
            str(Path(__file__).resolve().parents[1]),
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    reference = json.loads((tmp_path / "reference.json").read_text())
    assert reference["rows"][0]["samples"]["-120"] is None
    assert reference["batches"][0]["returned_points"] == 18
    assert reference["batches"][0]["network_request_performed"] is False
    assert reference["batches"][0]["rejected_epoch_rows"] == [
        {
            "returned_jd_tt_string": "4552054.001087964",
            "reason": "outside_frozen_epoch_match_budget",
        }
    ]
    seal = {
        "protocol_sha256": hashlib.sha256(
            (tmp_path / "protocol.json").read_bytes()
        ).hexdigest(),
        "reference_sha256": hashlib.sha256(
            (tmp_path / "reference.json").read_bytes()
        ).hexdigest(),
    }
    (tmp_path / "seal.json").write_text(json.dumps(seal))
    result = validate(
        tmp_path / "protocol.json",
        tmp_path / "reference.json",
        tmp_path / "raw",
        tmp_path / "seal.json",
    )
    assert result["exit_code"] == 2 and result["complete_cases"] == 0
    assert result["cases"] == 1 and result["position_probes"] == 18

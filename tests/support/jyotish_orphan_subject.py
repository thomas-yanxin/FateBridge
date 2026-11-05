"""Synthetic owner killed by the production-boundary lifecycle regression."""

import json
import os
import sys
import time
from pathlib import Path

from fatebridge.core.astro import native_execution as execution
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india

children = []
original_start = execution.subprocess.Popen
original_receive = execution._receive


def start(*args, **kwargs):
    child = original_start(*args, **kwargs)
    children.append(child)
    return child


def receive(*args):
    result = original_receive(*args)
    if result["kind"] == "ready":
        ready = Path(sys.argv[1])
        temporary = ready.with_suffix(".pending")
        temporary.write_text(
            json.dumps({"owner": os.getpid(), "child": children[0].pid})
        )
        temporary.replace(ready)
        # Child is computing with no sample callbacks or ACK wait. The test
        # kills this owner while it is blocked here, outside Python cleanup.
        time.sleep(60)
    return result


execution.subprocess.Popen = start
execution._receive = receive
birth = build_astro_birth_info(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_timezone="UTC",
    birth_longitude=0,
    birth_latitude=0,
    preserve_instant=True,
)
build_india(birth, divisions=[], birth_time_uncertainty_minutes=120)

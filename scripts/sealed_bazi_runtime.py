"""Replay historical source audits in their complete, byte-sealed dependencies.

The historical v1 runtime is evidence for its own stage. Current v10 numerical
outputs have separate pre/post repair checks; this replay cannot certify them.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

ARCHIVE_SHA256 = "7fdde43b03ed3be39c220f389c3027811eea922b76d0aadbb48b06dfd7976744"
MANIFEST_SHA256 = "175edf7b5d6965ab60c3d9bd47347b736b2c4248888d1f599a4f6d5eab1d4524"


def replay(program: str, payload: object, root: Path) -> object:
    fixture = root / "tests/fixtures/bazi_month_duty_identity_v1"
    archive = fixture / "runtime-source.tar.gz"
    manifest = fixture / "runtime-source-manifest.json"
    if (
        hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256
        or hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
    ):
        raise ValueError("Historical Bazi runtime seal changed")
    expected = json.loads(manifest.read_bytes())["files"]
    with TemporaryDirectory(prefix="fatebridge-historical-bazi-") as directory:
        target = Path(directory)
        with tarfile.open(archive) as sealed:
            names = {member.name for member in sealed.getmembers() if member.isfile()}
            if names != set(expected):
                raise ValueError("Historical Bazi runtime population changed")
            for name, digest in expected.items():
                stream = sealed.extractfile(name)
                if stream is None:
                    raise ValueError("Historical Bazi runtime file missing")
                raw = stream.read()
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError("Historical Bazi runtime file changed: " + name)
                if name.startswith("src/fatebridge/"):
                    output = target / name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(raw)
        env = dict(
            os.environ, PYTHONPATH=os.pathsep.join((str(target / "src"), str(root)))
        )
        completed = subprocess.run(
            [sys.executable, "-c", program],
            input=json.dumps(payload, ensure_ascii=False, allow_nan=False),
            text=True,
            capture_output=True,
            cwd=root,
            env=env,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

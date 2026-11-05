"""Acquire the exact DE440 kernel required by the independent test controls."""

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    options = parser.parse_args(argv)
    source = json.loads(
        (ROOT / "src/fatebridge/data/astronomy/de440-solar-v1.json").read_text(
            encoding="utf-8"
        )
    )["source"]
    target = ROOT / "ephe/solar-de440.bsp"
    digest = (
        hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
    )
    if digest != source["kernel_sha256"]:
        if options.verify_only:
            raise ValueError("The pinned DE440 reference kernel is missing or corrupt")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=target.parent, suffix=".download")
        os.close(descriptor)
        temporary = Path(name)
        try:
            urllib.request.urlretrieve(source["url"], temporary)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if digest != source["kernel_sha256"]:
                raise ValueError(
                    "Downloaded DE440 bytes do not match the declared source"
                )
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"path": str(target), "sha256": digest, "source": source["url"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

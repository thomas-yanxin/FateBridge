"""Original source editions for historical guards; current behavior is separate.

The original reviewers still run all 127 file and 30 named AST checks, including
their tamper tests. Their identities certify this sealed edition, not the layout
of the refactored production package.
"""

import hashlib
import json
from pathlib import Path

FOLDER = (
    Path(__file__).parent / "fixtures/architecture_refactor_v1/meihua-source-originals"
)
MANIFEST_SHA256 = "1582acd6eaf71599085d979f7b941af1d52b7983ee5ea9eb8db1e94fd3ad50bf"


def original_path(relative):
    raw = (FOLDER / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    files = json.loads(raw)["files"]
    path = FOLDER / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == files[relative], relative
    return path


def original_helper(name):
    return original_path("helpers/" + name)


def historical_package_root():
    raw = (FOLDER / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    for relative in json.loads(raw)["files"]:
        if relative.startswith("package/"):
            original_path(relative)
    return FOLDER / "package"

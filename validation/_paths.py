"""Canonical repository and runtime package paths for offline validation."""

from pathlib import Path

import fatebridge

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(fatebridge.__file__).resolve().parent

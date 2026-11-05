"""Keep the initial clock evidence while proving the same edit on a parallel baseline."""

import ast
import gzip
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_clock_integration_v63"
MANIFEST_SHA256 = "3a95dcf376dab4fc55bab35d342806a7965d22ffa7dd9480a8a61d2847b521f8"


def scope_before_folder():
    return FOLDER / "scope-before"

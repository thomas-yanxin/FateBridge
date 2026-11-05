"""Literal source readings retained from the reviewed pages, without revision replay."""

import json
from pathlib import Path

FOLDER = Path(__file__).parents[1] / "data/heluo"
CURRENT_HEADERS = json.loads((FOLDER / "yaoci-collation-v1.json").read_bytes())
CURRENT_COMMENTARIES = json.loads(
    (FOLDER / "commentary-collation-v1.json").read_bytes()
)
CURRENT_CATALOGUE = json.loads((FOLDER / "numerology-sources-v1.json").read_bytes())
HEADER_COUNT = 156
PENDING_COUNT = 228
CATALOGUE_VERSION = 15
COMMENTARY_RULESET_ID = CURRENT_COMMENTARIES["corpus_id"]
ALL_HEADER_PAGES = frozenset(e["pdf_page"] for e in CURRENT_HEADERS["entries"])

"""Compatible observed Sun contexts, without claiming an exclusive read set."""

from typing import Any

from fatebridge.utils.errors import EphemerisSourceError


def sun_source(snapshot: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    ids = set(row["file_ids"])
    return {
        **snapshot,
        "by_factor": {"equatorial_Sun": row},
        "files": [f for f in snapshot["files"] if f["id"] in ids],
        "has_unidentified_sources": row["status"]
        in {"identity_unavailable", "se1_contexts_partly_identified"},
        "factor_scope": "Observed equatorial Sun context. Native slots can include auxiliary or previously opened contexts; not an exclusive or complete dependency/read-set proof. Earth rotation is separate.",
    }


class SunSourceCohort:
    """Check models, overlapping slot editions and same-name contents.

    A previously unopened auxiliary slot can appear later. Its absence from an
    earlier observation does not prove that source was unused or incompatible.
    Never fill an earlier observation with files learned from a later call.
    """

    def __init__(self) -> None:
        self.sources: list[dict[str, Any]] = []
        self._model: str | None = None
        self._editions: dict[int, set[int]] = {}
        self._hashes: dict[tuple[int, str], str] = {}

    def add(self, source: dict[str, Any]) -> int:
        model = source["by_factor"]["equatorial_Sun"]["model"]
        if self._model is not None and self._model != model:
            raise EphemerisSourceError("model_changed")
        self._model = model
        editions: dict[int, set[int]] = {}
        for file in source["files"]:
            editions.setdefault(file["slot"], set()).add(file["de_number"])
            key = (file["slot"], file["filename"])
            if key in self._hashes and self._hashes[key] != file["sha256"]:
                raise EphemerisSourceError("changed_across")
            self._hashes[key] = file["sha256"]
        for slot, values in editions.items():
            if slot in self._editions and self._editions[slot] != values:
                raise EphemerisSourceError("edition_changed")
            self._editions[slot] = values
        if source not in self.sources:
            self.sources.append(source)
        return self.sources.index(source)

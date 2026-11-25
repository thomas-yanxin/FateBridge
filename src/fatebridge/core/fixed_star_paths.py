"""Load a fixed-star catalogue independently of the physical ephemeris path."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import Iterator

from fatebridge.core.ephemeris_installation import ephemeris_path_fits
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    preserve_ephemeris_path,
)


@contextmanager
def fixed_star_catalogue(native: ModuleType, catalogue_bytes: bytes) -> Iterator[None]:
    """Load the verified bytes, then use the operator path for sky calculations.

    In Swiss 2.10.03, fixstar2_mag loads the same catalogue as fixstar2.
    set_ephe_path resets planetary files but retains those parsed star records.
    close clears the catalogue at both ends of the scope.
    """
    with preserve_ephemeris_path():
        selected = configured_ephemeris_path() or ""
        native.close()
        try:
            short_root = "/tmp" if os.name != "nt" and Path("/tmp").is_dir() else None
            with TemporaryDirectory(
                prefix="fb-star-input-", dir=short_root
            ) as directory:
                path = Path(directory)
                if not ephemeris_path_fits(path):
                    raise ValueError(
                        "Temporary fixed-star directory is not a valid Swiss path"
                    )
                (path / "sefstars.txt").write_bytes(catalogue_bytes)
                operator = os.environ.pop("SE_EPHE_PATH", None)
                try:
                    native.set_ephe_path(directory)
                    native.fixstar2_mag("1")
                finally:
                    if operator is not None:
                        os.environ["SE_EPHE_PATH"] = operator
                    # Release Swiss's open catalogue handle before removing
                    # the temporary file. The parsed records stay loaded.
                    native.set_ephe_path(selected)
            yield
        finally:
            native.close()

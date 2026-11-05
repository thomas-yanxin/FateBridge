import importlib.util
import json
from pathlib import Path

from fatebridge.core.ziwei_tables import lookup_star_brightness

FIXTURE = Path(__file__).resolve().parent / "data" / "ziwei_brightness_reference.json"
_GENERATOR = (
    Path(__file__).resolve().parents[1] / "scripts" / "gen_ziwei_brightness_fixture.py"
)


def _load_build_fixture():
    """Import ``build_fixture`` from the generator script by file path.

    Loading by path avoids depending on ``scripts`` being an importable
    package, which it is not.
    """
    spec = importlib.util.spec_from_file_location(
        "gen_ziwei_brightness_fixture", _GENERATOR
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.build_fixture


def test_our_table_matches_reference_fixture():
    reference = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert reference, "fixture must not be empty"
    mismatches = []
    for key, expected in reference.items():
        star, branch = key.split("@", 1)
        actual = lookup_star_brightness(star, branch)
        if actual != expected:
            mismatches.append(f"{key}: ours={actual} ref={expected}")
    assert not mismatches, "brightness mismatches:\n" + "\n".join(mismatches)


def test_fixture_matches_generator():
    """The committed fixture must equal the generator's current output, so a
    data edit to the generator without re-running it cannot drift silently."""
    reference = json.loads(FIXTURE.read_text(encoding="utf-8"))
    build_fixture = _load_build_fixture()
    assert (
        reference == build_fixture()
    ), "Fixture is stale — re-run: python scripts/gen_ziwei_brightness_fixture.py"

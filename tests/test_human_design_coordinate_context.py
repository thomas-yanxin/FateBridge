"""Observer origin is part of a physical value's meaning, not a new orbit."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_apparent_positions import build_context
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

REFERENCE = json.loads(
    (Path(__file__).parent / "data/human_design/coordinate-meaning.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.fixture(scope="module")
def complete():
    return execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1981,
            birth_month=12,
            birth_day=30,
            birth_hour=6,
            birth_minute=59,
            birth_timezone="Europe/London",
        ),
    )


def test_current_origin_units_vertex_and_reading_are_bound_without_native_replay(
    complete,
):
    context = complete["apparent_position_context"]
    assert {
        k: context["coordinate_context"][k] for k in REFERENCE["expected"]
    } == REFERENCE["expected"]
    assert (
        "地心处太阳视线与目标视线的夹角"
        in complete["interpretation"]["coordinate_frame_meaning"]
    )
    assert (
        "不是以太阳为原点的日心角距"
        in complete["interpretation"]["apparent_position_context"]["text"]
    )
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier recalculated an orbit"),
    ):
        assert (
            verify_human_design_reading(complete)["status"]
            == "verified_fixed_template_reading"
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "observer",
        "vertex",
        "distance_origin",
        "distance_unit",
        "rays",
        "coordinate_frame",
        "apparent_kind",
        "heliocentric_bool",
        "drop_frame",
        "drop_text",
        "drop_all",
        "unknown_drop_all",
        "forged_text",
    ],
)
def test_current_or_unknown_contract_cannot_rehash_a_wrong_origin_or_remove_it(
    complete, mutation
):
    run = deepcopy(complete)
    frame = run["apparent_position_context"]["coordinate_context"]
    replacements = {
        "observer": ("observer_origin", "sun_center"),
        "vertex": ("angular_separation_vertex", "sun_center"),
        "distance_origin": ("distance_origin", "sun_center"),
        "distance_unit": ("distance_unit", "kilometer"),
        "rays": ("angular_separation_rays", ["Earth", "target"]),
        "coordinate_frame": ("spatial_frame", "J2000_equatorial"),
        "apparent_kind": ("position_kind", "geometric_true"),
        "heliocentric_bool": ("heliocentric_coordinates", True),
    }
    if mutation in replacements:
        k, v = replacements[mutation]
        frame[k] = v
    elif mutation == "drop_frame":
        run["apparent_position_context"].pop("coordinate_context")
    elif mutation == "drop_text":
        run["interpretation"].pop("coordinate_frame_meaning")
    elif mutation == "forged_text":
        run["interpretation"]["coordinate_frame_meaning"] = "太阳角距以太阳为原点。"
    else:
        run["apparent_position_context"].pop("coordinate_context")
        prefix = run["interpretation"].pop("coordinate_frame_meaning")
        r = run["interpretation"]["apparent_position_context"]
        r["text"] = r["text"][len(prefix) :]
        r["basis"].pop()
        if mutation == "unknown_drop_all":
            run["run_metadata"]["contract_sha256"] = "0" * 64
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(run)["status"] == "rejected"


@pytest.mark.parametrize("name", REFERENCE["native_changing_flag_bits"])
def test_mixed_native_origin_flags_are_not_labelled_geocentric(complete, name):
    c = complete["apparent_position_context"]
    batches = deepcopy(c["batches"])
    batches[0]["bodies"][0]["return_flags"] |= REFERENCE["native_changing_flag_bits"][
        name
    ]
    with pytest.raises(ValueError, match="flags"):
        build_context(batches, c["nominal_side_batch_ids"])

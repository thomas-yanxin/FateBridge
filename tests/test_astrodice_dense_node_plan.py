"""Dense reference collection must not silently remove derivative probes."""

import pytest

from scripts.gen_astrodice_horizons_wide import row_points


def plan(nodes):
    return {
        "cases": [{"body": "Mercury", "date_tt": "2500-05-11T12:20:34"}],
        "steps_seconds": {"Mercury": [120, 240]},
        "explicit_offsets_seconds": {"Mercury": nodes},
    }


def test_dense_grid_keeps_all_printed_epochs_and_required_twelfth_order_nodes():
    nodes = list(range(-1440, 1441, 10))
    assert row_points(plan(nodes))[0][2] == nodes
    assert len(nodes) == 289


@pytest.mark.parametrize(
    "change", ["remove", "duplicate", "fraction", "unsorted", "boolean"]
)
def test_bad_dense_node_plan_rejected(change):
    nodes = list(range(-1440, 1441, 10))
    if change == "remove":
        nodes.remove(1440)
    elif change == "duplicate":
        nodes.append(1440)
    elif change == "fraction":
        nodes[1] = -1430.5
    elif change == "unsorted":
        nodes.reverse()
    else:
        nodes[0] = True
    with pytest.raises(ValueError, match="Invalid explicit reference node plan"):
        row_points(plan(nodes))

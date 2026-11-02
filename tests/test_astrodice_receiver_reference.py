"""The fixed angular line cannot become two separate axis permissions."""

from fractions import Fraction as Q

from scripts.astrodice_receiver_reference import source_position_control


def test_two_individually_small_components_do_not_pass_the_joint_angular_line():
    models = [
        {
            "SR_model": str(i),
            "sun_epoch_model": "fixed_test",
            "potential_term": 0,
            "model_minus_observed_arcsec": [["0.015", "0.015"], ["0.015", "0.015"]],
            "source_model_position_line_met": True,
        }
        for i in range(8)
    ]
    result = source_position_control(
        {"rows": [{"case_id": "analytic_only", "models": models}]}
    )
    assert not result["all_source_model_levels_qualified"]
    assert len(result["failed_model_nodes"]) == 8
    assert Q(result["maximum_coordinate_distance_bound_squared"]) == Q(45, 100000)

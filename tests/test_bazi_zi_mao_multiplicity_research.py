"""Evidence audits do not turn the rejected source-condition gate green."""

from scripts.audit_bazi_zi_mao_multiplicity import audit


def test_entire_candidate_scope_and_independent_arithmetic_remain_replayable():
    result = audit()
    assert result["geometry_rows"] == 20736
    assert result["independent_daystem_probes"] == 1200


def test_frozen_source_regression_prevents_adoption_despite_local_c09_success():
    result = audit()
    assert result["new_source_control_regressions"] == 1
    assert result["failed_source_control"] == "two_mao_after_binding_gap"
    assert result["candidate_adopted"] is False


def test_old19_unknowns_labels_and_formula_grades_are_not_replaced():
    result = audit()
    assert result["original19_unresolved"] == 17
    assert result["known_unknown_counts"] == [127, 281]
    assert result["production_changed"] is False


def test_post_discovery_parity_controls_cannot_replace_the_failed_original_gate():
    result = audit()
    assert result["post_discovery_parity_diagnostics"][
        "not_new_independent_accuracy_credit"
    ]
    assert result["suites"]["candidate-gate-first"]["failed"] == 3
    assert result["new_classical_accuracy_credit"] == 0

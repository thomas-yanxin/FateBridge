"""A runtime workspace must not hand the model reviewer-only answers or grades."""

import pytest

from scripts.evaluate_agent import (
    _without_evaluation_private_sections,
    prepare_workspace,
)


def test_reviewer_artifacts_stay_in_snapshot_but_outside_the_model_workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("Runtime instructions")
    paths = {
        "skills/onda-shiye/SKILL.md": "Runtime consultation skill",
        "src/fatebridge/domain.py": "Executable backend",
        "docs/contracts/bazi_birth.json": "Actual runtime contract",
        "docs/scenario-routing.md": "Runtime routing",
        "docs/numerology-audit.md": "Public calculation and source audit",
        "docs/validation/old-answer.txt": "HIDDEN_EXPECTED_ANSWER",
        "docs/validation/nested/grade.json": "HIDDEN_GRADE",
        "docs/reviews/review.md": "HIDDEN_REVIEW",
        "docs/agent-evaluation.md": "HIDDEN_EVALUATOR_CRITERIA",
        "docs/numerology-semantics-preparation.md": "HIDDEN_NUMEROLOGY_PRIOR_GRADES",
        "docs/bazi-semantics-evaluation.md": "HIDDEN_BAZI_CRITERIA",
        "docs/liuren-jinkou-audit.md": "HIDDEN_REN_FIRST_GRADES_AND_REVIEW",
        "tests/fixtures/agent_behavior/cases.json": "HIDDEN_DATASET",
    }
    for name, value in paths.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    for name, value in paths.items():
        assert (source / name).read_text() == value
        if value.startswith("HIDDEN_"):
            assert not (workspace / name).exists()
        else:
            assert (workspace / name).read_text() == value
    assert (
        workspace / ".agents/skills/onda-shiye/SKILL.md"
    ).read_text() == "Runtime consultation skill"


def test_explicit_grade_spans_are_removed_without_losing_public_source_or_limits(
    tmp_path,
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("Runtime instructions")
    for name in ("src", "skills", "docs"):
        (source / name).mkdir()
    body = (
        "Verified public source facts.\n"
        "<!-- agent-evaluation-private:start -->\n"
        "HIDDEN_PREVIOUS_MODEL_GRADE\n"
        "<!-- agent-evaluation-private:end -->\n"
        "Whole-book alignment remains incomplete.\n"
    )
    path = source / "docs/public-audit.md"
    path.write_text(body)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    visible = (workspace / "docs/public-audit.md").read_text()
    assert "HIDDEN_PREVIOUS_MODEL_GRADE" not in visible
    assert "Verified public source facts." in visible
    assert "Whole-book alignment remains incomplete." in visible
    assert path.read_text() == body


@pytest.mark.parametrize(
    "text",
    [
        "<!-- agent-evaluation-private:start -->unfinished",
        "unopened<!-- agent-evaluation-private:end -->",
        "<!-- agent-evaluation-private:start --><!-- agent-evaluation-private:start -->nested<!-- agent-evaluation-private:end -->",
    ],
)
def test_unbalanced_private_markers_fail_closed_instead_of_leaking_or_guessing(text):
    with pytest.raises(ValueError, match="Unbalanced"):
        _without_evaluation_private_sections(text)

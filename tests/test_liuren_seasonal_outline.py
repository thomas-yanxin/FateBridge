"""Source components and sparse day facts retain independent, frozen anchors."""

import copy
import hashlib
import json
import shutil

import pytest
from pydantic import ValidationError

from fatebridge.core.output_liuren_seasonal import LiurenSeasonalEvidence
from scripts.audit_liuren_seasonal_outline import (
    FIDELITY,
    OUTLINE,
    audit_outline,
    audit_sparse,
    fidelity_reference,
    outline_reference,
)


@pytest.mark.parametrize("kind", ["outline", "fidelity"])
@pytest.mark.parametrize(
    "fault", ["data", "manifest", "extra", "missing", "joint_rewrite"]
)
def test_original_source_inventory_and_pin_cannot_be_redefined(kind, fault, tmp_path):
    folder = tmp_path / kind
    shutil.copytree(OUTLINE if kind == "outline" else FIDELITY, folder)
    name = "readings.json" if kind == "outline" else "reference.json"
    if fault in {"data", "joint_rewrite"}:
        value = json.loads((folder / name).read_text())
        value["scope"] = "rewritten source"
        (folder / name).write_text(json.dumps(value))
        if fault == "joint_rewrite":
            manifest = json.loads((folder / "freeze.json").read_text())
            manifest[name] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
            (folder / "freeze.json").write_text(json.dumps(manifest))
    elif fault == "manifest":
        (folder / "freeze.json").write_text("{}")
    elif fault == "extra":
        (folder / "extra").write_text("")
    else:
        (folder / name).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        (outline_reference if kind == "outline" else fidelity_reference)(folder)


def test_all_predeclared_day_contexts_reject_wrong_power_without_derived_phase_field():
    result = audit_sparse()
    assert result["counts"] == dict(
        valid=1320,
        invalid=5280,
        valid_rejected=0,
        invalid_accepted=0,
        metadata_faults=8,
        metadata_faults_accepted=0,
    )
    assert result["sparse_checks_passed"]


@pytest.mark.parametrize(
    "value",
    [
        {"day_stem_seasonal_power": "旺"},
        {"day_ganzhi": "甲子", "day_stem_seasonal_power": "旺"},
        {"phase_powers": {"木": "休"}, "day_stem_seasonal_power": "旺"},
    ],
)
def test_missing_anchors_remain_missing_without_inventing_season_or_day_element(value):
    before = copy.deepcopy(value)
    got = LiurenSeasonalEvidence.model_validate(value)
    assert got.model_dump(exclude_unset=True) == before


def test_existing_explicit_day_phase_and_sparse_day_derived_phase_agree():
    minimal = dict(day_ganzhi="甲子", month_branch="午", day_stem_seasonal_power="休")
    for values in [minimal, {**minimal, "day_stem_element": "木"}]:
        LiurenSeasonalEvidence.model_validate(values)
        with pytest.raises(ValidationError):
            LiurenSeasonalEvidence.model_validate(
                {**values, "day_stem_seasonal_power": "旺"}
            )


def test_same_group_wrong_power_is_detected_by_literal_cells_not_just_course_groups(
    monkeypatch,
):
    from fatebridge.core.metaphysics.liureng_seasonal import POWERS

    # Spring earth is 死. Changing it to 囚 still meets 失时's broader category.
    monkeypatch.setitem(POWERS["春"], "土", "囚")
    result, _ = audit_outline()
    assert not result["components_passed"]
    assert any(
        f["kind"] == "literal_power" and f["key"] == ["春", "土"]
        for f in result["failures"]
    )
    assert any(f["kind"] == "object_power" for f in result["failures"])
    assert not result["full_named_predicate_adjudicated"]

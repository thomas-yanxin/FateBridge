"""Ziwei services render snapshots when the caller requests them."""

from unittest.mock import Mock

import pytest

from fatebridge.services import metaphysics
from tests.support.transports import SPECS, projected_outputs, rest

BIRTH = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    gender="男",
)
TIMING = dict(
    BIRTH,
    target_year=2027,
    target_month=6,
    target_day=15,
    target_hour=12,
    target_minute=37,
    target_timezone="UTC",
)
CASES = [
    ("ziwei_birth", BIRTH, "宫位总览", "build_ziwei_snapshot_text"),
    ("ziwei_horoscope", TIMING, "流年", "build_ziwei_horoscope_snapshot_text"),
    ("ziwei_rules", {"year_stem": "壬"}, "四化总表", "build_ziwei_rules_snapshot_text"),
]
SNAPSHOT_KEYS = {"snapshot_text", "snapshot_export"}


@pytest.mark.parametrize("key,arguments,title,renderer_name", CASES)
def test_snapshot_work_follows_service_request(
    key, arguments, title, renderer_name, monkeypatch
):
    spec = SPECS[key]
    renderer = Mock(wraps=getattr(metaphysics, renderer_name))
    monkeypatch.setattr(metaphysics, renderer_name, renderer)
    service, args, kwargs = spec.bind(spec.request_model.model_validate(arguments))
    facts_only = service(*args, **(kwargs | {"render_snapshot": False}))
    assert "error" not in facts_only
    assert SNAPSHOT_KEYS.isdisjoint(facts_only)
    renderer.assert_not_called()

    full = service(*args, **kwargs)
    renderer.assert_called_once()
    assert facts_only == {k: v for k, v in full.items() if k not in SNAPSHOT_KEYS}

    selected = service(
        *args, **(kwargs | {"render_snapshot": False, "selected_sections": [title]})
    )
    assert selected["snapshot_text"] == full["snapshot_text"]
    assert selected["snapshot_export"]["selected_sections"] == [title]
    assert selected["snapshot_export"]["export_text"].startswith(f"[{title}]\n")


@pytest.mark.parametrize("key,arguments,title,_renderer_name", CASES)
def test_selected_snapshot_projection_matches_across_transports(
    key, arguments, title, _renderer_name, rest, tmp_path, capsys
):
    fields = [
        "snapshot_text",
        "snapshot_export.export_text",
        "snapshot_export.selected_sections",
    ]
    replies = projected_outputs(
        SPECS[key],
        {**arguments, "selected_sections": [title]},
        fields,
        rest,
        tmp_path,
        capsys,
    )
    snapshots = [{key: reply[key] for key in SNAPSHOT_KEYS} for reply in replies]
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert snapshots[0]["snapshot_export"]["selected_sections"] == [title]
    assert snapshots[0]["snapshot_export"]["export_text"].startswith(f"[{title}]\n")

"""Lilly row evidence survives actual horary transports and strict views."""

from pathlib import Path

import pytest

from fatebridge.application.examples import evidence_views
from tests.support.transports import SPECS, three_surfaces


@pytest.mark.parametrize("view", ["rows", "lilly_fortitudes", "lilly_fortune"])
def test_lilly_evidence_crosses_real_horary_transports(
    view: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SPECS["astro_horary"]
    fields = (
        ["horary.fortitudes", "horary.fortune"]
        if view == "rows"
        else evidence_views(spec)[view]["fields"]
    )
    response = three_surfaces(
        spec,
        {
            "question_year": 2024,
            "question_month": 6,
            "question_day": 1,
            "question_hour": 14,
            "question_minute": 30,
            "timezone_name": "Asia/Shanghai",
            "longitude": 116.4,
            "latitude": 39.9,
            "category": "general",
        },
        fields,
        "2024-06-01T06:30:00Z",
        tmp_path,
        monkeypatch,
        capsys,
    )
    assert not response.get("projection_warnings")
    horary = response["horary"]
    if view in {"rows", "lilly_fortitudes"}:
        fortitudes = horary["fortitudes"]
        assert fortitudes["full_original_text_acceptance"] is False
        assert fortitudes["physical_inputs"]["status"] == "computed"
        assert len(fortitudes["summary"]) == 7
        if view == "rows":
            for planet in fortitudes["planets"].values():
                assert len(planet["rows"]) == 41
                assert all(condition["source_pages"] for condition in planet["rows"])
                assert (
                    sum(condition["contribution"] or 0 for condition in planet["rows"])
                    == planet["known_fortitudes"] - planet["known_debilities"]
                )
        else:
            assert fortitudes["full_judgement_accepted"] is False
    else:
        pass
    if view in {"rows", "lilly_fortune"}:
        fortune = horary["fortune"]
        assert fortune["full_original_text_acceptance"] is False
        assert fortune["formula"]["reverses_at_night"] is False
        assert fortune["house_assignment"]["assigned_house"] in range(1, 13)
        if view == "rows":
            assert len(fortune["rows"]) == 28
            assert (
                sum(condition["contribution"] or 0 for condition in fortune["rows"])
                == fortune["known_fortitudes"] - fortune["known_debilities"]
            )
        else:
            assert fortune["interpretation_policies"]
    else:
        pass

"""The thirty new civil dates and seam retain their literal primary labels."""

import asyncio
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from fatebridge.core import lunar_1900_prefix
from fatebridge.core.almanac import get_lunar_context
from fatebridge.validation.meihua_calendar import reference_bundle
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_lunar_1900_prefix_v1"
REFERENCE = json.loads((CORPUS / "reference.json").read_text())


def test_frozen_month_and_year_boundary_match_pmo_and_tam_publications():
    manifest = json.loads((CORPUS / "freeze.json").read_text())
    for name, value in manifest["files"].items():
        assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == value
    _, tam = reference_bundle(ROOT / "tests/fixtures/meihua_calendar_v2")
    by_date = {row["date"].isoformat(): row for row in tam}
    assert len(REFERENCE["cases"]) == 31
    for case in REFERENCE["cases"]:
        expected = {key: case[key] for key in ("year", "month", "day", "is_leap_month")}
        assert {key: by_date[case["solar"]][key] for key in expected} == expected
        actual = get_lunar_context(
            datetime.fromisoformat(case["solar"] + "T12:00:00"),
            timezone_name="Asia/Shanghai",
        )
        assert actual is not None
        assert {key: actual[key] for key in expected} == expected
        if case["solar"] < "1900-01-31":
            assert (
                actual["conversion_source"]["method_id"] == "pmo_1900_january_prefix_v1"
            )
        else:
            assert "conversion_source" not in actual


def test_finite_prefix_never_extrapolates_to_unpublished_dates():
    assert lunar_1900_prefix.convert(date(1899, 12, 31)) is None
    assert lunar_1900_prefix.convert(date(1900, 1, 31)) is None
    assert lunar_1900_prefix.source_for(date(1900, 1, 31)) is None
    assert (
        get_lunar_context(datetime(1899, 12, 31, 12), timezone_name="Asia/Shanghai")
        is None
    )


def test_corrupt_prefix_month_is_rejected(tmp_path, monkeypatch):
    raw = json.loads(
        (ROOT / "src/fatebridge/data/lunar_calendar_pmo_1900_prefix.json").read_text()
    )
    raw["lunar_month"] = 1
    (tmp_path / "lunar_calendar_pmo_1900_prefix.json").write_text(json.dumps(raw))
    monkeypatch.setattr(lunar_1900_prefix, "files", lambda _: tmp_path)
    lunar_1900_prefix._load.cache_clear()
    try:
        with pytest.raises(ValueError, match="月序或范围"):
            lunar_1900_prefix.convert(date(1900, 1, 1))
    finally:
        lunar_1900_prefix._load.cache_clear()


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("day", [1, 30, 31])
@pytest.mark.parametrize("project", [False, True])
def test_prefix_lunar_year_and_source_survive_all_ren_transports(
    key, day, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    data = dict(
        analysis_year=1900,
        analysis_month=1,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
    )
    if key == "liureng_runyear":
        data.update(
            birth_year=1900,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_timezone="+08:00",
            gender="男",
        )
    if key == "jinkou":
        data["di_fen"] = "子"
    fields = [
        "calendar_context.lunar_calendar",
        "calendar_context.lunar_calendar_support",
    ]
    if key == "liureng_runyear":
        fields += ["runyear"]
    params = [("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", field) for field in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=data, params=params)
    code, cli = call_cli(spec, data, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, data, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    expected = next(c for c in REFERENCE["cases"] if c["solar"] == f"1900-01-{day:02}")
    for body in bodies:
        lunar = body["calendar_context"]["lunar_calendar"]
        assert {k: lunar[k] for k in ("year", "month", "day", "is_leap_month")} == {
            k: expected[k] for k in ("year", "month", "day", "is_leap_month")
        }
        assert (
            body["calendar_context"]["lunar_calendar_support"]["supported_range"][
                "start"
            ]
            == "1900-01-01"
        )
        if day <= 30:
            assert (
                lunar["conversion_source"]["method_id"] == "pmo_1900_january_prefix_v1"
            )
        if key == "liureng_runyear":
            assert body["runyear"]["birth_lunar_year"] == 1899
            assert body["runyear"]["age"] == (2 if day == 31 else 1)
            assert body["runyear"]["ganzhi"] == ("丁卯" if day == 31 else "丙寅")

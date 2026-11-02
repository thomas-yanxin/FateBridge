"""Ren/Jin Kou consume the named Sun without borrowing native source flags."""

import asyncio
from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.analytic_solar import MODEL_ID
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_ren_transports import PAYLOAD


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_named_solar_model_in_ren_calendar_all_transports(
    key, project, rest, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS[key]
    payload = dict(PAYLOAD)
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    root = "jinkou" if key == "jinkou" else "liureng"
    fields = [f"{root}.calendar_policy"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", field) for field in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        policy = body[root]["calendar_policy"]
        assert policy["solar_longitude_definition"]["astronomical_model"] == MODEL_ID
        assert (
            policy["solar_longitude_definition"]["horizons_frame_equivalence_certified"]
            is False
        )
        assert len(policy["solar_term_dependencies"]) == 5
        for term in policy["solar_term_dependencies"]:
            assert term["provider"] == "fatebridge_analytic"
            assert term["ephemeris_model"] == MODEL_ID
            assert term["ephemeris_retflags"] == []
            assert term["solar_model_details"]["native_choice_probe_model"] == "moshier"
            assert term["solar_model_details"]["accuracy_certified"] is False
            assert term["solver_time_scale"] == "TT"
        assert body["run_metadata"]["engine_is_approximate"] is True
        assert not body.get("projection_warnings")


@pytest.mark.parametrize("fault", ["native_flags", "wrong_model", "missing_details"])
def test_ren_rejects_borrowed_flags_and_incomplete_analytic_identity(
    fault, tmp_path, monkeypatch
):
    from fatebridge.core.metaphysics import ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    seed = _build_analysis_seed(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    current, following = ren_calendar.get_adjacent_solar_terms(
        seed.input_datetime, seed.timezone
    )
    assert current.ephemeris_model == MODEL_ID
    changes = {
        "native_flags": dict(ephemeris_retflags=(4,)),
        "wrong_model": dict(ephemeris_model="unknown"),
        "missing_details": dict(solar_model_details=None),
    }[fault]
    monkeypatch.setattr(
        ren_calendar,
        "get_adjacent_solar_terms",
        lambda *args: (replace(current, **changes), following),
    )
    with pytest.raises(RuntimeError):
        ren_calendar.require_ren_calendar(seed)

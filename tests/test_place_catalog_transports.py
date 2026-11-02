"""New county/city coordinates and civil zones agree on REST, MCP and CLI."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize(
    "place,timezone,longitude",
    [
        ("江苏省宿迁市宿豫区", "Asia/Shanghai", 118.32),
        ("Paris, France", "Europe/Paris", 2.35),
        ("悉尼, 澳大利亚", "Australia/Sydney", 151.21),
        ("Coyhaique, Chile", "America/Coyhaique", -72.07),
    ],
)
@pytest.mark.parametrize("key", ["bazi_birth", "astro_chart"])
def test_place_only_input_infers_the_same_point_on_all_surfaces(
    key, place, timezone, longitude, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = dict(
        birth_year=2000,
        birth_month=7,
        birth_day=1,
        birth_hour=12,
        birth_minute=10,
        birth_place=place,
        gender="男",
        use_true_solar_time=True,
    )
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    points = []
    for result in [response.json(), local, protocol.structured_content]:
        info = (
            result["bazi_birth"]["person_info"]
            if key == "bazi_birth"
            else result["person_info"]
        )
        if key == "bazi_birth":
            point = info["time_adjustment"]
            points.append((point["timezone"], point["longitude"]))
        else:
            points.append((info["birth_timezone"], info["birth_longitude"]))
    assert points[0] == points[1] == points[2]
    assert points[0][0] == timezone
    assert points[0][1] == pytest.approx(longitude, abs=0.1)

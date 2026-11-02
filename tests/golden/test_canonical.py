from tests.golden.canonical import canonical_json


def test_drops_volatile_metadata_fields():
    # run_metadata 每次都变的三个字段（时间戳 + 两个 uuid）必须全部剔除，
    # 否则同一计算的基线会次次不同，安全网失效。
    a = {
        "x": 1,
        "run_metadata": {
            "generated_at": "2026-01-01T00:00:00Z",
            "run_id": "aaaaaaaa",
            "trace_id": "bbbbbbbb",
            "tool_name": "t",
        },
    }
    b = {
        "x": 1,
        "run_metadata": {
            "generated_at": "2099-12-31T23:59:59Z",
            "run_id": "cccccccc",
            "trace_id": "dddddddd",
            "tool_name": "t",
        },
    }
    assert canonical_json(a) == canonical_json(b)
    # 但有意义的稳定字段（tool_name）必须保留——不能过度剔除。
    assert '"tool_name"' in canonical_json(a)


def test_rounds_floats_to_fixed_precision():
    # 第 9 位起的差异被 8 位精度吸收 → 视为相等
    assert canonical_json({"deg": 123.12345678123}) == canonical_json(
        {"deg": 123.12345678456}
    )
    # 但第 8 位的真实差异必须保留 → 精度恰为 8，既不过粗也不过细
    assert canonical_json({"deg": 123.12345678}) != canonical_json(
        {"deg": 123.12345679}
    )


def test_sorts_keys_stably():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_scrubs_nested_lists_and_dicts():
    payload = {"items": [{"generated_at": "x", "v": 1.0000000001}]}
    out = canonical_json(payload)
    assert "generated_at" not in out
    # 嵌套在 list 里的浮点同样要被规整（1.0000000001 → 1.0）。
    assert '"v": 1.0' in out


def test_execution_receipt_scrub_cannot_hide_business_numbers_or_sources():
    a = {
        "run_metadata": {"tool_name": "fengshui_xuankong_natal"},
        "layers": {"natal": {"number": 5, "source_ids": ["X2", "X3"]}},
        "provenance": {"ruleset_version": "1.0.1"},
        "warnings": ["approximate_lichun"],
    }
    receipt = {
        "duration_ms": 8,
        "runtime": {"implementation_sha256": "changing-build"},
        "effective_time": {"as_of": "2030-01-01T00:00:00Z"},
        "business_output_sha256": "unscrubbed-hash",
    }
    b = {**a, "run_metadata": {**a["run_metadata"], **receipt}}
    assert canonical_json(a) == canonical_json(b)
    assert canonical_json(b) != canonical_json(
        {**b, "layers": {"natal": {"number": 4, "source_ids": ["X2", "X3"]}}}
    )
    assert canonical_json(b) != canonical_json(
        {**b, "provenance": {"ruleset_version": "1.0.0"}}
    )
    assert canonical_json(b) != canonical_json({**b, "warnings": []})


def test_canonicalization_cannot_manufacture_out_of_range_coordinate_values():
    import json
    import math

    values = {
        "longitude": math.nextafter(360.0, 0.0),
        "degree_in_sign": math.nextafter(30.0, 0.0),
    }
    result = json.loads(canonical_json(values))
    assert result == values
    assert result["longitude"] < 360
    assert result["degree_in_sign"] < 30


def test_canonicalization_preserves_both_sides_of_every_sign_boundary():
    import json
    import math

    for boundary in range(0, 361, 30):
        for direction in (-math.inf, math.inf):
            value = math.nextafter(float(boundary), direction)
            result = json.loads(canonical_json({"coordinate": value}))["coordinate"]
            assert result // 30.0 == value // 30.0

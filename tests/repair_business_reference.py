"""Exactly declared business repairs; all other reference leaves stay exact."""

import json
from copy import deepcopy

OLD_SIXYAO = ["起盘信息", "卦象", "六爻与动爻", "卦辞与断语"]
NEW_SIXYAO = [*OLD_SIXYAO, "原典动爻", "专业关系依据", "取用与条件证据"]


def qualify_sixyao_registry(original):
    result = deepcopy(original)
    rows = [row for row in result["techniques"] if row["key"] == "sixyao"]
    assert len(rows) == 1
    row = rows[0]
    assert row["preset_sections"] == row["settings_template"]["sections"] == OLD_SIXYAO
    row["preset_sections"] = NEW_SIXYAO[:]
    row["settings_template"]["sections"] = NEW_SIXYAO[:]
    return result


def qualify_nongli_clock_precision(original):
    result = deepcopy(original)
    clock = result["analysis_context"]
    corrected = result["birth"]
    legacy = corrected.split(".", 1)[0]
    assert clock["corrected_datetime"] == clock["effective_datetime"] == legacy
    clock["corrected_datetime"] = corrected
    clock["effective_datetime"] = corrected
    return result


def qualify_decennials_snapshot(original):
    """Remove two repeated witnesses from prose; retain every structured fact."""
    result = deepcopy(original)
    text = result["snapshot_text"]
    start = text.index("[星盘信息]\n") + len("[星盘信息]\n")
    end = text.index("\n\n[十年大运设置]", start)
    old = text[start:end]
    reference = json.loads(old)
    basis = reference["calculation_basis"]
    assert "longitude_motion" in basis and "apparent_position_policy" in basis
    basis.pop("longitude_motion")
    basis.pop("apparent_position_policy")
    new = json.dumps(reference, ensure_ascii=False, indent=2, default=str)

    def replace(value):
        if isinstance(value, str):
            return value.replace(old, new)
        if isinstance(value, list):
            return [replace(child) for child in value]
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        return value

    # Exactly the three duplicated text locations change. In particular, the
    # original structured longitude_motion and apparent_position_policy remain.
    result["snapshot_text"] = replace(result["snapshot_text"])
    result["snapshot_export"] = replace(result["snapshot_export"])
    assert result["natal_reference"] == original["natal_reference"]
    return result

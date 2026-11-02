"""The snapshot allowance must not hide unrelated interpretation changes."""

from scripts.audit_bazi_ordered_conditions import prior_facts


def test_exact_line_removed_from_all_three_declared_snapshot_locations():
    line = "原典先后复核：测试候选。"
    before = {
        "snapshot_text": "甲\n乙",
        "snapshot_export": {
            "sections": [{"content": "甲\n乙"}],
            "export_text": "甲\n乙",
        },
    }
    after = {
        "snapshot_text": f"甲\n{line}\n乙",
        "snapshot_export": {
            "sections": [{"content": f"甲\n{line}\n乙"}],
            "export_text": f"甲\n{line}\n乙",
        },
    }
    assert prior_facts(after, {line}) == before


def test_snapshot_allowance_preserves_other_strings_and_near_matches():
    line = "原典先后复核：测试候选。"
    value = {
        "ordinary_text": line,
        "snapshot_text": f" {line}\n{line}更改",
        "ordinary_section": {"content": line},
        "nested": {"snapshot_export": {"export_text": line}},
    }
    assert prior_facts(value, {line}) == value


def test_snapshot_allowance_does_not_hide_changed_old_facts_or_types():
    line = "原典先后复核：测试候选。"
    before = {"snapshot_text": "身印分列", "energy": 1, "strong": False}
    after = {"snapshot_text": f"身印已合判\n{line}", "energy": 1.0, "strong": 0}
    normalized = prior_facts(after, {line})
    assert normalized["snapshot_text"] != before["snapshot_text"]
    assert type(normalized["energy"]) is float
    assert type(normalized["strong"]) is int

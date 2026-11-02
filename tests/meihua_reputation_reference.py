"""Remove only the declared v50 additions for a frozen historical hash check.

This is not an expected-answer oracle. The independent current-before audit
retains all original mismatches and verifies every prior JSON leaf separately.
"""

from copy import deepcopy


def restore_pre_v50_reputation_supplement(result):
    restored = deepcopy(result)
    interpretation = restored["interpretation"]
    if interpretation["interpretation_topic"] != "reputation":
        return restored
    selected = interpretation["topic_reading"].pop("chapter_qualifications")
    main = selected["summary"]
    suffix = main
    for row in interpretation["casting_readings"]:
        layer = row["topic_clause"].pop("chapter_qualifications")
        text = layer["summary"]
        assert text and row["traditional_judgement"].endswith(text)
        row["traditional_judgement"] = row["traditional_judgement"][: -len(text)]
        label = "原数口径" if row["line_sum_basis"] == "raw_counts" else "卦序数口径"
        suffix += label + "求名补充另核：" + text
    assert main and interpretation["traditional_judgement"].endswith(main)
    interpretation["traditional_judgement"] = interpretation["traditional_judgement"][
        : -len(main)
    ]
    assert interpretation["comprehensive_judgement"].endswith(suffix)
    interpretation["comprehensive_judgement"] = interpretation[
        "comprehensive_judgement"
    ][: -len(suffix)]
    assert restored["summary"].endswith(suffix)
    restored["summary"] = restored["summary"][: -len(suffix)]
    scope = interpretation["evidence_scope"].pop("reputation_supplement")
    assert "selected_NLC1925_supplement" in scope
    return restored

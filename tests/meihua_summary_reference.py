"""Reverse v44 summary composition and recorded nullable weather additions."""

from tests.meihua_text_reference import restore_pre_v46_text_display

VOLUME2_PREFIX = "卷二所选《衰旺论》："
VOLUME3_PREFIX = "卷三所选《体用衰旺之诀》："
SUMMARY_SCOPE = "selected_volume2_and_volume3_parallel_conditions_no_net_priority_v1"


def restore_pre_v44_strength_summaries(result):
    result = restore_pre_v46_text_display(result)
    interpretation = result["interpretation"]
    if interpretation["interpretation_topic"] == "weather":
        for key in ["classical_text_reference", "action_hint", "risk_hint"]:
            assert interpretation.pop(key) is None
    layers = [interpretation, *(interpretation.get("casting_readings") or [])]
    replacements = {}
    for layer in layers:
        q = layer.get("seasonal_qualification")
        if q is None:
            continue
        old = q.pop("volume2_summary")
        assert q.pop("summary_scope") == SUMMARY_SCOPE
        combined = (
            VOLUME2_PREFIX
            + old
            + VOLUME3_PREFIX
            + q["volume3_qualification"]["summary"]
        )
        assert q["summary"] == combined
        assert replacements.get(combined, old) == old
        replacements[combined] = old
        q["summary"] = old
    carriers = [
        (result, "summary"),
        (interpretation, "comprehensive_judgement"),
        (interpretation, "traditional_judgement"),
    ]
    carriers += [(layer, "traditional_judgement") for layer in layers[1:]]
    for parent, key in carriers:
        text = parent.get(key)
        if isinstance(text, str):
            for new, old in sorted(
                replacements.items(), key=lambda p: len(p[0]), reverse=True
            ):
                text = text.replace(new, old)
            parent[key] = text
    return result

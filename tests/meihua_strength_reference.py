"""Remove only the predeclared v43 additive child for historical hash checks."""

from copy import deepcopy


def strip_volume3_strength_view(result):
    result = deepcopy(result)
    interpretation = result["interpretation"]
    for layer in [interpretation, *(interpretation.get("casting_readings") or [])]:
        qualification = layer.get("seasonal_qualification")
        if qualification is not None:
            new = qualification.pop("volume3_qualification")
            assert new["ruleset_id"] == "meihua_strength_exceptions_nlc1925_v1"
            assert new["version"] == "1.0.0"
    return result

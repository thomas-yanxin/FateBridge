"""Validate current documentary witnesses without replaying index migrations."""

from typing import Any

PDF_SHA256 = "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
PUBLISHER_IMAGE_SHA256 = (
    "431ca7b415d6e72c4f1492b87df112f26e6f26c6a229a810baf37387bd53359c"
)
PUBLISHER_NOTE = "出版者标注依据同一书影书名页；命式与强弱标签独立于出版身份。"
NAME_NOTE = "姓名按原页字面记录；未认定历史人物身份。"


def validate_identity_index(data: dict[str, Any]) -> None:
    """Check the current printed publisher/name facts, never an older index."""
    printed_names = {
        "ZP-PROSPECTIVE-17-MAO-HEAVY": (["壬寅", "戊申", "壬辰", "壬寅"], "馬參政"),
        "ZP-PROSPECTIVE-18-MA-LIGHT": (["己巳", "癸酉", "癸未", "庚申"], "茅狀元"),
    }
    for record in data["records"]:
        witness = record.get("source_identity_revision")
        if witness is None:
            continue
        reference = record["source_reference"]
        if (
            reference["whole_pdf_sha256"] != PDF_SHA256
            or "上海世界图书馆发行" not in reference["edition"]
            or witness["publisher_as_printed"] != "上海世界圖書館發行"
            or witness["source_pdf_page"] != 1
            or witness["source_image_sha256"] != PUBLISHER_IMAGE_SHA256
            or witness["source_strength_label_assigned_or_regraded"] is not False
            or witness["independent_expert_review"] != "not_completed"
            or witness["new_independent_validation_credit"] != 0
        ):
            raise ValueError("当前出版身份与所选书影字面不符")
        if "name_correction" in witness:
            name = witness["name_correction"]
            expected = printed_names.get(record["case_id"])
            if (
                expected != (record["pillars"], name["name_as_printed"])
                or record.get("name_as_printed") != name["name_as_printed"]
                or name["source_pdf_page"] != 73
                or name["historical_person_identity_asserted"] is not False
            ):
                raise ValueError("当前姓名必须忠于同页四柱且不宣称历史人物身份")

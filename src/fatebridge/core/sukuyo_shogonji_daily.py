"""Daily marginal positions, author emendations and separate named witnesses."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_naoj_shogonji_daily.json"


def daily_annotation_reference(
    year: int, month: int, leap: bool, day: int
) -> dict[str, Any] | None:
    if year != 1346 or leap or (month, day) not in {(6, 20), (6, 21), (8, 3), (8, 5)}:
        return None
    source = load_source(SOURCE)
    bundle = deepcopy(source.data)
    records = []
    for row in bundle["records"]:
        if row["month"] != month:
            continue
        role = (
            "original_position"
            if day == row["original_position"]["day"]
            else "author_suggested_position"
        )
        records.append({**row, "current_date_role": role})
    return {
        **bundle,
        "source_bundle_sha256": source.sha256,
        "records": records,
        "current_lunar_fields": [year, month, day, leap],
        "source_is_study_author_transcription": True,
        "original_manuscript_independently_read": False,
    }


def daily_annotation_reading(reference: dict[str, Any]) -> list[str]:
    lines = []
    for row in reference["records"]:
        original, suggested = row["original_position"], row["author_suggested_position"]
        role = row["current_date_role"]
        role_label = (
            "原始旁注所在日" if role == "original_position" else "作者建议移置日"
        )
        current = row[role]
        lines.append(
            f"荘厳寺逐日旁注对照：本参考日是{role_label}，"
            f"作者归年1346（康永五年）普通{row['month']}月{current['day']}日，"
            f"日付原读{current['day_ganzhi_kana']}，规范{current['day_ganzhi_normalized']}。"
            f"1992年研究转写第{original['printed_page']}页的「{row['annotation_literal']}」"
            f"原在{row['month']}月{original['day']}日（{original['day_ganzhi_normalized']}）日付上部栏外；"
            f"作者第232页说明{row['author_note']['number']}建议移至"
            f"{row['month']}月{suggested['day']}日（{suggested['day_ganzhi_normalized']}，"
            f"转写第{suggested['printed_page']}页）。建议位置不是原卷的实录位置，未移动旁注或修改输入日期。"
        )
    lines.extend(
        [
            "「らうさく」的汉字规范化候选为狼藉，原注本身仍是假名；研究作者归入三箇悪日。"
            "它不能当作本次T1299宿曜羅刹的观测或验算。国文研鵜飼文庫200019259、目录标文化八年刊"
            "《暦林問答集》61章题为滅門大禍狼藉，62章另题羅刹；这是不同条目。",
            "该印本64章把四种恶日的禁忌限定在三宝类仪式，余无咎；吉日仍要求支干之吉。"
            "这是该书的解释，未替换现用T1299的事项规则；61章虽称宿曜經云，也不能据此证明"
            "所引段落就在现用T1299。馬場2017研究使用天理吉田文庫本并参照中村1985校改，"
            "不等于此1811印本或未修改的原卷转写。未校全书，62章疑读前缀未擅补。",
            "国立国会图书馆解说标题作狼籍、表头作狼藉且首列为生年；未提供生年，"
            "月法也未在此核定，未删去该条件套成无条件月日规则。",
            "现用CBETA文件指纹对应2026.R2及固定提交dbdea41071e1；头部2025-01-30不是发行年份。"
            "它与2025.R1的完整text及后部校记相同，缺字声明忽略排版亦相同。"
            "本文件正文及校记的逐字检索未见狼藉／狼籍／三箇之凶／三箇之兇；"
            "这不证明一切历史传本无此文，也不替《暦林問答集》的引书归属作定论。",
            "本组仅两条旁注与四个相关日付，依据研究作者转写，未独立核原卷，未逐日抄录全历；"
            "六月建议前移一天、八月前移两天，不是统一换日修正。两条均无半日或钟时，"
            "未据此确立古代日界或闰月／小月优先级，也未改主宿或事项计算，现实预测样本仍为零。",
        ]
    )
    return lines

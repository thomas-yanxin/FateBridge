"""Catalogue candidates describe provenance; they do not supply missing readings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_hinoo_catalogue_v1.json"
FACTS_SHA256 = "53e0e33810a64208537e81caa9ad8629303ba7cfb5bfcb7ef0c287ece24dfe3c"


def validate_bundle(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("桧尾馆藏候选、目录记录及未取得状态改变，须重新核验")


def catalogue_reference(publisher_witness_note: str) -> dict[str, Any]:
    """Keep the named Taisho witnesses bound to this profile's actual note."""
    loaded = load_source(SOURCE)
    data = loaded.data
    validate_bundle(data)
    if (
        publisher_witness_note
        != data["facts"]["existing_sat_note_not_new_discovery"]["literal"]
    ):
        raise ValueError("桧尾目录候选与本次大正书目注不一致，不能继承旧候选")
    return {**data, "source_bundle_sha256": loaded.sha256}


def catalogue_lines(reference: dict[str, Any]) -> list[str]:
    facts = reference["facts"]
    hinoo = facts["kozanji_hinoo_search"]
    shukuyo = facts["kozanji_shukuyo_search"]
    return [
        "高山寺典籍文书目录检索补充：檜尾／桧尾合并检索实际返回"
        f"{hinoo['actual_returned_record_count']}条记录、"
        f"{hinoo['catalogue_group_count']}个目录组，不是8部独立写本。"
        "第四部79函85号四条记录包括摘要7131、包纸7132／7133与正文7134，"
        "正文登记建久四年写，不能冒充大正书目注的建久六年本。",
        "第四部84函1号、id7744《檜尾口決》登记鎌倉时代建久六年写、印高山寺，"
        "与既有SAT底本描述相合，只列为候选；未取得该件原图或核对题记，"
        "没有认证就是大正底本，更不是甲本。另84函2号id7745为秘密口決檜尾僧都説、"
        "84函18号id7768题名含（va jra dha tu）口決，均不能仅凭檜尾字样并为同书；"
        "84函27号id7786合题檜尾口決与高雄口決，登记享保十六年写，"
        "也不能当作建久六年本或宝历十一年甲本。",
        "宿曜检索另有"
        f"{shukuyo['actual_returned_record_count']}条目录记录全部保留；"
        "如第四部117函21号id12674《宿曜經疑義》登记永保四年写，"
        "本轮未读其原图或正文，不能由书名推出日界、闰小月规则或当作T2465见证。"
        "该检索系统自述对应目录第一至第四卷，所列简目不等于馆藏全部实物。",
        "大正大学数字档案门户分别检索檜尾与桧尾均0命中，仅是这两次关键词结果，"
        "不证明学校没有该书、甲本不存在或未数字化，也未证明智山专门学校本的现藏处。"
        "SAT原本／甲本书目注此前第十八轮已保存，本轮复核不算新发现；"
        "新目录候选不等于已经取得的京都新写本或善通寺109-4。",
        "上述高山寺及大正大学检索补充取得的是简目及检索响应，"
        "未新增这些候选的正文影像，也未完成独立人工校勘。"
        "目录年代与同名不能认证实物同一或谱系独立，未以记录数投票改宿；"
        "古代平明、桧尾半日、闰月复用与小月补配先后仍未裁定，"
        "新增独立历史观测0、真实预测样本0，当前历日和配宿按实际结果保留。",
    ]

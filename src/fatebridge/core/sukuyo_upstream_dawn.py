"""Direct Vinaya text acquisition without inventing clock or birth boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_upstream_dawn_sources.json"
DATA_SHA256 = "744af87237075bf003bbceed2def968afee781039ab6f706208b565831ff9c83"
FACTS_SHA256 = "37ee7d1b53573d74dc525d958341bf1b33de2c459574adda57200493f45d3ffa"
REFERENCE_SHA256 = "8c4d7b9ee0dd447cf8953acc79d3e63b9affb89e18243926f632e41ae004143b"


def validate_upstream_reference(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("上游来源、语境、文本层或未定控制改变，须重新核验")


def upstream_reference() -> dict[str, Any]:
    from fatebridge.core.sukuyo_apparatus_scope import apparatus_reference
    from fatebridge.core.sukuyo_matanga_time import matanga_time_reference
    from fatebridge.core.sukuyo_sanskrit_editions import sanskrit_edition_reference

    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("上游原文资料身份改变，须重新冻结来源")
    validate_upstream_reference(loaded.data)
    return {
        "id": loaded.data["id"],
        "source_data": loaded.data,
        "source_bundle_sha256": loaded.sha256,
        "source_bundle_hash_scope": "source_data_only_v76",
        "apparatus_coverage": apparatus_reference(),
        "before_code_reference_sha256": REFERENCE_SHA256,
        "baseline_acquisition_flags_describe_round": 75,
        "matanga_time_comparison": matanga_time_reference(),
        "sanskrit_edition_comparison": sanskrit_edition_reference(),
    }


def upstream_lines(reference: dict[str, Any]) -> list[str]:
    from fatebridge.core.sukuyo_matanga_time import matanga_time_lines
    from fatebridge.core.sukuyo_sanskrit_editions import sanskrit_edition_lines

    validate_upstream_reference(reference["source_data"])
    return (
        [
            "本轮已取得《律二十二明了論》《善見律毘婆沙》《十誦律》的具名电子本和《行事鈔諸家記標目》目录。旧来源快照的未取得标记属于第75轮，不能追溯改写成当时已取得；当前取得状态按本轮选段分别说明，具体引本尚未认证。",
            "《律二十二明了論》所见东方已赤，是安居五缘的第三项，位于正文的行内释文，前有解五能成夏住因的偈文；不能抽成所有事项通用的换日定义。《善見律毘婆沙》阿留那出时、汉言明相出现在过十日衣物舍堕的解释中，阿在0772a02末，留那在0772a03首，跨行连接；Aruṇuggamana.是所报外语后置脚注，不是汉字正文中的另一独立见证。其离衣宿叙述也有明相出而成离宿的条件，不能直接移为出生历日界。",
            "已取得《十誦律》电子本文并定位地了时用例。比丘尼独宿戒的正文行内释文作：夜者，從日沒至地未了，是中間名夜；独行戒的释文作：晝日者，從地了至日未沒，是中間名晝日。同段又分别列地了时、日出时、日出已，未将它们校成一个现代钟点；端点开闭、现代刻制、太阳高度与T1299平明对应均未确立。所读电子正文及释文中，‘見地色分了’完整原句尚未定位；这不证明别本或其他语境绝无此义，也不完成转引谱系校勘。卷五正文署弗若多羅譯，与题头及卷四十二的共羅什譯分别保留。",
            "《十誦律》的有闰处、无闰处及闰春末月，处在雨浴衣与安居时令的规则中；《善見律毘婆沙》听数胎月、闰月数、十四日布萨则处在受具足戒年数的语境。两段都不能据此裁定宿曜闰月复用、小月缺日补配先后，或改写一般出生年龄与历日算法。",
            "《行事鈔諸家記標目》电子题头署宋慧顯集、日本戒月改錄，正文直接署戒月改錄；其目录另著录行事鈔音義指歸三卷，并接宋京兆天壽寺通慧大師贊寧述。目录不是被著录的三卷正文，尚未取得其中二刻或掌文的对应原段；目录编改者、被著录书述者及短称指歸的具体引本身份各自保留。以上正文行内释文、note行内注、原注/改注及app分别记录，未认证亲见各版印字或全部原典。",
        ]
        + matanga_time_lines(reference["matanga_time_comparison"])
        + sanskrit_edition_lines(reference["sanskrit_edition_comparison"])
    )

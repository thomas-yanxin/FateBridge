"""Named source months and diagnostic table projections, never date conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "sukuyo_month_names.json"
T1299_SOURCE = DATA_DIR / "sukuyo_t1299_days.json"


def month_name_reference(rizang: dict[str, Any]) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    if data["source_files_sha256"]["T13n0397.xml"] != rizang["source_sha256"]:
        raise ValueError("月名对照与日藏具名版本不一致，须重新核验")
    t1299 = load_source(T1299_SOURCE).data
    if data["source_files_sha256"]["T21n1299.xml"] != t1299["source_sha256"]:
        raise ValueError("月名对照与T1299具名版本不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def month_name_lines(reference: dict[str, Any]) -> list[str]:
    months = (
        "",
        "正",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
    )
    named = "、".join(
        f"{r['named_month_literal']}为唐{months[r['Tang_month_label']]}月"
        for r in reference["Tang_named_month_annotations"]
    )
    example = reference["conditional_white_ninth_comparison"]
    counter = reference["single_bull_counterexample"]
    same = reference["projection_literal_equal"]
    different = reference["projection_literal_different"]
    return [
        "月名层原注：T1299上卷0388a07—18区分大唐建寅与天竺建卯，"
        "以白十五望宿名月，并明确列出："
        f"{named}。这12项与下卷表定十五日望宿的数月标签相合，"
        "不能将文中天竺、唐及不同来源的数月标号一概视为同一换历规则。",
        "日藏正月白十五角可通过原注角月对唐二月作具名对读；"
        f"若声明比较白月日序，日藏正月白九{example['mansion_literal']}与"
        f"T1299数月二月白九{example['T1299_27_literal']}形成条件性相合。"
        "原日藏正月没有改名，玄应只写二月九日仍未明确白黑分及历制，"
        "此对应未识别其实际引本，也未解决八／九日的古代日界。"
        "T2216实际选段0053b11另释黒前白後，0053b17仍保留梵暦不一純歟、是非難知的疑问，"
        "不是全印度历法统一的证明。",
        "11个显式白十五端点中10个可按同字宿名接到原注唐月名；"
        "日藏十一月七星与T1299星月唐十二月分字串保留，"
        "未将字串不同判成不同物理星宿。八月昴只是叙述锚点，可对原注昴月唐九月，未补成逐日表。"
        f"仅按事先声明的白月月号加一、黑月月号不变且日号加十五作表序比较，330槽{same}字面相合、"
        f"{different}不同，全槽均保留；T1299一侧是下卷27宿规则推得的对照值，不是逐日原文表格实录。"
        f"例如日藏正月黑十原字{counter['mansion_literal']}，所比较的T1299规则推得正月二十五"
        f"{counter['T1299_27_literal']}。"
        "不能以端点相合推成330槽算法相同，也不能拆牛女／女虛来消掉差异；"
        "比较计数的分母固定为全部330个文本槽，80个不同项没有从分母中剔除。",
        "当前T1299档案继续直接采用已声明宿主农历月及其表定望宿，不能因上述月名对应再给宿主月份加一。"
        "这不是已接纳的日期转换，没有由循环月号换算年份、闰月、日界、半日或补配优先，"
        "没有移动当前历日、主宿、候选或双向关系。",
    ]

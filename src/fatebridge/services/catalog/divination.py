"""Divination tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.meihua_clock_binding import meihua_time_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.output_meihua_cast import MeihuaCastOutput
from fatebridge.core.requests.compatibility import SukuyoCompatibilityRequest
from fatebridge.core.requests.divination import (
    CanpingRequest,
    GuaLookupRequest,
    GuaMeiyiRequest,
    HeluoRequest,
    MeihuaAnalysisRequest,
    OtherBuRequest,
    SanShiUnitedRequest,
    SixYaoRequest,
    SuZhanRequest,
    TongSheFaRequest,
)
from fatebridge.core.requests.meihua import MeihuaCastRequest

calculate_canping_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_canping_analysis"
)


calculate_gua_lookup = lazy_service(
    "fatebridge.services.divination", "calculate_gua_lookup"
)


calculate_gua_meiyi = lazy_service(
    "fatebridge.services.divination", "calculate_gua_meiyi"
)


calculate_heluo_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_heluo_analysis"
)


calculate_meihua_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_meihua_analysis"
)
calculate_meihua_cast = lazy_service(
    "fatebridge.services.meihua", "calculate_meihua_cast"
)


calculate_otherbu_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_otherbu_analysis"
)


calculate_sanshiunited_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_sanshiunited_analysis"
)


calculate_sixyao_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_sixyao_analysis"
)


calculate_sukuyo_compatibility = lazy_service(
    "fatebridge.services.divination", "calculate_sukuyo_compatibility"
)


calculate_suzhan_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_suzhan_analysis"
)


calculate_tongshefa_analysis = lazy_service(
    "fatebridge.services.divination", "calculate_tongshefa_analysis"
)

SPECS: List[ToolSpec] = [
    # --- Divination --------------------------------------------------------
    ToolSpec(
        key="gua_lookup",
        bind=raw_invoke(calculate_gua_lookup),
        request_model=GuaLookupRequest,
        summary="卦象查询：传单个卦名或卦码，返回该卦的六十四卦义理；要一次查多卦用 gua_meiyi。",
        operation_label_zh="卦象查询",
        family="divination",
        rest_path="/api/divination/gua",
        mcp_name="gua_lookup",
    ),
    ToolSpec(
        key="gua_meiyi",
        bind=raw_invoke(calculate_gua_meiyi),
        request_model=GuaMeiyiRequest,
        summary="卦义批量查询：传一组卦名/卦码（List），一次返回多卦义理；单卦查询用 gua_lookup。",
        operation_label_zh="卦义",
        family="divination",
        rest_path="/api/cn/gua/meiyi",
        mcp_name="gua_meiyi",
    ),
    ToolSpec(
        key="meihua_analysis",
        bind=meihua_time_invoke(calculate_meihua_analysis),
        request_model=MeihuaAnalysisRequest,
        summary=(
            "梅花时间起卦：按所选公历钟时与时区查农历取数，返回本变互卦、"
            "固定体卦下的初中终生克、季令与原文来源；"
            "闰月、换年换日约定随结果列明；interpretation_topic=weather选天时条款，不以体用断天气。"
            "仅支持时间法，传统提示不保证现实成败。"
        ),
        operation_label_zh="梅花易数",
        family="divination",
        rest_path="/api/divination/meihua",
        mcp_name="meihua_analysis",
        cli_request_file=True,
    ),
    ToolSpec(
        key="meihua_cast",
        bind=raw_invoke(calculate_meihua_cast),
        request_model=MeihuaCastRequest,
        output_model=MeihuaCastOutput,
        required_output_fields=(
            "analysis_type",
            "input_normalized",
            "meihua",
            "interpretation",
            "summary",
        ),
        summary=(
            "梅花原始资料起卦与已有卦解读：物件数量、两段声音、端法取象、丈尺/尺寸、"
            "所报字形笔画、传统四声、字数（默认至百字，影印百余字需显式依据并保留范围未定），或已有卦码及单动爻。"
            "也接收明确农历年支月日时与已报加数lunar_time_added_count；不猜姓氏笔画。"
            "不猜笔画读音、观察取象或时间；公历时间换算用meihua_analysis。"
            "天时解释显式选interpretation_topic=weather，条件资料用weather_context。"
        ),
        operation_label_zh="梅花显式起卦",
        family="divination",
        rest_path="/api/divination/meihua/cast",
        mcp_name="meihua_cast",
        cli_request_file=True,
    ),
    ToolSpec(
        key="tongshefa",
        bind=raw_invoke(calculate_tongshefa_analysis),
        request_model=TongSheFaRequest,
        summary=(
            "统摄四卦组合：按实际给定的 taiyin/taiyang/shaoyang/shaoyin "
            "组合左右卦、潜藏与亲和；不实现蓍草十八变或大衍随机起卦，固定默认不是用户起卦。"
        ),
        operation_label_zh="通蓍法",
        family="divination",
        rest_path="/api/divination/tongshefa",
        mcp_name="tongshefa",
    ),
    ToolSpec(
        key="sixyao",
        bind=raw_invoke(calculate_sixyao_analysis),
        request_model=SixYaoRequest,
        summary=(
            "六爻纳甲：问一件具体事能不能成（需明确一事一方向）；"
            "method=coin 真·摇钱起卦（系统随机六掷，可传 coins 报真实掷果或 seed 复现）；"
            "传 gua_code/lines 用已摇之卦，未传则按起卦时刻自动时间起卦；"
            "focus_kind 区分明爻、实际变爻、伏神、日月，focus_line/focus_kinship 明确取用；"
            "event_horizon 可明确近事near或久远long_term以审进退，未给保持待定；"
            "月令、动静、生克、三合与飞伏均附条件，timing_days 列已实现的日级候选，未综合断现实成败。"
            "按指定问时取数用 meihua_analysis，问方位谋略用 qimen。"
        ),
        operation_label_zh="六爻",
        family="divination",
        rest_path="/api/divination/sixyao",
        mcp_name="sixyao",
    ),
    ToolSpec(
        key="canping",
        bind=raw_invoke(calculate_canping_analysis),
        request_model=CanpingRequest,
        summary=(
            "邵子参评数 / 金锁银匙：需明确性别，默认卷六日支起数，命名选择卷七附子平配运，支持带时区时刻查询及年内交运分段；提供规则依据与条文，现实预测效力未验证。"
            "普通命格画像用 analyze_destiny 或 ziwei_birth，仅深追问才调。"
        ),
        operation_label_zh="邵子参评数",
        family="divination",
        rest_path="/api/divination/canping",
        mcp_name="canping",
    ),
    ToolSpec(
        key="heluo",
        bind=raw_invoke(calculate_heluo_analysis),
        request_model=HeluoRequest,
        summary=(
            "河洛理数：须明确性别；天地数、元堂、先后天卦、大限和影印规则流年月日卦序，附逐条爻辞校勘状态与日期映射限制；现实预测效力未验证。"
            "普通命格用 analyze_destiny 或 ziwei_birth，仅深追问才调。"
        ),
        operation_label_zh="河洛理数",
        family="divination",
        rest_path="/api/divination/heluo",
        mcp_name="heluo",
    ),
    ToolSpec(
        key="suzhan",
        bind=raw_invoke(calculate_suzhan_analysis),
        request_model=SuZhanRequest,
        summary=(
            "宿占：农历二十七宿、七曜及T1299事项条文；钟时可未知，保留历法候选；星图和天文28宿需已知钟时，默认采用现代视赤经不等宽研究宿界；"
            "解读已有占星骰面用 otherbu，中式起卦用 sixyao 或 meihua_analysis。"
        ),
        operation_label_zh="宿占",
        family="divination",
        rest_path="/api/divination/suzhan",
        mcp_name="suzhan",
    ),
    ToolSpec(
        key="sukuyo_compatibility",
        bind=raw_invoke(calculate_sukuyo_compatibility),
        request_model=SukuyoCompatibilityRequest,
        summary="宿曜双人相性：农历月日定二十七宿，T1299三九法双向关系；闰月保留候选。",
        operation_label_zh="宿曜合盘",
        family="compatibility",
        rest_path="/api/compatibility/sukuyo",
        mcp_name="sukuyo_compatibility",
    ),
    ToolSpec(
        key="otherbu",
        bind=raw_invoke(calculate_otherbu_analysis),
        request_model=OtherBuRequest,
        summary=(
            "占星骰面解读：必须提供实际planet/sign/house，house为0..11索引（实际第N宫传N-1）；"
            "支持日月、八行星、南北交点及中英名称/符号；返回符号依据、七曜星座关系、喜乐宫和规则来源。"
            "时间地点可省略；提供时仅生成独立天象背景。无随机抽骰、精确应期或经验证的预测概率。"
        ),
        operation_label_zh="其他卜法",
        family="divination",
        rest_path="/api/divination/otherbu",
        mcp_name="otherbu",
    ),
    ToolSpec(
        key="sanshiunited",
        bind=raw_invoke(calculate_sanshiunited_analysis),
        request_model=SanShiUnitedRequest,
        summary=(
            "三式合参：太乙年/月/日/时计、六壬和奇门时刻盘，按真实方位对应五将与星门神；日计明确采用金钥匙积日及十精，保留异数和未决。"
            "六壬贵人表可显式选择，实际起点与金镜明钞／四库当时法逐版对照，朝暮边界及完整联合断法另核。"
            "尚无已验证的联合事件预测规则，不生成综合胜率或独立投票结论。"
        ),
        operation_label_zh="三式合参",
        family="divination",
        rest_path="/api/divination/sanshiunited",
        mcp_name="sanshiunited",
    ),
]

# 八字时运：交运边界、关系证据与准确性审计

本页对应当前源码开发分支。历法归属、传统关系、工程计权与现实效果是四种不同证据；结果可复算不等于现实预测有效。

[起运整数展示修复](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-dayun-integer-age.md)另保留先取两位再向上取整的一岁误差与首次失败。`start_age_unrounded`是同次折算原值，旧名`start_age_precise`仍是两位展示，`start_age`为向上取整、至少1岁的整数展示；实际选运继续比较`start_at/end_at`，不能由整数4推成四周岁生日交运。完整矩阵验证状态单独记录，不替代既有历法与原典门槛。

## 时运取值与边界

| 盲区 | 原实现怎样改变结果 | 当前处理 |
| --- | --- | --- |
| 用整数周岁选大运 | 自动取已满年龄，再减起运岁数；实际交运后仍可能停留在旧运数月 | 默认按分析时刻与交运起止比较，区间含起点、不含终点 |
| 过早舍入起运与累计年数 | 起运先保留两位，再把累计年数舍入后整除10，临界点可能选错一步 | 内部保留未舍入间隔，显示值最后舍入；日期选择直接比较边界 |
| 大运只算八步 | 超过默认80年覆盖便无可用大运 | 时运服务给出十二步时间轴及覆盖状态，期数不表示寿命 |
| 两条底层路径忽略立春 | 综合分析及流月补流年时只传公历年，1月会错用新年干支 | 传目标时刻与时区，统一按立春解析 |
| 综合时运缺省年月用了固定时区 | 跨时区跨年时，可能把上海的1月当成命主当地仍在12月的当前月份 | 缺省年月统一读取出生民用时区的冻结时钟 |
| 固定十神、合冲评分 | 正印固定加分、七杀固定扣分、合吉冲凶，不核对原局喜忌与救应 | 分数返回 `null`、吉凶返回“未判定”，保留实际关系与所缺条件 |
| 把百分比变化当力量变化 | 五项占比重新归一后，按上升项数量判断“整体力量增强” | 改为“结构占比变化”，公布计数口径，不能解释成旺衰或吉凶 |
| 时间层彼此缺少关系证据 | 单层元素加入不能表达原局两支遇流年补全合局等结构 | 增加保留位置的原局—时运、时运—时运关系图 |
| 尚未起运变成接口错误 | 有效查询得到错误包络，交运信息不能作为正常结果读取 | 独立大运工具返回 `before_dayun`、空当前柱和完整时间轴 |

主要实现：[`core/timing.py`](../src/fatebridge/core/timing.py)、
[`analysis/timing_effects.py`](../src/fatebridge/analysis/timing_effects.py)、
[`services/timing_state.py`](../src/fatebridge/services/timing_state.py)。

## 交运换算的明确口径

`three_days_one_year_calendar_v1` 以[《三命通会·卷二·论大运》](https://zh.wikisource.org/zh-hant/三命通會/卷二#論大運)的三日折一年、十年一运为传统依据。
实际计算采用年干阴阳与已确认性别定顺逆；顺行找严格晚于出生的下一“节”，逆行找不晚于出生的上一“节”。“节”指十二月令边界，不是任意一个中气。

1. 在出生民用时区解析真实出生瞬间；出生到参考节的间隔用UTC历时，不用真太阳钟替换这一物理间隔。
2. 每一物理秒折为120个名义秒；名义360日折一年、30日折一月，分解成年、月、日及不足一日的余量。
3. 将这些年月日一次加到出生民用日期，使用公历月份加法；这是本版本工程约定。秒级延拓同样属于工程约定，不能声称古籍认证了秒级应期。
4. 每步大运的十年边界分别从首运锚点计算，避免闰日逐步截断造成累积偏移。派生重复钟时默认取 `fold=0`，不存在的当地钟时向前移过缺口；但首运不能早于已确认出生瞬间。如果默认选择违反这一条件，改用核验有效且不早于出生的较晚一次，并返回 `dst_policy=fold_0_gap_forward_initial_not_before_birth`；不存在有效选择时明确失败。后续十年锚点沿用原默认政策，未确认的出生重复钟时仍拒绝猜测。

首运重复钟时修复（本地数据：`validation/bazi-dayun-initial-fold-v1.md`）保留正间隔却排到出生前的实际程序反例、完整1,296行队列和零间隔控制。它修正首运的实际瞬间选择，不改三日一年、未舍入年龄、数值旺衰或原典标签。

出生恰在交节、日历加法、固定年长、虚实岁和其他流派的分歧需要按所选口径比较，不能静默混用。本版本没有提供所有流派的可切换实现。

`start_age_precise` 仍是两位显示值，内部另存 `start_age_unrounded`；选运以 `start_at/end_at` 为准。
`start_age` 保留旧版向上取整显示，不能用它反算交运日。
按日期查询返回的累计及本运年数按365.2425日折年供显示，**不参与选运**。
`reference_term_resolution` 保留参考节实际来自星历还是线性降级；降级结果不可解读为同等精度。

### 一个确实会改柱的回归例

虚构输入：1990年5月15日10:30，男，`Asia/Shanghai`，关闭真太阳时；查询2028年1月20日12:00。
按上述版本的参考节与日历加法，乙酉运从2027年8月31日19:06开始。
旧版取已满37岁，仍选甲申；新版按时刻选乙酉。
这一差异源于选运时钟与交运换算，不是新加了某种吉凶评分，也不说明现实会发生某事件。

显式 `analysis_age=37` 仍可查询旧式“年龄参考”，并返回 `selection_basis=explicit_age_reference`。
它不等价于任意一个实际日期；独立大运工具禁止同时传年龄与分析日期。
综合工具的显式年龄覆盖仍保留，用于调用者明确构造的参考场景，返回相同的依据标识。

## 岁运关系证据

综合时运的 `interaction_analysis` 采用 `natal_timing_relations_v1`：

- 节点区分原局年、月、日、时与大运、流年、流月、流日、流时；重复的同字地支仍保留为不同位置。
- 每个时间柱列出对日主的透干十神、支中藏干十神及原局同五行根的位置。根的存在与有效根力分开。
- 识别天干五合、有方向的五行克、地支六冲、六合、六害、子卯刑、自刑、完整三刑与不完整三刑候选。
- 检查三合、三会、含中神的半合、同柱重见、岁运并临，以及本版本明确定义的天克地冲结构。
- 原局两支遇时间柱补全三合，与同一个时间柱冲原局另一支，可以同时保留。半合、完整合局、六合的多个关系视图不做叠加计分。

每条关系有 `rule_id`、参与位置、作用域和状态；返回来源、`rule_trace` 与未覆盖项。
刑冲会合的传统依据见[《三命通会·卷二》](https://zh.wikisource.org/zh-hant/三命通會/卷二)相应章节；关系表、完整三刑门槛及天克地冲定义是本版本的明确形式化范围，不能代表所有门派。
合局匹配统一保留 `transformation=not_assessed`，不把配对或三支齐全直接判成合化、救应或吉运。
通用的同柱重见提示也不能替代古籍特定位置下的“伏吟／返吟”判断。

当前年度、月度或小时层同时出现，只说明查询时刻下各层的关系。不能用流时命中解释全年，也不能把年度关系细化成某日必然应验。

## 出生时刻范围与解释忠实

`timing_analysis` 和 `dayun_analysis` 接受可选 `birth_time_uncertainty_minutes`（0至120的整数分钟）。只有用户确认范围后才提供；省略参数不代表生时精确，0表示只核对名义分钟。范围以出生真实瞬间为中心，按UTC历时每分钟采样，保留DST重复钟时的两个瞬间；真太阳时四柱归一与交运民用日期分别计算。未消歧的重复或不存在的出生钟时会报错，需要明确UTC偏移，不能静默取第一遍。

返回的 `birth_time_sensitivity` 保留四柱候选、顺逆、目标时刻的大运候选及各步交运边界范围。`stable_on_minute_grid` 只表示采样的本命四柱、顺逆和当前大运未变；交运日期本身仍可随输入变化，见 `boundary_ranges_vary`。逐分钟采样没有证明两分钟之间的秒级稳定性，候选频次也不是概率。

历史偏移变更可能让派生本地钟时出现非零秒。范围采样保留每个实际瞬间的秒数，原始秒数未知的事实仍保留；不能把名义00秒参考重新套到所有派生钟时。修复前对照与尚未补齐的中间事件候选见[派生秒数与漏采事件](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-derived-clock-audit.md)。

综合时运未提供性别时仍核对四柱范围和独立流年等时间层；只将顺逆与交运范围标为不可计算，列入 `unavailable_fields`。四柱未变时返回 `partial`，不能将未计算的大运写成已核对稳定。

例如上述1990年虚构生时声明±1分钟，在2027年8月31日19:06查询，即使四柱相同，也会得到甲申／乙酉两个当前大运候选。文字快照明确单盘部分对应名义生时，列出已知候选与范围提示；不能只解读其中一个交运时刻。工具未提供任意未知生时反推或秒级连续区间证明。

```bash
uv run --locked --extra dev fatebridge dayun_analysis \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-timezone Asia/Shanghai --use-true-solar-time false \
  --analysis-year 2027 --analysis-month 8 --analysis-day 31 \
  --analysis-hour 19 --analysis-minute 6 --birth-time-uncertainty-minutes 1 \
  --fields dayun_info birth_time_sensitivity --strict-fields true \
  --include-snapshot-text false --response-char-limit 0
```

## 使用方式

下列命令使用源码锁定环境；输入为虚构回归例。

```bash
uv run --locked --extra dev fatebridge dayun_analysis \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-timezone Asia/Shanghai --use-true-solar-time false \
  --analysis-year 2028 --analysis-month 1 --analysis-day 20 --analysis-hour 12 \
  --fields dayun_info timing_context --strict-fields true \
  --include-snapshot-text false --response-char-limit 0

uv run --locked --extra dev fatebridge timing_analysis \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-timezone Asia/Shanghai --use-true-solar-time false \
  --analysis-year 2028 --analysis-month 1 --analysis-day 20 --analysis-hour 12 \
  --fields interaction_analysis dayun_analysis liunian_analysis \
  --strict-fields true --include-snapshot-text false --response-char-limit 0
```

REST 对应 `/api/timing/dayun` 和 `/api/timing/comprehensive`；`fields`、`strict_fields` 是查询参数。
MCP 对应 `dayun_analysis`、`timing_analysis`，参数来自同一请求模型。
日期全部省略时，综合、流月、流日、流时及独立大运使用冻结时钟的完整当地瞬间，保留偏移、fold和秒微秒；不再替换为月初、月中或零点。`analysis_reference`记录实际比较时刻与补齐来源。提供部分日期时仍沿用各工具原补齐约定；独立大运缺年取当地当前年，缺月日取1，缺时分取0。显式不存在或重复的分析墙钟须消歧，已确认UTC瞬间通过`as_of`表达并保持出生时区，详见[分析瞬间修复](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-analysis-instant.md)。
完整导出不投影，按默认响应预算及 `result_delivery` 读取同一run。
任务字段视图 `interactions` 和 `dayun_timeline` 只是选字段参考，不是新请求参数。

## 验证范围与未决门槛

新增回归分别验证物理间隔换算、生日之前的真实交运、边界前后、过早舍入、DST、闰日、立春、位置关系与反例。
三端测试核对完整业务JSON、字段投影、显式年龄与日期冲突、未起运状态及冻结时钟回执；实际stdio子进程亦完成选运调用。

2026-10-22 首轮本机工程验收（macOS arm64 / Python 3.12）：全量 **4120通过、91跳过**；Black、isort、全源码mypy、文档链接、生成合同与场景检查均通过，wheel/sdist构建成功，新模块已核对入包。后续生时范围、原典资格及现实评估模块的验收分别记录，不沿用该数字代替新检查。
7份时运黄金快照只更新已审查的业务变化，未变化的历法和节气字段已与旧快照比对一致；**Linux x86_64参考环境的黄金字节验收尚未执行**。
真实模型多轮咨询与既有桌面连接重新加载未作为本轮已通过项；stdio结论来自当前源码启动的新子进程。

香港天文台独立夹具（本地数据：`../tests/fixtures/bazi-timing-hko-2026.json`）从已发布的[2026十二中气表](https://www.hko.gov.hk/en/gts/astron2026/files/2026SolarTerms24.pdf)和[二月月历](https://www.hko.gov.hk/en/gts/astron2026/files/2026cal02.pdf)整理13个时刻，未由生产输出生成。
首轮全部落在发表到分钟的60秒容差内，最大差异29秒。后续扩展到2026–2028年全部72个节气时刻（本地数据：`../tests/fixtures/calendar_hko_v1/reference.json`），保留官方原始XML及散列；72项均在60秒容差内，最大差异30秒，另在上海及纽约核对144项交节与中气边界。它仍不覆盖所有年份或术数解释。

既有[独立原典审计](bazi-assessment.md#原典对照基准与未覆盖范围)首轮为10例月令格局匹配8例；校正禄刃资格与有限杂气会支条件后增至9例，当前共享实现再补入有限的正官财印条件后名称匹配10例。这10例已用于开发，不能再称盲测。3例原文明示强弱仍匹配1例；7例强弱原文未裁定；`classical_acceptance_passed=false`、`real_world_efficacy=not_tested`。逐项边界与新增评估器见[四项独立验收](prediction-validation.md)。
未改冻结命例与预期，也未通过重新定义通过率隐藏分歧。

深入时运的下一层仍有以下实质缺口：

| 优先级 | 缺口 | 成立前所需的验证 |
| --- | --- | --- |
| 高 | 用神／相神、成格破格与制化救应的独立结构裁定 | 先解决当前原典分歧，冻结完整前提与反例，不能靠固定十神优先表 |
| 高 | 运来后根气、争合、解冲与流通的有效变化 | 保留原局月令与各时间层作用域，限制同一根气重复消费；不能把时间柱当新增本命柱直接拼入旺衰模型 |
| 高 | 人元分日司令、寒暖燥湿及调候剂量 | 明确作者、版本、日数与节令边界；不同司令表须分版本验证 |
| 中 | 连续秒级生时区间与未知生时 | 已实现用户声明范围的逐分钟候选；连续区间仍需边界求解与独立验证，不能把采样结果当连续秒级证明 |
| 中 | 小运、空亡填实、合冲先后与其他流派换算 | 各方法分立，纳入有来源的完整案例；不自动补成所有门派共识 |
| 独立任务 | 对现实结果的预测效度 | 预注册、外部样本、基线比较及可证伪指标；原典一致性和工程测试均不能替代 |

本次提供可核对的交运与结构证据。现有五维指数仍是工程模型，不能作为概率或权威认证。

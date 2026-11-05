# 月紫白：十二节月与独立月盘

`monthly_zibai_jie_v1@1.0.0` 返回中性的月星数字、名称、五行和九宫落位。独立工具为 `fengshui_monthly_stars`；合参显式选择 `methods=["monthly_stars"]`，或提供 `monthly` 输入。月盘、年盘、历史宅盘分别保留，不改变历史定运，也不以月星覆盖床门取用、年星作者规则或现场条件。

## 输入与时间

两种输入方式互斥：

- 含时区的 `query_at` 与显示用 `timezone_name`，按实际交节瞬间计算。
- `effective_solar_year` 与 `solar_month_number` 成对，由调用方独立确认。1为立春寅月，11为大雪子月，12为下一公历年的小寒丑月；不是公历或农历月份，没有第13月。

不传时返回 `partial`；不取当前日期。合参显式选择月层而省略 `monthly` 时，只复用顶层的实际 `query_at/timezone_name`；顶层只有 `effective_year` 时不能补出节月。显式 `monthly` 有自己的查询或确认资料，不被顶层年度覆盖。自动选法不会仅因传了年度查询时刻而额外选月层。

换月用立春、惊蛰、清明、立夏、芒种、小暑、立秋、白露、寒露、立冬、大雪、小寒十二个节，中气不换月。起点含、终点不含；跨时区比较实际瞬间，重复钟时保留明确偏移。公历2027年1月10日属于2026午年的第12节月，入中为六，而不是按2027未年套表。

`time_context.timing` 分别报告起止交节的求解器、实际星历模型、TT与民用时标政策、未来闰秒假设。选定模型无法取得交点时返回错误，不用线性近似补出节月；Moshier在计算交节前后5秒保留候选，不给唯一节月或月盘。候选共用的有效年仍可保留，立春节界同时保留前后有效年；远离边界仍可计算并保留模型限制。独立确认的有效年／节月也需要实际交点才能交付其有效区间。

5秒是工程候选保护窗口，不是原典口诀、宣称的误差上界或更宽的验收门槛。独立Skyfield/JPL DE440对1800–2200年全部4,812个十二节TT交点的一秒门槛保持不变：完整Swiss文件配置全部通过，最大差约0.115秒；Moshier的569项失败与最大约2.455秒差异完整保留。这个窗口防止在已知较弱模型的极近边界把错误月份写成唯一结果，不把保留候选算作数值通过或现实命中。年星、命卦和跨20年宅运边界共用相同保护，只有日期的命卦还保留窗口跨过的相邻民用日。完整Swiss配置与独立确认输入仍可计算，未来实际UTC闰秒和历史时标限制另行保留。

交节待确认时，唯一 `valid_from/valid_until` 也为null；`provisional_interval` 单列模型暂取窗口，`candidate_months` 逐项保留候选区间及起止实际模型。端点的 `full_resolution_path` 指向同次 `candidate_boundary_resolutions` 中的完整交节记录。需完整逐根依据时，首次选入该记录或设 `fields=null`，再读同run分页；分页不能恢复首次投影舍弃的字段。固定释义列出各候选有效期，不把暂取窗口当已确认月份。字段、虚构示例与验收见[月区间分层](../../../docs/fengshui.md)。

## 来源与差异

- MP1：《沈氏玄空学》玄空辑要，沈竹礽编、王则先辑要，姚国华与柯誉整理；中央编译出版社2011年版、2016年重印，ISBN978-7-5117-0801-4。完整PDF的SHA-256固定，PDF731三组年支的36个入中数逐项核对，原表图像与独立转录一并保留。
- MP2：[Sean Chan署名网页](https://www.masterseanchan.com/fengshui-2026-flying-star-chart/)，2026-09-24更新、2026-10-22读取；核对节瞬间换月、立春前归前一有效年及2026年十二张月盘，不采用其中事件与处方断语。
- MP3：[香港天文台节气时刻表](https://www.hko.gov.hk/en/gts/astronomy/Solar_Term.htm)，只核对冻结年份的节气与公布分钟，不证明风水规则或任意年份秒精度。

MP1的六月节候栏原印“大暑、小暑”，与标准时间顺序相反。保留原图及原始标签，时序独立按小暑起月、大暑为中气；不能把重排后的表冒充原书。该差异使原表历法标签的全符合状态保持false。助手视觉转录没有替代独立人类专家校勘，限定表格一致也不认证整本或现实效果。

## 结果与释义

读取 `layers.monthly_stars`，保留 `rulesets/rule_trace`。`center_star_number` 和 `palaces.*.monthly_star_number` 是本节月飞星，`palace_number` 是固定宫数。月星名称和五行共享固定数的身份，不继承基础年星表中的通用吉凶标签。

`position_reading@1.0.0` 包含一条年／月／有效期说明和九条逐宫固定文本。每条有精确 `target_path`、完整时间与来源的 `basis_paths/basis`；只消费同次返回值，不重算月份或星盘。资料缺失或交节待确认时，仅说明缺项／候选，不给唯一月盘。完整原始响应与从执行端另外保管的完整回执，可交给 `fatebridge.validation.fengshui_monthly.verify_monthly_reading` 核验。通过须先满足月表数字、逐宫数式和区间上下文的内部一致性，再核对固定文本与原run；不表示历法独立精度、自由模型改写或现实预测通过。

布局只按物件已确认的**位置**读取月星；朝向不能替代位置。`usage_interpretation=not_covered_not_inauspicious` 表示本版没有月星用途与行动规则，不判该宫不利，不生成搬动、摆水、施工或物件处方。候选方案在各自新位置重新读取同一时间月盘，不能沿用旧位置星数。

`derived_monthly_numeric_consistency_verified`只给实际完整月盘；内部矛盾停止交付。保存的旧错误回执、新独立检查及完整公开年份分支验收见[月盘数式与历法消费端](../../../docs/fengshui.md)。候选保护通过仍不能抵消Moshier的数值超差，也不认证额外自由文字或现实效果。

## 调用

```bash
uv run --locked --extra dev fatebridge fengshui_monthly_stars \
  --query-at '2027-01-10T12:00:00+08:00' --timezone-name Asia/Shanghai
```

REST为 `POST /api/fengshui/monthly_stars`，请求体可用 `{"effective_solar_year":2026,"solar_month_number":12}`。MCP名称为 `fengshui_monthly_stars`，参数以当前工具Schema为准。完整原始响应按初次请求范围读取同run交付，不能重算旧输入来替代原始回执。

三端比较须使用同一星历配置。由客户端启动stdio MCP子进程时，自定义 `SE_EPHE_PATH` 应显式写入该服务器的 `env`；标准MCP客户端只继承有限环境变量，不能假定它会转发宿主的自定义星历路径。核对实际返回的 `ephemeris_model` 和文件回执：Moshier与完整Swiss配置可能给出不同交节时刻，工具同名本身不证明后端一致。

完整TT实现对照可离线复核：

```bash
uv run --locked --extra dev python scripts/audit_fengshui_monthly_calendar.py \
  --reference tests/data/fengshui_monthly_v1/jie-de440-tt.json.gz \
  --output /tmp/fengshui-monthly-tt-audit.json
```

该命令按实际选中的星历配置运行；Moshier失败仍非零退出。参考文件散列、全部4,812行和固定一秒门槛均核对，不能删失败年份、替换参考数据或加宽门槛取得通过。参考由独立环境中的收集脚本生成，不导入FateBridge；内核与工具版本固定，不包含于运行wheel。

# 八字星历模型、派生缓存与同次历法依据

本次修复让四柱、流月和流日窗口的缓存使用与节气求解相同的星历环境标识，并在综合及九专题公开实际节气来源。它修复环境切换后沿用旧结果的矛盾，不把提供者可用或缓存一致当作独立精度认证。

## 复现与修复

在当前提供者下，1904-01-06 17:37 UTC处于两个模型的小寒交气时刻之间。加载Swiss数据文件时，边界为17:37:01.212146；Moshier为17:36:59.500387。修复前，在同一进程先使用完整文件、随后切入Moshier，新的节气上下文已进入丑月，四柱与流月仍从缓存返回子月，流日所附窗口也沿用旧值。

这个例子是跨环境一致性反例，不是以程序自身充当独立天文标准。修复后，派生缓存键纳入星历求解的环境标识；切换过去、切换回来都跟随相应环境。该标识使用选定路径、库身份及文件元数据，能够识别通常的安装与配置变化，不构成文件字节持续不可变的证明，也不解决所有计算步骤之间发生并发安装的事务问题。

## 公开依据

每个公开节气记录现在同时给出：

- `resolution_provider`：`swisseph`为数值求解库，`linear_1900_fallback`为粗略线性回退；八字计算拒绝后者和未知来源。
- `ephemeris_model`：实际返回标志所示的`swieph`、`moshier`或其他明确模型；不能从目录存在或请求标志推断实际模型。

九专题的`<topic>_analysis.calendar_context`复用该次出生计算已生成的上下文，不重新排盘。十个公开入口均提供`calendar_basis`证据视图，调用时将其中的`fields`复制为参数；视图名本身不是请求参数。首轮主题摘要不强制带上完整历法块，需要核对时可以投影同次依据。指定大运、流年覆盖也保留出生历法依据。

运行元数据根据实际业务结果识别Moshier，并保留`engine_is_approximate=true`、`approximate_engine`警示及实际模型来源；投影字段不会把底层模型重新标为完整精度。`false`也仅表示未识别到已声明的降级模型，不证明原典、UTC精度或全局正确。

```bash
# 明确为虚构测试资料；核对公开节气来源字段。
fatebridge bazi_career --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender male --use-true-solar-time false \
  --analysis-year 2026 --analysis-month 10 --analysis-day 12 \
  --fields career_analysis.calendar_context.current_solar_term \
  --strict-fields true --include-snapshot-text false
```

完整Swiss文件的安装与路径配置见[快速入门](getting-started.md#星历数据与精度)。精度必须结合[全部节气TT比较](bazi-all-terms-audit.md)看待：首轮完整文件4,872点均在1秒门槛内，Moshier有501点未达门槛；不得因来源信息已完整而抹去这个分歧。来源标签补充没有修改Moshier的数值模型。

## 交付预算

大量安装文件曾使运行回执本身超过4,096字预算，并挤掉默认首轮事业分析。现在超长运行环境在同一run的不可变结果中完整保留，行内返回环境散列、原清单散列、文件数及`run_metadata.runtime.delivery_path`，`result_delivery.deferred_fields`明确列出`run_metadata.runtime`。读取该路径可恢复完整回执及每个文件的散列；不会将未显示清单标为空，也不会重新计算。

压缩依据是运行环境整体大小，不仅是文件清单长度；实际清单为空时，较长的依赖与实现清单也可触发同一规则。文件数仍按真实库存计算。

综合时运的默认首轮投影使用`dayun_analysis.first_view`，它保留当前大运、日期依据、状态、精度与方法，只省去`timeline.periods`的完整十二步表。该表仍在同次`dayun_analysis.timeline.periods`内；完整输出不删表，未知性别、未交运和明确年龄基准也保留各自状态。该改动缩减默认业务投影，并曾在定向环境通过10,000 UTF-8字节门槛；后续加载完整星历清单的联合检查仍返回10,997字节，原门槛保持失败，不能视为所有环境的体积问题已解决。

预算为0的完整输出不变。默认预算下的九专题实际分析仍需直接可读；只要求叶字段的投影契约测试另外使用三端一致的无限预算，完整清单与预算逻辑分别测试。详见[API交付约定](api-reference.md#25-字段投影与输出体积)与[同次完整读取](agent-guide.md#完整结果交付与同次导出)。

完整目标状态仍见三项目标要求（本地数据：`validation/bazi-three-axis-requirements.json`），本轮证据见本地运行记录（本地数据：`validation/bazi-classical-routes-local-verification.json`）。

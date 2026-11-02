# 候选节月与各自有效期一并保留

[历法边界](fengshui-calendar.md) · [月紫白规则](../skills/onda-fengshui/references/monthly-stars.md) · [事件有效年分层](fengshui-event-year-fidelity.md)

交节保护区内，月层原已返回候选年／月并停止生成唯一月盘，但有效期仍是模型暂取月份的一套起止，只有 `interval_scope` 标注暂取。现在唯一 `valid_from/valid_until` 为null，每个候选节月保留自己的完整区间和实际交节来源。

| 字段 | 交节待确认时的含义 |
| --- | --- |
| `effective_solar_year` | 候选共用的有效年仍保留；跨立春有两个有效年时为null |
| `solar_month_number`、`month_branch` | 均为null，不把暂取月份升级为唯一结果 |
| `valid_from`、`valid_until` | 均为null，不把一套有效期写成已确定区间 |
| `provisional_interval` | 模型暂取年／月、月支及起止；仅追踪本次分侧 |
| `candidate_months` | 按时间顺序返回各候选年／月、月支、起点含与终点不含的区间 |
| 候选的 `start_resolution/end_resolution` | 实际时刻、求解器、模型、时标政策及同次完整来源路径 |
| `candidate_boundary_resolutions` | 按年／节月键保存完整交节记录，包括解析模型的逐根细节 |
| `timing.interval_basis` | `provisional_solar_month`，原起止记录仍仅对应暂取月份 |

相邻候选共享的端点指向同次来源。逐根解析模型说明较长，候选端点以 `full_resolution_path` 指向完整记录，避免四次重复展开。若需完整逐根依据，首次请求应选入 `candidate_boundary_resolutions` 或设 `fields=null`；分页只能恢复该次实际保留的响应，不能恢复被首次投影舍弃的字段。随后读取同run的 `result_delivery`，不能另算一次冒充原始依据。默认MCP预算不增加，两个候选及所选区间事实仍须在首轮可读。

立春候选可为上一有效年第十二节月与新有效年第一节月；小寒两侧则同属上一有效年的第十一、十二节月。同年内换月不能因月份不确定而清空已确定有效年。非边界和显式确认年／节月的原有输出、入中数与九宫飞布保持不变。

固定 `position_reading` 列出同次候选的年／月及各自有效期，说明暂取区间不表示月份已确认；不补月盘、不取当前日期。每条仍绑定同次完整时间上下文。既有历史partial响应未含新候选区间时，保留原通用说明，可继续按原回执核验。

## 可复现的虚构输入

[示例](examples/fengshui-month-interval-candidates.json)是原生Moshier计算根附近的回归输入，不是住宅资料，也不认证该秒为真实交节时刻。显式使用原生模型和空目录，并核对实际模型；自动模式可能选择具名解析模型。

```bash
mkdir -p /tmp/fatebridge-v26-empty-ephe
SE_EPHE_PATH=/tmp/fatebridge-v26-empty-ephe FATEBRIDGE_SOLAR_TERM_MODEL=native \
  uv run --locked --extra dev fatebridge fengshui_monthly_stars \
  --request-file docs/examples/fengshui-month-interval-candidates.json \
  --fields layers.monthly_stars.status \
    layers.monthly_stars.time_context.effective_solar_year \
    layers.monthly_stars.time_context.solar_month_number \
    layers.monthly_stars.time_context.valid_from \
    layers.monthly_stars.time_context.valid_until \
    layers.monthly_stars.time_context.candidate_months
```

预期partial、无唯一年／月或有效期，候选为2024年第十二节月和2025年第一节月。每个候选均有起止时刻、实际模型和同次完整记录路径。

## 合同指纹的导入顺序

收尾的独立进程检查发现，输出的宅盘朝向原写 `Literal["true", "magnetic"]`，输入及其他领域声明写 `Literal["magnetic", "true"]`。枚举接受值相同，类型缓存却会使Schema枚举顺序及八工具合同指纹随导入顺序变化。现在声明统一为磁北、真北的同一顺序，不排序或改写已产生的历史回执。

两个不同哈希种子下，分别先导入目录或先导入风水服务的独立进程回归，修复前均失败、修复后均通过。月区间修复阶段的原始Schema完全相同比对继续保留；最后这项修复对原始Schema造成的八处枚举顺序差异也如实记录，接受值和必要输出根不变，不把原始散列差异隐藏成“字节完全一致”。

## 验证范围

```bash
uv run --locked --extra dev pytest -q tests/test_fengshui_month_interval_fidelity.py tests/test_fengshui_contract_import_order.py
```

检查覆盖实际原生Moshier、实际具名解析模型及具名模拟回退，立春／惊蛰／小寒两侧、±5秒闭端点与±6秒、显式月份、显示时区、固定释义、历史响应、REST／实际FastMCP协议／CLI一致性及默认MCP预算。模拟回退只验证状态传递，不计独立天文样本。

五秒候选政策、一秒数值验收、既有原典差异和日时选局未决项均不改变。本次验证不授予整本符合、自由模型解释或现实预测成绩。完整运行记录见第二十六轮证据（本地数据：`validation/fengshui-month-interval-v26-evidence.json`）。

最终隔离回归2,456项通过、零失败和跳过，6,238个冻结文件运行后不变。新增70项月区间检查、两项跨进程合同检查，并扩展一项空文件但大模型政策的交付场景；原始失败、第二次通过与最终类型声明修复后的第三次通过分别保存。

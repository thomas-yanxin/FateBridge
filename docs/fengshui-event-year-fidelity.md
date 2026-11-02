# 事件有效年与宅运的不确定性分别保留

[历法边界](fengshui-calendar.md) · [玄空合同](fengshui-xuankong.md) · [边界模型](fengshui-model-boundary-fidelity.md)

立春操作保护区内，事件有效年可能仍为两个候选。若两个候选年同属一个历史二十年运，宅运可确定；这不能把模型暂取年升级为已确认事件年。共享年界、玄空定运、年盘、命卦、快照和固定释义现在保留这一层次。

## 问题与修复

此前共享 `year_context` 已返回 `effective_year_status=requires_confirmation` 和两个候选年，但同时保留唯一 `effective_year`、`valid_from` 与 `valid_until`。年盘和命卦在调用处清空年数，未清空这段单一有效期；定运在非二十年换运年份则直接把暂取年写入 `effective_event_year`。于是同一结果既说有效年待确认，又像是确认了唯一有效年或年度区间。

| 2025立春保护区内的虚构事件 | 现在返回的事实 |
| --- | --- |
| 事件有效年 | `effective_event_year=null`，状态待确认；候选2024、2025 |
| 暂取年 | 单独的 `provisional_effective_event_year`，仅追踪本次模型分侧 |
| 历史宅运 | 两个候选年均属九运，`number=9`、`resolution_status=resolved` |
| 定运范围 | `resolution_scope=period_number_only_event_year_unconfirmed` |
| 年盘与命卦 | 仍为partial，未产生唯一年盘或命卦；年度有效期不再冒充唯一 |

共享时间上下文在不确定时，`effective_year`、唯一 `valid_from/valid_until` 均为null；`provisional_effective_year` 保留模型暂取值。`candidate_year_intervals` 逐年保留候选有效期及起止实际交节来源。旧 `timing` 的起止分辨记录明确以暂取年为依据，不表示该年已确认。

跨运时，同样从全部候选有效年映射历史运区间，返回 `number=null`、`candidate_period_numbers` 和 `timing.candidate_period_intervals`，不保留一套貌似唯一的运区间起止。2024年是八、九运候选，2044年按历史顺序为九、一运，不能把运号数值排序成一、九。两个年份同运时继续输出确定宅盘，不因无关的年份不确定性阻断计算。

确认 `effective_event_year` 或 `period_number` 的原有输入合同保持有效。非边界时刻、历史纪元、运号公式、飞布和角度选择不变；五秒操作保护及一秒数值实现验收也没有调整。候选保护不是误差上界、源历法满分或现实预测认证。

## 可复现的虚构示例

[示例输入](examples/fengshui-event-year-candidates.json)的时刻由本轮实际Moshier立春求解取得，仅用于回归，不是住宅资料。要重现Moshier操作区，须显式选择原生模型及空目录，并核对实际返回模型；自动模式或完整Swiss文件可选不同模型，不能只凭目录或标签断定。

```bash
mkdir -p /tmp/fatebridge-v25-empty-ephe
SE_EPHE_PATH=/tmp/fatebridge-v25-empty-ephe FATEBRIDGE_SOLAR_TERM_MODEL=native \
  uv run --locked --extra dev fatebridge fengshui_xuankong_natal \
  --request-file docs/examples/fengshui-event-year-candidates.json \
  --fields layers.xuankong_natal.status \
    layers.xuankong_natal.period_context.number \
    layers.xuankong_natal.period_context.effective_event_year \
    layers.xuankong_natal.period_context.candidate_effective_event_years \
    layers.xuankong_natal.period_context.resolution_scope \
    layers.xuankong_natal.period_context.event_time_context.boundary_resolution.ephemeris_model
```

预期宅盘为complete、九运，事件有效年为null、候选为2024与2025。快照与固定释义同步说明“所有候选年均属9运”及“事件有效年仍未确认”。固定释义引用同次 `layers.xuankong_natal.period_context`，不另算年份或选择候选。

## 验证范围

```bash
uv run --locked --extra dev pytest -q tests/test_fengshui_event_year_fidelity.py
```

新增51项检查覆盖实际Moshier、实际解析模型和具名模拟回退；模拟回退不计真实天文样本。包括±5秒闭端点与±6秒、同运及跨运、跳过区间求解时的状态保留、显式确认、快照、固定释义和四个入口的REST／实际FastMCP协议／CLI一致性。修改前六个关键检查失败，原日志保留。

前后两个隔离运行副本只差六个修改源文件：50个非边界案例的完整业务结果一致，八个边界案例的宅盘、候选、状态及缺项不变，八工具输入／输出Schema与必要输出根完全一致。它们是回归不变性证据，不是独立天文精度、自由模型解释、部署或现实预测验证。原典三处正文和一项图数字差异、Moshier数值失败与现实数据缺口均继续保留。

完整隔离回归2,322项通过、零失败和跳过，2,660个冻结文件运行后不变；原始失败、来源闸门和精确范围见第二十五轮证据（本地数据：`validation/fengshui-event-year-v25-evidence.json`）。

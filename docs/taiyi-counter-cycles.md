# 太乙完整计数、纪元坐标与原例题注

`taiyi.counter_cycles`把本次实际完整计数分解为360周期、60计数组与72计数组，并绑定同盘`core_board.accumulation`及`kook_number`。年、节月、日、时辰分别标明单位；局号和组内余数不能代替完整积数。当前分解只在同盘72周期位与实际局号一致时成立，不一致即报错。

| 完整计数 | 360周内位 | 60组／组内位 | 72组／组内位 |
| --- | --- | --- | --- |
| 72 | 72 | 2／12 | 1／72 |
| 73 | 73 | 2／13 | 2／1 |
| 315 | 315 | 6／15 | 5／27 |
| 360 | 360 | 6／60 | 5／72 |
| 361 | 1 | 1／1 | 1／1 |
| 887 | 167 | 3／47 | 3／23 |

887和行宫捷数47可以落同一太乙宫，却有不同的文昌与局号。新增字段使实际取用哪一个完整计数可核对；没有修改积数公式、时计起点或默认配置。`calendar_ganzhi_alignment=not_assessed_by_counter_decomposition`明确表示未据分组认证实际干支、古历起元或原书每个“纪／元”题注的含义。

## 十卷题注逐条保留

依据[四库本卷一](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷01)及[卷九](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷09)，冻结十卷转录中所有同一行同时含“局”及“纪／元”的15处上下文，包含10条案例和5处公式、表头。此范围不代表已审完整十卷规则或全部无题注算例。原文、书影、逐条预期和读取限制见冻结文件（本地数据：`../tests/fixtures/taiyi_cycles_v42/freeze.json`）。

在明确声明的“甲子从一、60为纪组、72为元组”坐标假设下，10条中9条有唯一相位，1条不能同时满足全部标签。未明阴阳遁的5条两支全部列出，不按数值择优。

| 原例 | 同时满足题注的相位 | 数值比较与限制 |
| --- | --- | --- |
| 当时法 | 315 | 给定相位的10项核心字段相符，但没有公元年或绝对积数；元字仍有版间疑读，完整原例未通过 |
| 占敌动静 | 无 | “阴第三纪、第52局、乙卯时”在所声明坐标假设下不相容；按52局的7项盘面相符仍不能认证完整题注 |
| 两军相当 | 2 | 按印出第2局，阳支仅1／10项、阴支0／10项相符；原字、两支及差异全部保留 |

明钞卷九书影也印出第三纪／第52局／乙卯时，未据现代程序改成第一纪。逐一去掉约束的诊断结果全部保留，但不以放松条件后的相符冒作整例通过。该冲突也不证明古书必错：题注中纪名的实际含义、流派与版本仍待校勘。旧例不是新增独立古例，资料读取非盲法，独立专家复核为0。

冻结主审计后另核明钞卷六第78图，发现同一两军例写“上元第一局”，而四库转录写“上元第一纪第二局”；始击也有巽／大武（坤）的差别。此后单独冻结书影和预期再计算：明钞第一局阳支9／10、阴支0／10，阳支仍有始击巽／坤不符。见补充报告（本地数据：`validation/taiyi-jinjing-v42/ming-supplement-report.json`）。这项版差没有改掉原四库失败、选择阴阳遁或增加完整古例通过数；补充不是先前冻结运行输入的一部分。

## 同次解释与复现

太乙和三式均发布`counter_cycles`字段视图。读取该视图的`fields`后，保持`strict_fields=true`、`include_snapshot_text=false`。快照与导出由同次保存值生成，不重新取钟或另排一盘；三式仍须按`synthesis.time_scopes`分别解释时间层。

首读视图保留原有字段；详细分组通过专用视图取用。密集响应可将完整`run_metadata`回执延后到同次manifest，并在`deferred_fields`明确标出；首屏运行标识与manifest的完整结果哈希用于绑定恢复后的回执，不能把分页参考当成另一次计算。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 10 --analysis-day 25 --analysis-hour 12 \
  --analysis-timezone +08:00 --no-use-true-solar-time \
  --calculation-mode hour --hour-profile key_hour_winter_jiazi_v1 \
  --fields taiyi.counter_cycles taiyi.calendar_summary \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
uv run --locked --extra dev python scripts/audit_taiyi_cycles.py \
  --output docs/validation/taiyi-jinjing-v42/report.json
```

审计脚本保留整体未通过状态并返回1。数学、传输与回归测试通过只认证其各自范围。新增完整有日期古例通过数、模型调用和现实预测验证均为0；既有历法失败、原典分歧及V25模型原成绩不重判。运行材料见V42验证记录（本地数据：`validation/taiyi-jinjing-v42/README.md`）。

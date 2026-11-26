# 完整结果与核验

需要核验完整计算回执、时钟来源或全部选文时读取本页。

未请求、未返回、未读取、未选择与未计算须分别说明。河洛未指定 `analysis_year` 时仍生成 `heluo_timing.annual_rows`，只是 `selected_annual=null`；只能据此说未选定或未解读具体年。字段被投影排除或尚未读取时保留证据缺口，不据此否定已经生成的内容，也不为自证另排一次。年序已生成同样不证明民用历法映射或预测有效。

需要完整结果与审计证据时，使用 `detail=audit` 且 `fields=null`（CLI 省略 `--fields`）；仅核验时钟与核心字段时，按 `fields` 精确投影：

```bash
python3 -m fatebridge.cli heluo --date 1990-05-15 --time 10:30 --lon 116.40 --gender 男 --fields input_normalized numerology_evidence.birth_clock
```

摘要调用只保留实际投影范围，完整业务须使用 `detail=audit` 且 `fields=null`。如果本地没有可用的引擎环境（且非连接咨询），保留核验缺口并交付已有可答部分；不猜解释器位置、不为咨询安装依赖，也不重算冒充已有运行。调用规范见[引擎调用](../shared/fatebridge-engine.md#怎么调引擎)。

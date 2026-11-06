# 同次交付与核验

返回包含 `result_delivery` 即读取本页，包括业务完整显示、仅延后回执的 `compact_reference`。先核验原 run 与存储完整性，再确认所需业务字段已经读取；两者分别确认。

未请求、未返回、未读取、未选择与未计算须分别说明。河洛未指定 `analysis_year` 时仍生成 `heluo_timing.annual_rows`，只是 `selected_annual=null`；只能据此说未选定或未解读具体年。字段被投影排除或尚未读取时保留证据缺口，不据此否定已经生成的内容，也不为自证另排一次。年序已生成同样不证明民用历法映射或预测有效。

长结果使用[同run核验读取](../../_shared/fatebridge-engine.md#怎么调引擎)：

```bash
fatebridge result-read RESULT_ID --run-id ORIGINAL_RUN_ID --path numerology_evidence.birth_clock --offset 0
```

结果ID与run ID取自原回执。接口以内部清单检查完整保留payload，再返回所选字段页；公开响应不提供哈希或指纹。其他所需事实继续读取同run，直到所需字段的 `next_offset=null`。核验成功不表示已经读取全部业务事实。摘要调用的文件只保留实际投影范围，完整业务须首次 `fields=null`。

客户端不能读取资源且没有已安装的引擎环境时，保留该项核验缺口，交付已有可答部分；不猜解释器位置、不为咨询安装依赖、不重算冒充原run。结果读取只维护引擎的共享实现。

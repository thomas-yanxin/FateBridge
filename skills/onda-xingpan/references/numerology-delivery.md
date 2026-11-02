# 同次交付与校验

返回包含`result_delivery`即读取本页，包括业务完整显示、仅延后回执的`compact_reference`。先核验原payload和run，再确认所需业务字段已完整读取；两者分别确认。若业务已全部在首屏，可校验读取`run_metadata.run_id`，仍需使用原`result_delivery.sha256`核验整个保留payload。

未请求、未返回、未读取、未选择与未计算须分别说明。河洛未指定`analysis_year`时仍生成`heluo_timing.annual_rows`，只是`selected_annual=null`；只能据此说未选定或未解读具体年，不能说没有计算岁运。字段被投影排除或尚未读取时保留证据缺口，不据此否定该层已生成的内容，也不为自证另排一次。年序已生成同样不证明民用历法映射或预测有效。

长结果优先用[确定性校验读取](../../_shared/fatebridge-engine.md#怎么调引擎)。源码已有依赖环境可执行`PYTHONPATH=src python -m fatebridge.cli result-read RESULT_ID --sha256 ORIGINAL_SHA256 --run-id ORIGINAL_RUN_ID --path numerology_evidence.birth_clock --offset 0`；分别取原回执的`result_delivery.result_id`、`result_delivery.sha256`、`run_metadata.run_id`，不要用裁剪前的`business_output_sha256`替代交付散列。成功的`verification`核验原完整payload与run，`text`仍是所选字段，其他所需事实继续读同run，分页到`next_offset=null`。不要另试多种JSON序列化凑散列；外层文件SHA或`sort_keys=True`不是交付payload SHA。没有成功核验就保留身份缺口，审阅者事后验对不能替代本次模型读取，也不能重算冒充旧run。

客户端不能读资源、当前目录又没有已安装的FateBridge解释器时，使用随技能提供的[标准库读取器](../../_shared/read-retained-result.py)，不猜`.venv`位置或安装依赖。脚本位置按本页相对链接解析；下面是仓库根目录的调用形式，文件路径、SHA和run均换成原回执的实际值：

```bash
python skills/_shared/read-retained-result.py RECORD_FILE --sha256 ORIGINAL_SHA256 --run-id ORIGINAL_RUN_ID --path numerology_evidence.birth_clock --offset 0
```

`RECORD_FILE`来自原`result_delivery.file_path`。读取器只读该文件，在同一对象上按原序序列化并核验完整payload与run，再返回最多2048字符的字段页；不导入计算包、不重算、不写文件。`local_record_payload_sha256_v1`表示客户端本地核验，未查询服务端引用状态，也不证明业务计算或解释正确。检查退出状态、JSON及`verification`；页未结束时沿用该次`next_offset`，需要完整字段才拼接并核对字段`sha256`，不一次打印整份大记录。失败后保留具体缺口，不把失败命令当作成功读取。

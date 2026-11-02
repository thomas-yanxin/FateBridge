# 金镜两算的独立加数核查

现有 `source_position_recount` 使用生产计数函数，把原表位置代入所选通则。它能区分输入位置与算数差异，但不能单独排查这个函数自身的错误。本轮增加另一种实现的冻结参照，保留原表、生产实际位置和源位置重算三个对象；生产数字和公开输出合同没有改变。

参照来自[卷二《推太乙运式法》](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02#推太乙運式法)：正宫按本数，间神加一；明例为大义亥至太乙巽九，1＋8＋3＋4＝16。卷二宫数对应给出乾、子、艮、卯、巽、午、坤、酉的权重1、8、3、4、9、2、7、6，和为40。本轮以累计和差分及模40运算，独立生成全部16起点×8宫的128个软件对照值；没有调用生产的逐神行算循环。

同宫取本宫数仍是所选读法。全部20个同宫原表槽位（本地数据：`../tests/fixtures/taiyi_jinjing_arithmetic_v49/all-coincident-source-slots.json`）同时保存，阴46客算原表2与所选读法1的冲突不删。不能用19项相符将这一读法认定为已经完全校定，更不能将128个算术对照称为128个新增古例。

参照说明（本地数据：`../tests/fixtures/taiyi_jinjing_arithmetic_v49/reference-specification.json`）、128个参照及加数（本地数据：`../tests/fixtures/taiyi_jinjing_arithmetic_v49/reference-grid.json`）、完整144行原位置／两算（本地数据：`../tests/fixtures/taiyi_jinjing_arithmetic_v49/source-inputs.json`）在新的运行事实采集与比较前冻结（本地数据：`../tests/fixtures/taiyi_jinjing_arithmetic_v49/freeze.json`）。原位置及数字沿用V23书影语义校读和四项既有订正，本轮没有新增逐字识读。读者已知旧代码与差异，属于非盲的独立实现，不是独立人类审阅或新统计证据。

| 比较对象 | 要求数 | 结果 |
| --- | ---: | --- |
| 生产计数函数与独立参照 | 128 | 数值、逐项加数、终点和排除终点说明全部一致 |
| 实际144局的主客算与各自实际位置的独立参照 | 288 | 数字和算路一致，未发现新误算 |
| 原表位置的生产重算与独立参照 | 288 | 数字和算路一致 |
| 独立参照按原表位置重算与原表数字 | 288 | 278相符、10不同 |
| 程序实际两算与原表数字 | 288 | 277相符、原11差异保留 |
| 程序实际四位置与原表位置 | 576 | 573相符、原3始击差异保留 |

这些分母属于不同对象，不能相加为准确率。独立参照保留了十处书内两算差异（本地数据：`validation/taiyi-jinjing-v49/delivery-audit-report.json`）。对原288槽位逐项联接后，276项输入及两算一致，9项同输入而规则与表数不同，2项源位置可解释算差，1项两算相同但源位置不同，见完整归因（本地数据：`validation/taiyi-jinjing-v49/independent-diagnosis.json`）。阴37源目午重算27与表数25不同；阴43／44源目代入能得表数38／31。这些关系没有裁定应改程序、原表、版本或适用条件。

回归还故意把阳39实际主算从35改成表数25：表值相符会升高，但独立算术检查会失败。把源位置重算也改成25，仍会被独立参照检出。总数保持16而起点写错或终点排除标记写错，也会单独报告算路失败；布尔值不能冒充一宫。这些是明确标注的软件对抗检查，没有修改或重评分真实源行。

```bash
uv run --locked --extra dev python -m scripts.capture_taiyi_jinjing_arithmetic \
  --output /tmp/taiyi-arithmetic-actuals.json
uv run --locked --extra dev python -I scripts/audit_taiyi_jinjing_arithmetic.py \
  --actuals-file /tmp/taiyi-arithmetic-actuals.json \
  --output /tmp/taiyi-independent-arithmetic.json
```

第二条命令在报告正常生成后退出1，表示完整原典验收未通过。省略 `--actuals-file` 可只核原表与独立参照，此时 `runtime_assessed=false`，终端摘要的程序失败计数为 `null`，不得将没有采集运行事实当作程序已通过。独立审计只导入标准库；原评分文件只用于保留旧层，参照数值没有取自旧程序结果。

最终冻结源7个完整模块共297项通过，当前工作区新增模块142项通过；当前和冻结源的128计数、144盘及144份源重算业务事实逐值相同。并行工作区的历法公共文件及其他方法另有变化，因此这不认证当前全树、完整历法、部署或已连接MCP。详见V49证据（本地数据：`validation/taiyi-jinjing-v49/README.md`）。完整古历、原表十处内部冲突、三处始击差异和真实模型解释仍待验收；新增模型调用、有日期古例与独立专家审阅均为0。

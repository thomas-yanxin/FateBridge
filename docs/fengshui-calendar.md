# 风水历法独立验收

[时间边界规范](../skills/onda-fengshui/references/calendar-boundaries.md) · [总审计](fengshui-depth-audit.md) · 原始参考清单（本地数据：`../tests/fixtures/fengshui_calendar_v10/provenance.json`）

风水领域复用共享交节求解，分别保留年数、定运与民用时间政策，报告真实回退和实际星历模型。REST、MCP、CLI共用字段与可读摘要，`time_basis`位于各自分辨记录内。科学范围与解释要求统一维护在上方规范。

[历法消费端验收](fengshui-calendar-consumer-integrity.md)另覆盖公开1801–2199年全部十二节及固定前后时刻，核对年、月、命卦与宅运的分支传播；月盘原表及逐宫数式也有独立检查。Moshier的569项一秒超差保持不通过，候选保护成功不抵消数值失败。

共享引擎现有 `auto`、`native`、`analytic`、`spk`、`de440`太阳模型政策。无外部严格JPL配置时，自动模式在1800–2200年使用打包DE440，风水层另有[历史端点扩展](fengshui-historical-calendar.md)。原生控制试验须显式设置 `FATEBRIDGE_SOLAR_TERM_MODEL=native`，并继续核对实际返回的 `ephemeris_model`；空星历目录不能单独证明正在运行Moshier。各模型与严格外部来源的成绩分别判断，不互相授予。

对于Moshier、具名解析模型及两个打包DE440模型，风水边界保留既有五秒操作保护，分别给出实际模型和原因；此保护不是误差上界，也不改变固定一秒实现验收。年界、月界、宅运换界和跨民用日期的命卦候选均沿用该区别；明确有效出生年且无需交节求解的命卦不新增模型观测。详见[模型边界证据链](fengshui-model-boundary-fidelity.md)。

保护区内的唯一年数与年度有效期保持null，暂取年与全部候选年度区间单独返回；两个候选有效年同属一个二十年运时，可以确定宅运但不能确认事件有效年。跨运则保留完整候选运区间，详见[事件有效年与宅运分层](fengshui-event-year-fidelity.md)。

月层在交节待确认时，同样不返回唯一有效期；各候选年／节月分别带起止及实际来源，暂取区间单列。同年内换月仍保留已确定有效年，跨立春则保留两个候选年。完整字段、来源引用与虚构示例见[候选节月有效期](fengshui-month-interval-fidelity.md)。

完整文件可通过[风水历法安装配置](fengshui-ephemeris-setup.md)取得，并在新进程中自动发现已验证用户缓存。安装完成仍须核对实际模型与独立门槛，不将文件身份等同天文验收。

## 固定协议与独立参考

最新[全部24节气验收](fengshui-all-terms-calendar.md)覆盖1784–2204年10,104个交点，默认DE440全部在原1秒线内，实际Moshier控制组保留1,196项失败。以下原立春协议独立保留，历史配置成绩不追授给别的模型。

最初冻结1800–2200年401项TT交点及1秒实现容差。随后按实际20年宅运端点向外扩展为1784–2204年421项，不删除首版或改变容差；两个协议、两份参考和首版收集器全部保留。覆盖边界由1864纪元及有效事件年1800–2199推导，不从通过／失败结果挑年份。

参考收集器不导入FateBridge，使用固定Skyfield1.53的 `almanac_east_asia.solar_terms` 与JPL完整DE440，在固定2月1日至8日TT区间二分。JPL公开MD5与完整文件SHA-256均核对；原星历约114MiB，不装入wheel或测试仓库。参考中记录收集器散列、五个依赖版本、原协议与所有交点。它是独立软件／星历实现比对，不是新收集的现实观测或盲测风水案例。

使用新输出路径复建：

```bash
uv run --no-project --with skyfield==1.53 python scripts/build_fengshui_lichun_reference.py \
  --kernel /absolute/path/de440.bsp \
  --protocol tests/fixtures/fengshui_calendar_v10/period-protocol.json \
  --output /tmp/new-lichun-reference.json
```

参考文件不覆盖。日常离线验收使用原始冻结参考：

```bash
uv run --locked --extra dev python scripts/audit_fengshui_calendar.py
uv run --locked --extra dev pytest -q tests/test_fengshui_calendar_v10.py
```

完整Swiss星历配置下421项通过，最大差约0.106秒；显式原生模式实际采用Moshier的控制配置下，该脚本应退出1，375项通过、46项失败，最大差约2.14秒。常规安装的自动模式可能另选解析模型，必须按实际模型单独验收，不能把完整配置或其他模型的通过结果赋给它。未安装Swiss或交点求解失败的固定气回退，421项均保留为未通过，不拿近似钟时伪装TT比较。

脚本保留所有比较。删除、重复、重排年份，NaN／布尔参考值或放宽1秒门槛均被拒绝；单条参考偏移会形成真实失败。TT数值比对不消除历史UT1约定、未来闰秒假设或现场时间输入误差。

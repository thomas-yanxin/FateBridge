# 风水历史宅运端点的DE440轨道覆盖

[玄空宅盘](fengshui-xuankong.md) · [上一轮精度差异](fengshui-angle-source-audit.md)

公开宅运事件年1800–2199对应的完整二十年运区间，端点可早至1784年、晚至2204年。原有独立历法协议因此冻结了1784–2204的全部421个立春TT样本。不能因公开请求不接受1785年，就删除协议中该年的失败。

第三十二轮发现：默认打包模型只覆盖1800–2200软件年份，外部年份回到native路径；在该次环境中，1785年Moshier比独立基准早约1.114秒，未过原定1秒门槛。现在新增独立轨道资料版本，使风水历史区间使用真实DE440位置系数求根；原样本与1秒门槛保持不变。

## 来源与选用范围

| 风水历法所需年份／选择 | 实际路线 |
| --- | --- |
| 1800–2200，默认auto或de440 | 原`fatebridge_de440_solar_v1`，原资料保持字节一致 |
| 1784–1799、2201–2204，auto或de440 | `fatebridge_de440_solar_historical_v1`；风水层独立选择，不扩张公开请求年份 |
| 显式native、analytic、spk | 继续按对应共享模型规则处理，不被历史扩展替换 |
| auto另配置严格JPL来源 | 保留严格JPL选择，不绕过其来源校验 |
| 历史扩展缺失、损坏或计算中配置变化 | 停止计算并返回来源错误，不静默退到Moshier或线性日期 |

新资料从[NASA/JPL完整DE440](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp)抽取地球、地月质心及太阳的原始type2记录，包含1782–2207填充年份。完整内核SHA-256为`a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5`，记录结构依[NAIF原始格式说明](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html)。没有拟合、降阶、四舍五入或逐年修正表，也没有把立春参考答案打包进运行数据。

扩展清单散列为`d7cf5e3ee5bda32b54bbbf087dedff62d0c4f7ea64824e64ccfe572fe879bda0`，压缩系数散列为`29a8ade47dd04ff53f5b7abff04549ea448a2105fb5fab7dc6b8f005045cdca1`。生产者署FateBridge项目；来源原注只作为档案保留，参见[NOTICE](../NOTICE)与[NAIF再分发规则](https://naif.jpl.nasa.gov/naif/rules.html)。这份衍生数据不表示NASA/JPL认可FateBridge。

## 数值与解释分别验收

提取前先固定范围、原内核散列和数值门槛；提取后、接入新运行分支前冻结系数及独立SPK读取器的5,052组位置／速度。每个1784–2204年份取四个TDB季度时刻、三组天体关系，不能用生产算法生成预期值。逐记录检查和独立状态比较用于验证系数读取与切比雪夫求值；原421个立春表继续验证TT求根。

原版401个立春求根及来源回执与修改前代码逐项比较，防止扩展改变原有范围。Moshier控制组继续保留原数值失败，不将改用DE440后的通过追授给它。历法软件相合不证明观测上的绝对精度，更不证明风水现实预测有效。

每个历史端点返回实际模型、原内核与系数散列、TDB覆盖、参考表未参与运行、TT根区间及钟时约定。历史UTC形式标签仍按UT1／ΔT约定换算；未来UTC仍受冻结闰秒假设限制。5秒边界候选保护不代替1秒TT数值验收。

另修正了宅运待确认原因：DE440计算保留跨运候选时，不能写成“近似立春回退”。结构化原因现标明DE440模型的候选保护，快照也区分轨道计算与线性回退。它不认证自由模型撰写的解释。

## 复现

[虚构1800年竣工输入](examples/fengshui-historical-period.json)用于验证1784–1804历史运区间，不是住宅证据：

```bash
uv run --locked --extra dev fatebridge fengshui_xuankong_natal \
  --request-file docs/examples/fengshui-historical-period.json
uv run --locked --extra dev python -m pytest -q \
  tests/test_fengshui_historical_solar.py tests/test_fengshui_calendar_v10.py
```

从原内核重建核对需要研究依赖`jplephem2.24`、`numpy2.2.6`，不增加运行时依赖。使用`scripts/build_fengshui_historical_solar.py --kernel ... --check`逐字节核对；不带`--check`时拒绝覆盖既有冻结资料。

实际测试范围、平台、安装包三端结果及未通过检查见第三十三轮证据（本地数据：`validation/fengshui-historical-solar-v33-evidence.json`）。原典图文冲突、日时选表和前瞻现实验证继续独立保留，不能以天文数值通过授予四项满分。

第三十四轮进一步核对[全范围24节气](fengshui-all-terms-calendar.md)：新增独立10,104项TT参考，分别验证原始根与输出钟时回算，不以此前立春及轨道状态检查代替其余节气。

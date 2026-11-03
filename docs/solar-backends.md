# 可选太阳后端

太阳模型由 `FATEBRIDGE_SOLAR_TERM_MODEL` 显式选择，默认仍为 `auto`。`swiss` 要求实际使用 Swiss 文件模型；AA1996 与 VSOP2013 需要另行构建。先完成[源码环境准备](development-guide.md#环境准备)，再按所选模型准备数据。外部星历与默认路线见[星历数据与精度](getting-started.md#星历数据与精度)。

## 严格 Swiss 文件模式

需要原生 Swiss 视位置流程、并希望在缺少文件时停止计算，可选择 `swiss`。公开节气输入为1800—2200年；首尾输入所需1799／2201年边界仅在原上下文内读取，不扩展公开年份。原 `native` 选择继续保留原生回退行为和既有 Moshier 失败。

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --profile fengshui_calendar
export FATEBRIDGE_SOLAR_TERM_MODEL=swiss
```

该文件配置含所需的 `sepl_12`／`semo_12`／`sepl_18`／`semo_18` 分段；自定目录通过 `SE_EPHE_PATH` 选择。严格模式复用现有 TT 求根及文件来源核查，不拟合参考交点，也不修改 Moshier 的系数。缺文件、返回 Moshier 或不能取得交点时，三端返回非重试503及 `solar_swiss_files_required`；无法核查文件来源时保留相应来源错误。与显式原生 JPL 配置冲突时返回配置错误。

参评1800年初所需的1799年立春沿用已核对的相邻年组件；120年投影若越过2201年边界，则返回 `solar_swiss_range`，不交付缩水年序或更换模型。风水等领域另需范围外历史边界时也须按该领域的模型支持范围选择来源，不能从文件存在推定已扩展资格。

每个交点仍返回实际旗标、TT 括区和观测到的行星／月球文件身份；环境回执的 `analytical_fallback_allowed=false` 仅描述选择政策。能使用文件不自动证明任意年份或全部交点达到一秒；数值验收必须同时绑定所用文件、参考和样本。依据为 [Swiss 请求与实际返回模型的区别](https://www.astro.com/swisseph/swephprg.htm)。

同一批冻结96点的当前复核见[数值与失败保留记录](validation/solar-numerics-20261103-v1/report.md)。原1秒 TT 门槛下，严格 Swiss 文件路径无超差，原空目录 Native 对照的12项超差单列保留；这是不同模型的分别验收，不表示 Moshier 系数误差已修复。

## 模型与适用范围

| 项目 | AA1996 | VSOP2013 |
| --- | --- | --- |
| 选择值 | `aa1996` | `vsop2013` |
| 模型标识 | `fatebridge_moshier_aa1996_solar_v1` | `fatebridge_vsop2013_solar_v1` |
| 当前来源配置 | [aa1996-solar-v1.json](../src/fatebridge/data/astronomy/aa1996-solar-v1.json)，1.1.0 | [vsop2013-solar-v1.json](../src/fatebridge/data/astronomy/vsop2013-solar-v1.json)，1.1.0 |
| 轨道与视位置 | Moshier AA 5.6 的1996年地月质心级数、完整 Moshier 月球、Swiss 视位置流程 | 完整 VSOP2013 地月质心、Moshier 月球、ERFA TT→TDB、Swiss 2.10.03 视位置流程 |
| 公开日历年份 | 1800—2200 | 1700—2300 |
| 内部端点 | 风水运期允许1784—2204年 | 工作 TT 区间1684年初至2421年初；完整节气资格1684—2304年，2305—2420年仅另核对立春 |
| 清单变量 | `FATEBRIDGE_AA1996_MANIFEST` | `FATEBRIDGE_VSOP2013_MANIFEST` |

内部端点服务于具体消费方，不扩张公开出生年份或完整节气年表。参评具现代立春映射的两种八字配运方法仍返回120条年序和121个边界，不补造旧命宫法未知的 UTC 映射。

## AA1996

在项目根目录构建到尚不存在的绝对目录：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_aa1996 --output /absolute/new-aa1996-build
export FATEBRIDGE_SOLAR_TERM_MODEL=aa1996
export FATEBRIDGE_AA1996_MANIFEST=/absolute/new-aa1996-build/manifest.json
```

构建器下载并核验固定原包、32个计算源码文件，再调用本机 C 编译器。离线原包可用 `--swiss-archive`、`--aa56-archive` 指定，字节须匹配来源配置。1.0.0旧构建不具有1.1.0的扩展范围，需在新目录重新构建。

已记录的实际构建平台为 macOS arm64；Linux 构建分支尚未验收，Windows 不支持该构建器。算法来源与方法见[作者级数研究](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/liuyao-moshier-aa1996-audit.md)。

## VSOP2013

```bash
uv run --locked --extra dev python -m fatebridge.fetch_vsop2013 --output /absolute/new-vsop2013-build
export FATEBRIDGE_SOLAR_TERM_MODEL=vsop2013
export FATEBRIDGE_VSOP2013_MANIFEST=/absolute/new-vsop2013-build/manifest.json
```

离线构建用 `--source-dir` 提供匹配来源配置的文件；`--compiler`、`--linker` 可选择已有工具链。系数与时间转换代码编入本地库，运行时无需 Python ERFA、jplephem 或外部星历文件。旧来源配置的清单需用当前构建器重新生成，保留旧库与证据。

直接计算输入为 TT 儒略日，求根括区须跨越向前的目标太阳黄经：

```python
from fatebridge.core.vsop2013_solar import longitude_crossing_tt, solar_longitudes_tt

points = solar_longitudes_tt([2451545.0])
crossing = longitude_crossing_tt(285.0, 2451545.5, 2451556.5)
print(points["longitudes"], crossing["jd_tt"])
```

返回保留模型身份、`bracket_tt` 与 `bracket_seconds`；`cache_key()` 和 `expected_source_key` 可绑定连续计算的来源。显式选择与严格原生 JPL 配置冲突时先报配置错误。只查询文本、未消费太阳坐标的工具不加载可选库，回执注明未观察到业务使用的来源。

## 构建证据与错误处理

两个构建器都保留原包、许可证、源码图、编译命令、日志、二进制和 `manifest.json`。失败目录保留，重试使用新目录。默认 wheel 不携带这些已构建二进制；业务请求不会触发下载、编译或替换已安装的 Swiss 库。

加载器核对来源配置、模型、平台、ABI、清单与二进制散列，使用已验证字节的私有副本，并记录实际计算入口所属映像。原生标志 `260` 只描述选项，模型身份由具名模型及来源图确定。清单缺失、来源变更、错误 ABI、返回标志或非有限结果均明确失败，不静默切换太阳模型；来源错误沿用非重试503合同。

## 已有验证与未完成范围

以下是固定版本的历史结果，不是本轮重新执行的成绩。交叠队列、源码与安装包重放不能相加为独立样本。

| 模型 | 固定门槛与记录 | 仍需区分的范围 |
| --- | --- | --- |
| AA1996 | 10,104交点按原1秒 TT 线检查；升级后最大差0.899854秒。运期58项旧失败修复后，14,364查询与4,788消费事件保留完整重放 | 五秒操作性保护只用于保留候选，不是精度门槛；原生 Moshier 的501项失败未重评 |
| VSOP2013 | 15,020项对照按原1秒 TT 线检查：14,904节气最大差0.446105秒，116个未来立春最大差0.816974秒 | 未来立春不等于完整未来节气资格；原生96项的84通过／12超差保留；接入时共享回归的405失败、139错误和84跳过不能记为全仓通过 |

这些结果使用 DE440 参考框架，不认证绝对 UTC、历史 UT1、全部连续时点、完整原典、真实模型解释或现实预测。VSOP2013 的记录平台为 macOS arm64 / Python 3.12.13；Linux、其他平台和部署验收仍需另行完成。

构建修订、首次失败和原始记录见合并前的 [AA1996 指南](https://github.com/thomas-yanxin/FateBridge/blob/73ec8912677b2b687a4b11ccb06727332296e8e1/docs/aa1996-solar-backend.md)与 [VSOP2013 指南](https://github.com/thomas-yanxin/FateBridge/blob/73ec8912677b2b687a4b11ccb06727332296e8e1/docs/vsop2013-solar-provider.md)。领域层如何解释来源和条件见对应[专题入口](README.md#计算原理与专题)。

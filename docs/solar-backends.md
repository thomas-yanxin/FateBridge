# 可选太阳后端

AA1996 与 VSOP2013 都需要显式构建和配置。它们为节气及领域历法提供具名太阳模型；默认选择仍为 `auto`。先完成[源码环境准备](development-guide.md#环境准备)，再按所选模型构建。外部星历与默认路线见[星历数据与精度](getting-started.md#星历数据与精度)。

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

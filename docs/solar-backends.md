# 太阳计算与可选后端

`FATEBRIDGE_SOLAR_TERM_MODEL` 选择共享太阳交节模型；默认 `auto`。普通安装在适用年份使用随包 DE440 系数，无需另行下载或编译。更改此变量会影响八字、时运、六壬、数算和风水等消费方，具体路径见[架构依赖表](architecture.md#历法与星历依赖)。

## 默认模型与选择顺序

| 模式 | 实际选择与准备 | 年份和失败边界 |
| --- | --- | --- |
| `auto`（默认） | 已配置严格原生 JPL 时优先使用 JPL；否则 1700–2300 年使用随包 DE440，范围外进入原生路径 | 软件允许年份和各消费方公开输入仍分别校验；无可用交点时明确失败 |
| `de440` | 显式选择随包 DE440，无需 `jpl` extra 或外部 SPK | 公开模型输入 1700–2300 年；内部相邻边界及参评投影使用各自具名资料，不扩大公开年份 |
| `native` | 可用 Swiss／JPL 文件保留原生模型；Moshier 回退采用下述完整修订 | 读取实际模型与来源，不能用原生库可导入推定文件已就绪 |
| `swiss` | 必须实际使用 Swiss 文件；[下载分段](ephemeris.md) | 1800–2200 年；缺文件、返回 Moshier 或来源未核查时拒绝 |
| `analytic` | 显式选择 `core/analytic_solar.py` 的具名解析模型 | 1800–2200 年；不与完整 Moshier 修订混名，不能沿用另一模型的验收成绩 |
| `spk` | `FATEBRIDGE_SOLAR_SPK_FILE` 指向外部 SPK，安装 `jpl` extra | 以所选文件、加载器和消费方支持范围为准 |
| `aa1996` / `vsop2013` | 按下文构建并指定清单 | 各自范围、平台及来源单独核验 |

选择逻辑见 [`solar_model_policy.py`](../src/fatebridge/core/solar_model_policy.py)。默认系数来自 DE440 的无损裁取，主模型、扩展年份及派生边界保留各自模型身份和来源指纹。TT 网格符合不能认证绝对 UTC、全部连续时刻或现实预测。

外部数据准备见[星历安装](ephemeris.md)，固定有限队列及仍未通过项见[分项精度验收](precision-acceptance.md)。需要可选模型时先完成[源码环境准备](development-guide.md#环境准备)；SPK／视位置对照所需依赖可用 `uv sync --locked --extra dev --extra jpl` 安装，后续命令也保留这两个 extra。

## 严格 Swiss 文件模式

需要原生 Swiss 视位置流程、并希望在缺少文件时停止计算，可选择 `swiss`。公开节气输入为1800—2200年；首尾输入所需1799／2201年边界仅在原上下文内读取，不扩展公开年份。`native` 有文件时沿用实际 Swiss／JPL；解析回退使用下述完整 Moshier 修订。

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --profile fengshui_calendar
export FATEBRIDGE_SOLAR_TERM_MODEL=swiss
```

该文件配置含所需的 `sepl_12`／`semo_12`／`sepl_18`／`semo_18` 分段；自定目录通过 `SE_EPHE_PATH` 选择。严格模式复用现有 TT 求根及文件来源核查，不拟合参考交点，也不修改 Moshier 的系数。缺文件、返回 Moshier 或不能取得交点时，三端返回非重试503及 `solar_swiss_files_required`；无法核查文件来源时保留相应来源错误。与显式原生 JPL 配置冲突时返回配置错误。

参评1800年初所需的1799年立春沿用已核对的相邻年组件；120年投影若越过2201年边界，则返回 `solar_swiss_range`，不交付缩水年序或更换模型。风水等领域另需范围外历史边界时也须按该领域的模型支持范围选择来源，不能从文件存在推定已扩展资格。

每个交点仍返回实际旗标、TT 括区和观测到的行星／月球文件身份；环境回执的 `analytical_fallback_allowed=false` 仅描述选择政策。能使用文件不自动证明任意年份或全部交点达到一秒；数值验收必须同时绑定所用文件、参考和样本。依据为 [Swiss 请求与实际返回模型的区别](https://www.astro.com/swisseph/swephprg.htm)。

当前数值门槛为与固定 DE440 参考比较的1秒 TT，参考输入与原数值见 [96点当前参考](../tests/data/solar/de440-guard-tt.json)。原版 Swiss Moshier 同一队列的12项失败继续单列；FateBridge完整修订按独立身份验收，不将旧模型失败改判。

当前原生求根使用 `native_swiss_tt_solar_bisection_v2`：返回首个达到或越过目标太阳黄经的可表示 TT 浮点点，其前一浮点点仍在交点之前，策略为 `first_post_crossing_tt_float`。这是同一太阳模型数值方程的边界取点约定，不修正星历系数，也不把浮点分辨率当作物理精度。实现见 [`almanac.py`](../src/fatebridge/core/almanac.py)，当前前后侧验证见 [`test_native_solar_crossing_side.py`](../tests/integration/test_ci_regressions.py)。

## 完整 Moshier 解析回退

当前 `native` 路径缺少文件而实际返回Moshier时，太阳交点使用 `fatebridge_complete_moshier_solar_v1`。它完整求和作者1996年 `ear404` 地月质心级数及其解析速度，调用原生公开接口取得完整几何月球，按地月质量比还原地心，再计算光行差、IAU2006/P03及IAU2000B日期真黄道。运行时不读取参考交点，不替换已安装的Swiss库，也不需要另行编译。

原版误差来自地月质心级数与短月球偏移两部分：仅补完整月球时，原96点仍7项超差；仅更新地月质心时仍2项；两者都更新后，当前完整实现原96点全部进入1秒线，最大0.775253秒。新增576个未重叠TT点全部进入原线，最大0.668031秒。原有14904点参考中，内部1784—2204年全部10104个交点实求验收，最大0.883480秒、零超差；其中公开1800—2200年共9624点。参考队列、数值与1秒线均未重建或放宽。

`resolution_provider=fatebridge_moshier` 保留新模型与系数身份，不借用原生太阳返回标志。源码见 [`moshier_solar.py`](../src/fatebridge/core/moshier_solar.py)，数值检查见 [`audit_solar_model_reference.py`](../scripts/astronomy/audit_solar_model_reference.py) 和 [`audit_complete_moshier_accuracy.py`](../scripts/astronomy/audit_complete_moshier_accuracy.py)。原始数学依据为 [Moshier AA5.6](https://www.moshier.net/) 的 `gplan.c`、`ear404.c`、`epsiln.c`，原表整数及独立作者C实现的位置和导数另行核验。

更广原队列中仍发现15个1秒超差，不能推广为全时域通过。DE440比较共享轨道谱系，不是独立物理观测，也不认证历史／未来UTC。风水原5秒候选保留策略不变，与1秒数值验收分别报告。

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

构建器下载并核验固定原包、32个计算源码文件，再调用本机 C 编译器。离线原包可用 `--swiss-archive`、`--aa56-archive` 指定，字节须匹配来源配置。构建须使用当前来源配置与范围；不载入不同配置生成的清单。

已记录的实际构建平台为 macOS arm64；Linux 构建分支尚未验收，Windows 不支持该构建器。算法来源与当前构建参数见[AA1996来源配置](../src/fatebridge/data/astronomy/aa1996-solar-v1.json)。

## VSOP2013

```bash
uv run --locked --extra dev python -m fatebridge.fetch_vsop2013 --output /absolute/new-vsop2013-build
export FATEBRIDGE_SOLAR_TERM_MODEL=vsop2013
export FATEBRIDGE_VSOP2013_MANIFEST=/absolute/new-vsop2013-build/manifest.json
```

离线构建用 `--source-dir` 提供匹配来源配置的文件；`--compiler`、`--linker` 可选择已有工具链。系数与时间转换代码编入本地库，运行时无需 Python ERFA、jplephem 或外部星历文件。清单须由当前构建器按已声明来源生成。

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

## 当前验证与范围限制

数值验证使用具名来源、完整固定队列和原1秒 TT 线；不能按某模型较容易通过的样本子集更换参考或放宽门槛。领域消费方还须检查所需年边界、整条年序和当前模型是否相同。原版Moshier的12项失败与当前完整修订的通过分别保留；可选二进制模型的通过也不能替代这两者各自的实际验收。

DE440对照不认证绝对 UTC、历史 UT1、全部连续时点、完整原典、自由解释或现实预测。当前支持范围以各加载器来源配置与公开请求 Schema 为准；构建平台、部署与真实模型行为须分别验收，不从文件存在或旧运行报告推定完成。领域层的来源和条件解释见对应[专题入口](README.md#计算原理与专题)。

共享节气入口只返回实际求解并绑定当前来源的交点。选择 Native 后缺少依赖或未找到交点，返回 `solar_native_unavailable`（503、不可重试）；来源回执不足返回 `solar_term_source_unverified`。1900年线性固定气回退已移除。民用月中只用于 Native ±30日搜索的初始定位，不作为节气值或误差界。

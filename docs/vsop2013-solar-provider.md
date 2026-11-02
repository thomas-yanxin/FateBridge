# VSOP2013 太阳核心提供器

`fatebridge.core.vsop2013_solar`提供明确具名的太阳黄经与TT求根接口。R98已将它接到全局模型选择、缓存、河洛／参评等领域消费者及REST/MCP/CLI来源回执。使用前需单独构建并配置实际清单；默认仍为`auto`，选择新模型不授予准确性或传统解释认证。

该模型使用完整VSOP2013地月质心、完整Moshier月球偏移、完整地心ERFA TT→TDB及Swiss2.10.03视位置流程。系数和时间转换代码编入本地库，运行时不需要Python ERFA、jplephem或外部星历文件。原生Moshier控制与已有默认DE440路线保持各自身份。

## 构建与调用

源码环境统一使用uv：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m fatebridge.fetch_vsop2013 --output /absolute/new-model-directory
```

构建器下载并核验固定来源，保留原始材料、编译日志、源码图及清单；输出目录必须是新目录。离线构建使用`--source-dir`，目录内文件名和字节需满足已发布的来源配置。`--compiler`与`--linker`可显式选择本机已有工具链。本轮macOS实际使用`/opt/homebrew/opt/llvm/bin/clang`和`/opt/homebrew/opt/lld/bin/ld64.lld`；这些路径不是其他机器的默认前提。

```python
import os
from fatebridge.core.vsop2013_solar import (
    longitude_crossing_tt,
    solar_longitudes_tt,
)

os.environ["FATEBRIDGE_VSOP2013_MANIFEST"] = "/absolute/new-model-directory/manifest.json"

points = solar_longitudes_tt([2451545.0])
crossing = longitude_crossing_tt(285.0, 2451545.5, 2451556.5)
assert points["model"]["model_id"] == "fatebridge_vsop2013_solar_v1"
print(points["longitudes"], crossing["jd_tt"])
```

公开计算选择同一份已构建的库：

```bash
export FATEBRIDGE_SOLAR_TERM_MODEL=vsop2013
export FATEBRIDGE_VSOP2013_MANIFEST=/absolute/new-model-directory/manifest.json
```

显式模式的日历输入范围为1700—2300年。缺清单、来源变动或库不符返回既有来源错误，不静默换用另一模型；与严格原生JPL配置冲突时先报配置错误。只查文本而未实际消费太阳坐标的工具不会加载可选库，其运行回执注明来源尚未被业务输出观察。参评具现代立春映射的两种八字配运方法仍返回原120条年序和121个立春边界，晚端可派生至2420年；这不扩张公开出生输入或完整节气年表范围，也不补造旧命宫方法未知的UTC映射。

输入是TT儒略日。求根括区必须跨越向前的目标太阳黄经；结果保留`bracket_tt`、`bracket_seconds`及实际载入模型的`model`回执。`cache_key()`和`expected_source_key`可绑定连续计算使用的来源。不得把返回的内部260标志当作原生Moshier身份；轨道模型身份由独立标识和源码图给出。

## 来源和失败处理

来源配置在[模型配置](../src/fatebridge/data/astronomy/vsop2013-solar-v1.json)，包括原始文件地址、散列、完整系数打包散列和计算源码图。实际计算入口、模型标识、ABI、平台、清单和二进制都需匹配；装载器用核验后的私有副本，并观察实际函数所在映像。

只有受检查的太阳坐标入口对外导出，原始Swiss坐标入口在该库内私有。未初始化、非有限或范围外TT均返回明确失败并清空坐标。Python层拒绝错误来源、载入中变化及计算异常，不换用另一条计算路线。来源类异常保留既有非重试503契约。

模型修订`1.0.1`还检查内部地月质心求值的失败状态，拒绝部分或非有限向量；失败后清空该私有库的计算缓存，避免已报错的时刻污染后续计算。旧`1.0.0`清单不满足新来源配置，需用当前构建器重新构建。完整故障注入记录及本轮验收见第47轮审计（本地数据：`validation/liuyao-v47/README.md`）；其中故障案例是工程检查，不增加独立天文样本。

修订`1.1.0`固定已审阅完整来源配置的canonical SHA-256，拒绝重复键和非空来源／范围／计算图替换；配置读取异常也转换为既有非重试503来源错误。旧`1.0.1`清单需用当前构建器重新构建，不覆盖旧库和旧证据。

库的工作TT区间现为1684年初至2421年初。完整节气队列资格仍为1684—2304年；另有2305—2420年116个立春、目标黄经315度的派生资格，用于参评120年时间线。后者没有扩为这116年的完整节气队列。日历输入年份为1700—2300；工作TT范围不等于对所有民用历法、闰秒、历史UT1或所有连续时点的准确性认证。

## R46／R47历史验收

- 原14,904个节气根：原1秒TT门槛下0超差，最大0.446105秒；与第45轮研究结果逐点相同。
- 从修订wheel、仅默认依赖安装后构建出的库：再次实际计算全部14,904个根，结果逐点相同。该环境没有Python ERFA、jplephem、Skyfield或pytest。
- 同一组33项输入、清单和真实编译库错误处理检查，在源码和安装包两层均通过；两层不能相加为独立样本。

完整记录、初败日志和边界见第46轮审计（本地数据：`validation/liuyao-v46/README.md`）。验收平台为macOS arm64、Python3.12.13；本轮没有执行Linux构建或部署验收。数值资格不代表整部原典符合、真实模型解释满分或现实预测有效。原生Moshier、旧研究候选和共享套件的失败记录分别保留。

## R97提供器历史验收

源码和独立默认依赖安装包分别通过全部15,020项TT对照：原14,904点逐点与旧候选相同，对原DE440参考最大差0.446105秒；新增116个未来立春最大差0.816974秒，均在原1秒TT线内。参考先封存，候选不以参考根作初值。两层重放不能相加为独立样本。

原33项检查保留，新增11项来源变异及范围控制，共44项在最终源码、独立安装包和当轮工作区均通过；默认河洛／参评完整业务对象与修订前相同，对应REST、CLI和进程内MCP字段一致。当轮只验默认兼容性，公开工具在R98接入。

完整原始行、首次失败、构建／类型证明、来源依赖和后续接入要求见第97轮审计（本地数据：`validation/numerology-vsop-projection-audit.md`）与冻结证据（本地数据：`../tests/fixtures/vsop2013_projection_v1/README.md`）。原生96项仍为84通过／12超差；未完成全仓CI、Linux或部署验收，也未重连当前聊天MCP。

## R98领域接入与混源修复

显式模型连接到节气、参评派生立春、壬课黄经复查、风水边界提示及实际来源回执。还修复了原自动／原生路线中短暂配置切换后恢复可能把不同模型根混入同一缓存年表的问题：所有交点改用同一份已捕获的模型选择。

候选源码和独立默认依赖安装包各完成15,020项原参考重放，最大TT差0.816974秒，原1秒线不变；两层不能相加为独立样本。638模块回归含405失败、139错误和84跳过，保留全部节点及修订前比较，不能报告全仓全绿。完整范围、主工作区验证、初败和外部依赖见第98轮审计（本地数据：`validation/numerology-vsop-integration-audit.md`）。原生12个超差、未校原典、模型解释与现实预测缺口均未被本轮消除。

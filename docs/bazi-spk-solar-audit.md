# 交节分钟判定与JPL SPK太阳后端

本页保存本轮当时的默认路径与首跑结果。后续源码开始接入[随包DE440默认路径](bazi-de440-default-audit.md)，其完整验收与本页分开；本页原默认解析反例和原生控制组不回写。

新增显式SPK太阳模型`fatebridge_jpl_spk_solar_v1`，供需要更高交节精度且已准备星历文件的部署使用。它直接读取地球、地月质心及太阳的原始轨道向量，未读取基准交点作运行数据。默认`auto`行为保持；新路径不代表现有连接已更新，也没有把原生Moshier更名为JPL。

## 一秒内仍可能换错月

事前固定方案（本地数据：`../tests/fixtures/bazi_boundary_decisions_v1/protocol.json`）覆盖既有1899—2101年4,872个DE440/Skyfield交点。每个交点按明确的民用时标政策取所在整分钟和下一分钟，先冻结全部9,744个输入（本地数据：`../tests/fixtures/bazi_boundary_decisions_v1/probes.json`），再检查实际年柱、月柱、流月及流日窗口。端点缺少前／后参考的项保留未知，没有删除记录。

| 实际太阳路径 | 原一秒TT门槛超差点 | 节气侧不符 | 年界不符 | 月界不符 |
| --- | ---: | ---: | ---: | ---: |
| 配置Swiss文件、原生模式 | 0 | 1 | 0 | 0 |
| 空目录、原生Moshier | 501 | 42 | 2 | 18 |
| 空目录、默认解析模型 | 0 | 5 | 0 | 4 |
| 显式SPK、完整DE440 | 0 | 0 | 0 | 0 |

一秒是原数值比较标准，不保证这一秒内所有整分钟输入都在交点正确一侧。默认解析模型仍有1922清明、1964惊蛰、1975芒种、2022小暑四个月界反例，另有1980夏至的节气侧反例；配置Swiss文件仍有1936雨水的节气侧反例。它们与原501个Moshier失败完整保存在首次实际回放（本地数据：`validation/bazi-boundary-decisions-first-v1.json.gz`）中。

首轮验证器把流日底层`solar_term_window`误当作相邻二十四节气，产生了大量错误判据。实际该字段取自八字月令的十二“节”窗口；二十四节气另见`analysis_calendar.analysis_date_context.current_solar_term/next_solar_term`。原执行器、所有原始失败与实际计算值均保留，复核（本地数据：`validation/bazi-boundary-windows-adjudicated-first-v1.json.gz`）只更正这两个窗口期望，其余七项向量和原一秒门槛逐项不变。这是验证器勘误，没有记成算法改善。

## 物理来源与实现

原生Moshier及简化解析轨道都有自身位置误差，增加求根次数不能消除。[ERFA epv00说明](https://raw.githubusercontent.com/liberfa/erfa/9915ba38c9365f8b0738269b8c2ac1fdd5f8dee3/src/epv00.c)列明其简化VSOP2000模型及比较范围。本次物理候选（本地数据：`../tests/fixtures/bazi_boundary_decisions_v1/spk-experiment-protocol.json`）改用SPK的`0→3`地月质心、`3→399`地球和`0→10`太阳向量；地月质心不能直接充作地心。

[jplephem](https://github.com/brandon-rhodes/python-jplephem)读取原始Type2轨道数据，要求分段采用SPK参考系1（J2000/ICRF），按最后适用的分段选取实际TDB覆盖区间。TT通过[ERFA dtdb](https://raw.githubusercontent.com/liberfa/erfa/9915ba38c9365f8b0738269b8c2ac1fdd5f8dee3/src/dtdb.c)转为地心TDB，再作三次太阳光行时迭代、周年光行差及IAU2006/P03、IAU2000B日期真黄道转换。[NASA时标说明](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/time.html)区分这些时间坐标；不把求根TT、SPK的TDB和现实UTC混成一项。天文单位采用[IAU2012决议B2](https://www.iau.org/static/resolutions/IAU2012_English.pdf)的精确定义。

开发比较先保留全部旧交点与分钟输入（本地数据：`validation/bazi-spk-sun-development-first-v1.json.gz`），再以方案散列确定512个通用TT时点（本地数据：`../tests/fixtures/bazi_boundary_decisions_v1/generic-epochs.json`），在生成参考后才比较候选。通用比较（本地数据：`validation/bazi-spk-sun-generic-first-v1.json`）全部满足原一秒时间等效门槛，没有更换采样点或拟合修正项。

实际接入后的完整生产函数回放（本地数据：`validation/bazi-spk-public-boundaries-accepted-v1.json.gz`）仍计算全部4,872交点、9,744探针，最大TT实现差约0.000121秒，所有可判项无不符。首次接入回放曾因共享工作区的历法文件并行改变而中止（本地数据：`validation/bazi-spk-public-first-aborted-v1.json`），未计通过；接受的回放改从不可变源码快照执行。

完整数值回放之后，另外修复了交点短暂切换来源后恢复时可能污染整年缓存的问题，并改为记录实际载入模块的版本，避免并行安装器移除元数据而使回执失败。最终版本还明确拒绝其他SPK参考系。前后源码和首次失败均保留；证据测试逐项比较轨道向量、分段选择与求根部分的语法树，确认这些修复未改变已回放的数学。最终版本的接口与故障检查另行运行，没有把不同源码快照称为同一份完整数值首跑。

参考与新实现共享JPL内核及底层插值库；上述结果比较了不同时间／视位置／求根及消费端实现，不是独立物理观测。IAU2000B模型、历史民用钟时、未来闰秒假设及输入精度的原有范围继续存在。只有年、月与交节窗口在本队列中比较，不能把保存了四柱对象称为日、时柱也获得新的独立认证。

## 启用和失败语义

当前源码或对应构建包需要安装可选`jpl`依赖，并准备覆盖目标日期及太阳光行时的Type2 SPK文件。本轮使用[NASA完整DE440](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp)，实际SHA-256为`a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5`；没有自动下载或将120MB内核塞入软件包。

本机已将现有内核按相同散列复制至下述`ephe/solar-de440.bsp`，由Git忽略；其他部署需自行准备文件。未修改共享MCP启动配置或重启其他聊天使用的进程。

```bash
uv sync --locked --extra dev --extra jpl
export FATEBRIDGE_SOLAR_TERM_MODEL=spk
export FATEBRIDGE_SOLAR_SPK_FILE="$PWD/ephe/solar-de440.bsp"
uv run --locked --extra dev --extra jpl fatebridge jieqi_year --year 2022
```

SPK模式与原生Swiss直接访问JPL文件的`FATEBRIDGE_JPL_FILE`分开，不能同时作为同一太阳来源选择。新路径只控制共享交节求解，不把其他原生星体或真太阳时计算也标为已切换SPK。宿主需在自己的MCP启动配置中提供环境；源码／包内验证不等于已有长期连接的部署验收。

缺少可选依赖、文件不可用、格式／身体分段不符、范围不足或计算中源文件改变时明确报错，不偷偷退回原生、解析或线性近似。缓存绑定规范化路径、文件身份／散列及实际载入的参考系系数；返回的是实际文件来源，文件名本身不认证NASA来源或权威性。基础安装的`auto`仍无需这组可选依赖。

## 接口和验收范围

十个八字入口及流月、流日、流时、六爻、六壬、金口诀分别检查REST、原生MCP、CLI的同一结果与实际模型。返回`resolution_provider=jpl_spk`、实际内核散列、TDB覆盖、软件版本与时标方法，不借用Swiss原生返回标志。`accuracy_certified=false`继续保留。

首轮接入测试72项通过、3项失败，错误码注册位置及冲突文案修复后75项通过；后续来源切换、版本回执、参考系和证据保护检查加入后，源码共86项通过，最终冻结包内26项通过。源码和包内新进程MCP各对五个关键反例读取同run投影结果，页数均为10、11、11、11、11，并校验还原后的散列；这不认证任意自由文本。完整日志、包散列和当前范围见本地验收（本地数据：`validation/bazi-spk-solar-local-v1.json`）。

共享工作区仍有其他领域并行修改。最终包的899个运行时文件与该次冻结源码逐项相同；后续环境回执、其他领域时标说明和错误码的变动另记散列差异，不将包内验收归给任意后来的整个工作区。

本轮没有新增模型代理调用、古代强弱标注或现实预测样本。原典26个不同输入分歧、独立原典专家审查及更广解释验收仍未完成；知识缓存的“新散列配旧正文”假说在已观察连接上没有得到证明，本轮未改变其部署缓存语义。历法组件的改进不换算为三项满分或权威认证。

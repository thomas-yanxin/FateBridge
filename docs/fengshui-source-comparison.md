# 宅盘运行结果中的原书数表差异

[216条正文校勘](fengshui-lower-clause-collation.md) · [下卦盘图](fengshui-lower-diagram-collation.md) · [起星盘图](fengshui-replacement-diagram-collation.md) · [玄空调用](fengshui-xuankong.md)

已知的校勘差异随相应宅盘返回，供解释引用。`layers.xuankong_natal.source_comparison` 逐候选比较固定整理本的下卦正文与盘图、起星图数字，`coverage.natal_source_comparison` 提供摘要。快照和启用的固定释义同时保留原书值、计算值与所引卷别。起星正文、星名和兼向选盘条件仍未验证。

兼向角度另按[单位、起点与类别条件](fengshui-angle-source-audit.md)逐项校勘。王氏中央9度说明及《玄空辑要》的类别条件已有原页定位，但跨来源组合尚不等于单一原典的完整选盘认证；未说明的单位换算和起点不从现行算法反推。

新运行采用比较版本 `shen_2011_natal_numeric_comparison_v2@2.0.0`，与起盘的 `xuankong_zhongzhou_v1@1.4.0` 分开。它采用沈竹礽编、姚国华与柯誉整理的《沈氏玄空学》，中央编译出版社2011年6月第1版、2016年2月第3次印刷；CIP另记2011.3。完整917页PDF的SHA-256为 `b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847`。卷五《附说》PDF503另署申听禅编，起星图在PDF511–726，逐候选返回这段作者范围。底本未认证为早期六卷本，兼向条件也不自动并入中州规则。

旧 `shen_2011_lower_numeric_comparison_v1@1.0.0` 数据保持原散列。固定释义按运行记录中的比较版本选择模板，保留旧运行的逐字结果；不能把新覆盖范围追授给旧替卦结果。

## 比较内容

| 返回内容 | 具体范围 |
| --- | --- |
| `ruleset.sources` | 作者、整理者、版次、完整PDF散列及原文范围 |
| `ruleset.source_freezes` | 下卦正文、下卦盘图、起星盘图三份先于各自引擎比较冻结的转录散列 |
| `candidates.*.source_section` | 当前下卦／起星图所引卷别、作者范围、正文是否已核对 |
| `candidates.*.prose` | 仅下卦：页码、文字图像散列、山向种子与顺逆四字段，计算值和全部差异 |
| `candidates.*.diagram` | 相应页码、盘图图像散列、原图九宫27星数和全部差异 |
| `computed_plate_integrity` | 三组计算盘是否为1至9的排列，且与逐宫数字一致 |
| `source_plate_permutations` | 原图各层是否存在重复或缺数；保留原样，不作校正 |
| `source_angle_applicability_verified` | 固定为false：图数相合未验证这部书的兼向选盘条件 |

全部216条下卦正文、216张下卦图及216张起星图均打包为运行资料，由独立生成脚本只读原先冻结的来源事实。脚本不导入起盘引擎，不以计算输出生成预期。每个下卦比较四项正文值和27个图数；每个替卦只比较相应起星图27数。多个山向、下卦／替卦候选逐一保留，不按相合程度选一个盘。

摘要分别累计 `lower_candidates_compared` 与 `replacement_candidates_compared`；新版本的 `replacement_candidates_not_covered` 为0，仅表示数字图表已覆盖。候选正文未核对时，`source_section.prose_comparison_status=not_transcribed_or_compared`，不能把缺少正文当作正文通过。未算出宅盘仍为 `not_computed`。`local_numeric_agreement` 只比较已列数字成分，不能替代计算盘内部一致性或整本认证。

数表相合仅为当前候选与指定片段的数字关系。它不证明整本符合、独立人工专家校勘、完整技法、历法准确或现实预测。计算盘的 `complete` 仍表示起盘输入齐备；来源差异另列，不伪装成用户缺项。

## 计算盘异常会停止交付

原书图数与计算值不合，和计算盘内部矛盾是两种情况。七运申山寅向的原图重复五、缺二仍原样返回；本次计算的东宫山星仍为二。这一来源差异不会阻止有效计算，也不会被自动改图消除。

计算盘若出现重复、缺数、非整数、逐宫与角色表不一致，或虽然仍为一至九的排列却违反本次中心星和顺逆的飞行次序，则停止本次计算。宅运、山向、下卦／替卦身份，以及种子、中心星与顺逆记录也须彼此一致。检查在数字结构生成前及候选接受时执行，不依赖整理本原图是否相合。一个候选失败就停止，不能丢掉该候选、只交付余下结果。

公开入口返回 `fengshui_calculation_inconsistent`，REST状态503、MCP错误标记、CLI退出1，`retryable=false`。问题路径为 `runtime.fengshui.natal_chart`，只给固定原因码，不回传无效盘、释义、快照、成功运行回执或分页。`fields` 投影不能隐藏错误；这不是用户缺项，不能要求用户修改现场事实来绕过。

这些检查证明当前选择下的数字表示与飞行记录自洽。它们不证明宅运或山向测量选对、流派规则符合整部原典、历法精度或现实预测；同步改变错误规则和相应记录仍需独立原典与外部数值核查。

原盘数字有效也不保证派生字段正确。运行层另以原始三盘核对到山到向标签、三组同宫合十、父母组、固定地盘与历史运盘比较、有限下卦局名及八个有向对宫数和；中宫不参与空间对宫合取。派生值矛盾返回同一错误码、原因 `natal_structure_inconsistent`，停止后续解释。这是所选数字规则的一致性检查，不把该规则或传统局名认证为全本原典。

## 四个既有差异继续保留

| 下卦 | 原书与计算的差异 |
| --- | --- |
| 四运卯山酉向，PDF302 | 正文山向均逆，计算山向均顺；同页盘图与计算相合 |
| 一运酉山卯向，PDF307 | 正文山向均逆，计算山逆向顺；同页盘图与计算相合 |
| 六运巽山乾向，PDF324 | 正文山向均顺，计算山顺向逆；同页盘图与计算相合 |
| 七运申山寅向，PDF353 | 东宫山星原图五、计算二；原图山盘重复五、缺二 |

这些记录由逐字段比较得到，不用四个例外白名单跳过其余盘。若引擎另有数值回归，所有原格仍参与比较。反向测试把七运申寅计算盘东宫改为五，虽然能照抄原图，却不能通过计算盘排列检查；原图本身的重复数字也继续记录。不能把“照抄字面”冒充有效排盘。

## 起星图的三个数字差异

| 替卦候选 | 原图与计算 |
| --- | --- |
| 五运子山午向，PDF515 | 南宫山星原图九、计算六；原图山盘重复九、缺六 |
| 九运坤山艮向，PDF582 | 南宫山／向原图七／一、计算一／七；对应两层均有重复和缺数 |

当前中州规则可用[虚构五运174度输入](examples/fengshui-replacement-source-differences.json)复现第一项；九运39度复现第二项。这些角度只用于当前版本的合成回归，不是住宅测量，也不认证所引书的兼向适用条件。固定释义列出原图和计算值、页码、编者范围、重复缺数及尚未比较的成分，依据均来自同次结果。

## 读取同次证据

[虚构输入](examples/fengshui-source-differences.json)明确历史七运、评价九运与磁北60度，用于申山寅向差异复现，不是住宅资料：

```bash
uv run --locked --extra dev fatebridge fengshui_xuankong_natal \
  --request-file docs/examples/fengshui-source-differences.json \
  --fields layers.xuankong_natal.source_comparison coverage.natal_source_comparison
```

普通摘要可先读 `coverage.natal_source_comparison`。需要原书值、实际星数、全部来源及固定释义核验时，首次请求应保留完整字段或设 `fields=null`，再读同run `result_delivery`；分页不能恢复首次投影舍弃的字段，不能另算一次冒充原始证据。

固定释义逐候选引用来源比较记录及该次实际宅盘，明确写出差异和未覆盖状态。它不认证任意自由模型正文；旧运行没有这个新分支时，原有固定模板继续可核验。

## 生成与验证

```bash
uv run --locked --extra dev python scripts/build_fengshui_source_comparison.py --check
uv run --locked --extra dev pytest -q tests/test_fengshui_source_comparison.py
uv run --locked --extra dev pytest -q tests/test_fengshui_replacement_source_comparison.py
```

原书数据、既有不合及完整来源总闸门均保持原样。独立的原典与现实预测要求继续未完成；本次只把已经掌握的逐盘来源事实带到实际结果和解释中。

旧下卦比较的2,498项冻结回归、八工具Linux基线及24份安装包三端结果，见第二十七轮证据（本地数据：`validation/fengshui-source-comparison-v27-evidence.json`），不追授本次起星图扩展。新增范围及本次实际验收见第三十一轮证据（本地数据：`validation/fengshui-replacement-runtime-v31-evidence.json`）。测试通过均不增加现实预测成绩。

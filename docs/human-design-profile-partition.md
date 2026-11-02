# 人类图基础／过渡角色与精确太阳弧分区

新增 `profile_partition_context`，把本次实际日地线号形成的角色，与由人格太阳精确回退 88° 得到的理想分区分开记录。实际设计太阳仍来自原生求根结果，不用理想点替换，也不因边界差别改写角色。

## 来源及范围

[Jovian 公开词典](https://jovianarchive.com/pages/human-design-dictionary)的 Profile Foundation / Profile Transitions 条目给出：每线 56′15″，其中前 48′45″为基础区段，后 7′30″为过渡区段。基础角色为 1/3、2/4、3/5、4/6、5/1、6/2；过渡角色为 1/4、2/5、3/6、4/1、5/2、6/3。这些角宽不直接换算成人群比例。

词典在基础角色条目中使用 `Resonances`，同页一般 Resonance 条目又指不同卦中的同号线。本实现保留两种原有上下文，将其记录为未裁定的用词疑点，不擅自替换为 Dissonance，也不从该词推断基础角色的两个数字相等。

另核对了出版方域名提供的《Rave Cosmology VI: Profile, Purpose and Function》11 页样本：印刷第 3 页支持六种过渡角色名单，第 5 页的太阳弧章节没有包含在样本中。《The Lines of Consequence》8 页样本公开了开头的整体语境说明，后续线义和共振章节没有公开；未以目录替代已读正文。来源记录见本轮验证目录。

这项能力提供角度分类与实际计算包的对应关系。完整 384 线语义、全部 fixing、29.1/29.2 印刷分界、周期起点与多次交会取舍，仍分别保留原有未通过或未完成状态。

## 返回值

| 字段 | 含义 |
| --- | --- |
| `actual_profile` / `actual_profile_category` | 本次实际人格／设计日地线号及其基础／过渡分类 |
| `ideal_partition` | 将人格太阳的实际 binary64 值视为精确有理数，回退 88° 后分类；不是新的天文观测 |
| `actual_profile_matches_ideal_partition` | 实际角色是否与理想角度分区的角色一致 |
| `actual_solar_arc_residual_degrees_ratio` | 两个实际太阳坐标相对 88° 的有符号精确分数，单位为度 |
| `basis` / `ruleset` | 本次实际字段路径、独立版本、作者及来源范围 |

分数使用 `["分子", "分母"]` 十进制字符串，保留整数精度。例如已保存的虚构 `3/6` 案例，理想设计点的分子是 `11188641789053351`，超出 JavaScript 的安全整数范围；传输中不把它改成 JSON 数字。该例实际太阳弧残差为 `["7779", "35184372088832"]` 度；角色与理想分区一致不等于天文误差为零。

若实际设计太阳落在理想分界的另一侧，返回两种结果，并在文本中说明差别。原有 `profile`、`profile_evidence`、激活及求根规则保持原样。新解释只对应名义盘，不能拼接另一时刻或另一后端的激活。

## 调用

以下为工程验证使用的虚构输入，不代表已确认的个人出生记录。

```sh
uv run --locked --extra dev fatebridge human_design \
  --birth-year 1981 --birth-month 5 --birth-day 6 \
  --birth-hour 16 --birth-minute 22 --birth-timezone Europe/London \
  --fields profile profile_partition_context interpretation.profile_partition_context \
  --strict-fields --no-include-snapshot-text
```

已发布 `evidence_views.human_design.profile_partition`；视图名称不是请求参数，使用其 `fields`。完整导出仍读取同一 run 的交付记录，摘要不冒充完整回执。

## 验证状态

在实现前冻结了 3072 个独立有理数参考（本地数据：`../tests/fixtures/human-design-profile-partition-reference.json`），覆盖 64 门、每线的两个分界、分界前后相邻 binary64 值及两段内部点，包含 0° 的负次正规数环绕。参考生成器不导入生产引擎。

39 项专项测试通过。8 组前后对照在移除声明的新增区段后，原业务字段与原生调用记录逐项一致。原 38 项专业验收已重算，标准和状态完全未变，仍为 4 项失败、3 项未完成；两份天文参考报告与现实预测记录未变。详细记录见本轮验收（本地数据：`validation/human-design-profile-continuation-v1/README.md`）。

同一个 wheel 在 macOS 和断网 Linux 中，各有 33 次完整 REST / 外部 stdio MCP / 外部 CLI 调用及 21 次严格投影通过，包含上一轮原有案例与 8192 字符周期卡片。这里是本地安装包协议验收，不等于部署验收。当前聊天已有 MCP 连接的单次探测返回 `dependency_missing`（503、不可重试），尚未重载并核验；界面重载操作被电脑工具安全检查拒绝。

**Linux 专项为 79 通过、1 失败，失败保留。** 旧 macOS 回执的跨平台回放中，太阳投影角的浮点末位发生差别，严格几何重建拒绝该回执。相同输入的逐步探针已定位到 `sin` / `cos` 返回值的末位差别；没有修改投影的 `1e-12` 算术分界、比对标准或失败用例。[Python 文档](https://docs.python.org/3.12/library/math.html)说明大部分函数包装平台 C 数学库。该跨平台回放问题是新增未决项，不能用新生成回执在各自平台通过来替代。

2457 项完整回归在独立冻结副本中全部通过；上一轮的 2418 个节点全部保留。运行后核对 17329 个冻结输入，全部未变。首次副本遗漏共享测试助手及部分夹具，19 个收集错误已保留；补齐输入后的副本未修改生产代码或断言。运行期间共享工作区的 CLI、错误处理等有并行改动，完整回归只对应冻结副本；当前工作区另补跑相关接口及交付测试，56 项通过，所记录的 1941 个相关输入在执行期间未变。

原 768 个官方组合的输入及旧失败集仍保持冻结。该次角色扩展采集并核对 96 份官方图表，覆盖前 8 门的全部 12 个角色；剩余 672 个组合明确列出。2496 个门／线号、96 份结构和固定模板回执核验全部一致，原典与当前官方展示的交叉名称仍有 69 份字面不一致，均保留失败。该样本使用事先由引擎辅助规划的虚构输入，不是盲测或现实预测样本。每份 PDF 独立核对 13 项属性；门／线、中心及通道来自网页 SVG，未冒充 PDF 图形的独立转录。旧 36 份原始记录是新记录的逐字节前缀，旧 93 个封存文件全部未变。

前次完整集合与失败保留复核（本地数据：`validation/human-design-profile-cohort-integrity-v1/README.md`）扩展至288/768份，保留179个名称失败和480个缺项；此前192份逐例检查完全相等，原135个名称失败全部保留。该角色扩展的96份原始封存也保持不变。先前2470项冻结完整回归另见投影算术复核（本地数据：`validation/human-design-portable-projection-ci-v1/README.md`），原典与完整解释的专业要求继续单独验收。

最新完整768组合复核（本地数据：`validation/human-design-profile-all768-v1/README.md`）已收齐原定全部观察，实际显示的64门×12角色均匹配，无重复或缺项。768份与原19／193例共同核验，25480个门爻、980份机械字段及固定模板一致；名称失败15／86／487全部保留，联合命令仍退出1。此前596例的逐项检查完全相等，447／384检查点（本地数据：`validation/human-design-public-source-continuation-v1/README.md`）没有重写。29号争议点的独立DE440与当前官方图表支持等分线界，但2001版印刷分歧、完整原典与现实预测要求未关闭；这批工作没有再修改角色分区算法或共享验证规则。

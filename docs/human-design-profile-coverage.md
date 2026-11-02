# 人类图角色覆盖与新增精度反例

原计划的 **768/768** 份官方观察、PDF属性绑定及计算联合审计现已完成，见完整矩阵与全部失败记录（本地数据：`validation/human-design-profile-all768-v1/README.md`）：19968个门爻、768份机械字段和固定模板核验一致，**487个轮回交叉字面名称失败**，没有观察或审计缺项。新增独立检查器核对实际显示的太阳门／角色，而非只凭案例ID计数，768个不同组合全部匹配；严格完整性来源命令退出0，联合符合性命令仍退出1。此前447份采集／384份审计检查点（本地数据：`validation/human-design-public-source-continuation-v1/README.md`）、288份封存（本地数据：`validation/human-design-profile-cohort-integrity-v1/README.md`）、192份检查点（本地数据：`validation/human-design-portable-projection-ci-v1/README.md`）、144份检查点（本地数据：`validation/human-design-portable-projection-v1/README.md`）及96份检查点（本地数据：`validation/human-design-profile-continuation-v1/README.md`）保持不变。[角色角度分区能力](human-design-profile-partition.md)另有独立来源与计算验收。

当前审计协调器完整保留原19例（8＋11）、193例及本批768例，合计980例分别报告；共享词汇门槛、名称比较和领域计算均未改动。25480个门爻及980份机械字段全部匹配，980份固定模板通过；名称失败仍为15／86／487，共588例。此前596例的逐项官方检查完全相等，前384例的237个失败保留，后384例新增250个失败。原集合包含的四分定义、无定义等少见分支继续参与核对，没有放宽未知词汇。

完整矩阵的487个名称失败可按事实诊断为414个原书变体编号未显示、73个其余字面差异；同四门同角度的192组官方名称在各角色间均稳定。分类与原字面比较器逐例一致，原书编号和拼写没有被替换，诊断没有把这些失败改判为通过。

新增29号争议点以独立DE440确认当前官方图表采用29.1／30.1；照搬2001版印刷区间会成为29.2／30.1，固定解释已披露其条件性影响。单点太阳黄经差约0.000653″，原2″阈值未改，出版方勘误仍未取得，不能据此关闭原数值和完整语义验收项。

以下保留首次 **36/768** 检查点的记录：该阶段完善外部证据的采集、绑定与验收链，未改动生产计算或解释规则。36 份有限结果不能认证完整原典、完整解释、全历法范围或现实预测；其原始文件、18 个名称失败及新增 Moshier 反例均未修改。

## 已核对的有限范围

在读取新官方结果之前，已冻结 768 个合成输入（本地数据：`../tests/fixtures/human-design-profile-coverage-plan.json`）：64 个门，各取 12 种角色。输入选择使用当前引擎，因此不是盲测；取 1981 年的角度区间内部时刻，四舍五入至 UTC 分钟，再转换为伦敦当地时间。与原有 19/193 例没有输入重叠。

已完成第 1、2、3 门的全部 12 种角色。资料来自 [Jovian 官方公开图表页](https://jovianarchive.com/pages/get-your-human-design-chart)的正常表单操作，没有使用邮箱、账户或直接计算 API。网页 13 项属性逐例与原始 PDF 文本交叉核对；26 个门爻、中心和通道来自显示的 SVG，未声称 PDF 图形得到独立二次转录。

| 检查 | Swiss 文件模型 | 首次复制遗漏星历后的 Moshier 模型 |
| --- | --- | --- |
| 门爻 | 936/936 一致 | 936/936 一致 |
| 完整机制，含变量码 | 36/36 一致 | 35/36 一致 |
| 轮回交叉字面名称 | 18/36 一致，18 例失败 | 同样保留名称分歧 |
| 固定模板解释忠于实际计算包 | 36/36 核验 | 36/36 核验，不代表计算准确 |

名称只允许空白和大小写规范化，不删除原典变体编号，不以别名放行。原有 19 例中的 15 个名称失败、193 例中的 86 个名称失败及其资料保持原样，新结果不替代它们。

## 新增可复现反例

合成案例 `profile-02-3-6`，出生 UTC 为 `1981-05-06T15:22:00+00:00`：官方 PDF 的变量码为 `PRR DLL`；Swiss 文件模型一致，Moshier 返回 `PRR DLR`。设计北交点的细分由 Swiss 的 Color 4 / Tone 1，变为 Moshier 的 Color 3 / Tone 6，设计交点箭头翻转；门爻仍然一致。

两模型各自在其设计时刻的交点位置相差约 10.15″。又在两个相同 TT 时刻分别对照两模型，仍观察到约 10.15″ 的差异；该探针使用从已保存名义 UTC 换算的 TT，不冒充原始求根的精确二进制点，也不声称官方图表提供了数值经度真值。见完整反例（本地数据：`validation/human-design-profile-coverage/model-counterexample.json`）及同 TT 探针（本地数据：`validation/human-design-profile-coverage/same-tt-node-probe.json`）。

首次冻结测试结果是 **13 通过、1 失败**，已保留失败日志（本地数据：`validation/human-design-profile-coverage/fallback-replica-v1/frozen-tests.log`）与完整计算包。补齐原项目星历文件后，生产源码、测试与断言均未改变，重新冻结的 **14 项测试通过**。恢复文件没有消除 Moshier 模型的实际反例，也没有扩大 Swiss 的已证范围。

## 解释与原典还缺什么

36 份完整计算包通过当前固定模板核验，只证明这些文本与其计算、引用和内部推导一致。没有新增独立模型留出集，未完成全部 384 爻辞、全部 fixing 或任意咨询文本的原典语义验收。

另核对了出版方链接的 [Ra Uru Hu《The Kiron Return》样本](https://jovianarchive.com/products/the-kiron-return-the-sixth-line-being-and-coming-off-the-roof-by-ra-uru-hu)。取得的旧版样本只有 5 页，未包含后续算法章节，不能裁定周期的 Personality/Design 起点或逆行时多次交会的取舍。来源元数据（本地数据：`validation/human-design-profile-coverage/source-research.json`）保留具体链接、文件哈希、PDF 元数据与未解决项，不以目录代替已读正文。

原 38 项标准仍为 **4 项失败、3 项未完成**；本轮没有重认证或降低这些标准。原验收记录（本地数据：`validation/human-design-profile-coverage/preserved-original-acceptance.json`）保留全部项目与范围。29.1/29.2 印刷边界冲突、原有天文精度失败、来源真实性与完整语义问题仍未解决。现实预测样本量仍为 0。

## 复核与后续入口

最终记录见验证摘要（本地数据：`validation/human-design-profile-coverage/verification.json`）、36 例独立属性绑定（本地数据：`validation/human-design-profile-coverage/through-036/cohort.json`）及冻结 Swiss 复核（本地数据：`validation/human-design-profile-coverage/frozen-swieph-v2/audit/checks.json`）。冻结输入共 2093 个文件，检查后哈希漂移为 0；生成的 pytest/Python 缓存不计入运行输入。85 个人类图生产、资料和原验收脚本与上一份接受版本一致。本轮未重跑上一轮的完整 2418 项回归，也没有新增或修改 REST/MCP/CLI 契约。

```sh
uv run --locked --extra dev python scripts/build_human_design_profile_coverage.py \
  --observations docs/validation/human-design-profile-coverage/through-036/observations.jsonl \
  --pdf-directory docs/validation/human-design-profile-coverage/through-036/pdfs \
  --output /tmp/hd-profile-cohort.json
uv run --locked --extra dev python scripts/audit_human_design_profile_coverage.py \
  --cohort /tmp/hd-profile-cohort.json --output-directory /tmp/hd-profile-audit
uv run --locked --extra dev pytest -q tests/test_human_design_profile_coverage.py
```

输出路径必须尚不存在。上述首次36份检查点加`--require-complete`会因缺732个组合而拒绝；不得改用通过的小批次冒充完整覆盖。浏览器采集器仅由`cua_repl`注入已授权标签页后运行，进度由已保存ID前缀恢复。此前384／447前缀的严格完整性失败及浏览器中断记录继续封存；第448例等已提交结果随后按可见身份恢复保存，未盲目重提，完整768例的来源完整性现已通过。新观察组合检查器在旧384集合上仍实际退出1，缺384项，不把历史前缀重标为完整。原768输入没有夏令时跳时／重复时刻，因此本矩阵不能替代这些历法边界的独立验收。各阶段保留每个失败和缺项，完整矩阵仍不能替代完整原典解释及全范围精度的独立证据。

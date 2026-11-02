# 当时法完整原例与四维两支候选

三式宫位对应现在把四维的同方位两支一并交付。例如太乙巽九对应奇门巽四，同时列六壬地盘辰、巳的实际天盘支与神将。`status=not_assessed`继续表示寄支未定，`sector_candidates`是并列事实，不能任选一支下结论。子卯午酉仍直接对应，中五不寄坤；几何联接规则实现版本升为1.1.0。

依据是[《金镜》卷二](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02)的乾一戌亥、巽九辰巳，以及[卷九](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷09)东北三与西南未申对冲等约束。沿用先前已冻结的全十六神方位预期（本地数据：`../tests/fixtures/taiyi_gate_sectors_v1/sectors.json`），四维候选为乾戌亥、艮丑寅、坤未申、巽辰巳。这是同扇区几何推论，原句未指定唯一寄支，不能把方位映射反转为完整寄宫法。

## 原例逐层核对

[NCL明钞原件](https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf)第24页与[四库CADAL原件](https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu)第56—57图，同举十月五日庚申、寅时、立冬气六的阴27局。四库明列戊寅，明钞仅列寅，不补写其时干。两图元名字形照录为“五子元”，网络转录作“壬子元”，保留疑读，不据字形改算入纪。原例没有公元年，不能构造完整日期或验证从日历到积时的上游。

这不是新增独立古例：V2已含该例十项核心位置与主客算。此次把两本所乘神及完整条件连接起来，原图、读数、手推条件预期和既有成绩在新数值审计与生产修改前冻结（本地数据：`../tests/fixtures/taiyi_dangshi_case_v41/freeze.json`）。整理者已知旧结果和现有贵人表，非盲读，独立人类校审0。

源例说日在心宿；卷一十二分野将氐房心归卯，因此以卯加寅作为明确条件。这一步读取给定日宿，不证明古代太阳位置或中气换将边界。源例明确朝治大吉，按朝条件用庚日丑贵，两版贵人表在庚日相同。生产六壬现有布将步骤抽成无日期纯函数，正常六壬盘也调用同一函数，不在审计脚本另写一套布将算法。

| 原例将位 | 六壬实际地盘、天盘与神将 | 源例所乘神 | 核对范围 |
| --- | --- | --- | --- |
| 太乙巽九 | 辰／巳／勾陈；巳／午／青龙 | 青龙 | 候选之一相容，寄支未定 |
| 主大巽九 | 辰／巳／勾陈；巳／午／青龙 | 青龙 | 候选之一相容，寄支未定 |
| 主参坤七 | 未／申／白虎；申／酉／太常 | 太常 | 候选之一相容，寄支未定 |
| 客大震四 | 卯／辰／六合 | 六合 | 单支直接相符 |
| 客参离二 | 午／未／天空 | 明钞天空、四库天定 | 明钞直接相符，四库原字未识别，不默改 |

明钞五项均与同扇区候选相容，其中只有两项为单支直接相符；四库四项相容、仅一项直接相符，末项异文保留。三个四维行均未选寄支，所以两本完整原例均未通过。两种已有贵人配置与朝／暮各一轮共四组诊断，不算四条独立古例或预测样本。

当前自动寅时选择夜贵，与原例明确朝条件不同。按夜条件核对，两本均只剩客大六合一项相符。审计保留该负对照，不为提高相符率自动改昼夜、切换版本或选择邻支。古代朝暮边界仍待原典裁定。V41完整报告（本地数据：`validation/taiyi-jinjing-v41/report.json`）保留所有行及未决状态，报告正常写出后退出1。

## 调用与解释

沿用已发布的`palace_correspondences`选读视图，或直接选`synthesis.palace_correspondences`。四维行的`liureng.sector_candidates`保留每项`source_path`、`earth_branch`、`sky_branch`、`god`，同时给出`candidate_scope=same_sector_branches_not_adjudicated_lodging`与来源网址。路径指向同一run的实际六壬十二盘，不重算、不按神将优劣排序。快照和导出也明确写“未选寄支”。

```sh
uv run --locked --extra dev fatebridge sanshiunited \
  --date 2026-06-21 --time 17:00:02 --zone +08:00 \
  --use-true-solar-time false --taiyi-options '{"calculation_mode":"hour"}' \
  --fields synthesis.palace_correspondences synthesis.time_scopes \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
```

这里的现代日期仅为软件调用示例，与无公元年的原例分开。新增字段不会把`joint_judgment=not_implemented`改成已完成；候选神将没有被当成胜负概率、古历通过或预测有效性。完整历法、四维／中宫寄支、门具将发联合断法及真实模型解释验收继续保留，见验证记录（本地数据：`validation/taiyi-jinjing-v41/README.md`）。

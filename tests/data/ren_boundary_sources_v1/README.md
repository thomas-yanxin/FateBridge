# 独立六壬历法边界参考

`reference.json.gz`保存1800—2200年全部19248个秒级探针、1899—2101年9744个原分钟探针，以及生成源码、独立规则助手源码、原始表格文本和身份。配合[独立DE440节气TT资料](../solar_tt_de440_v1/README.md)使用；不依赖本地旧资料目录、已归档过程报告或旧侧件。参考读取不会执行包内源码。

当前生成器：[build_ren_boundary_reference.py](../../../scripts/ren/build_ren_boundary_reference.py)；类型化读取：[ren_boundary_reference.py](../../../scripts/ren/ren_boundary_reference.py)。输入从已确认原始资料逐字节准备，生成时拒绝覆盖现有文件。独立环境使用Python3.12、pyswisseph2.10.3.2和pydantic2.14.1；从仓库根目录运行：

```bash
uv run --no-project --python /absolute/path/reference-venv/bin/python \
  python -m scripts.ren.build_ren_boundary_reference \
  --input-directory /absolute/path/verified-original-inputs \
  --output /absolute/path/new-reference.json.gz
```

输入名称及原始字节身份由生成器的`INPUT_SHA256`声明；原DE440完整节气参考另按其现行身份校验。历史Swiss钟需要协议既定的`sepl_18.se1`和`semo_18.se1`；这些外部星历不随本资料分发。重新生成只使用参考TT根、独立规则表和参考钟，没有导入FateBridge生产领域计算。

每个原TT根先独立转民用钟，固定取整秒和下一秒，原1秒TT／200微秒输入钟门限未变。完整区间包含1952年立秋整秒输入；它的`inside_root_bracket`保留为真，所有判定仍比较。与旧数据重叠的标签和全部规则期望一致；1872年夏至的两个探针参考TT差约80.467微秒，原数据未被覆盖。不能把近边界数值一致解释为已确定物理时刻落在边界哪一侧。

原分钟标签及原共享钟输入逐字节保留，9744个条件状态重新按独立TT根分类并逐项核对；这不是独立历史UTC验证。1960年前参考钟与候选共享Swiss公布的UT1／ΔT模型，1960—1971年按独立SOFA／IERS线性段，现代及未来按明确的末次偏移延续假设。参考钟保留全部233项原SOFA控制点。

来源：[IERS历史UTC](https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history)、[SOFA2023-10-11](https://www.iausofa.org/2023-10-11c)、[Swiss时间接口](https://www.astro.com/swisseph/swephprg.htm)、[香港天文台干支与历法](https://www.hko.gov.hk/tc/gts/time/stemsandbranches.htm)、原`六壬指南`／金口诀转录表所保留的网址与引文。该表的指定取法不代表已解决所有原典分歧。

旧guard冻结清单、旧Ren边界协议与原分钟协议的既定身份差异保留在`legacy_identity_observations`，旧文件和缺失来源承诺未重写、未宣布恢复。当前auto臂采用DE440；原auto／analytic臂原文继续作为输入来源保存，当前臂不代替原门限结果。天文／民用钟、原典、接口交付、解释与现实预测分别验收；本资料不授予全算法或SOTA认证。

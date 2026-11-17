# VSOP2013 太阳模型的固定独立参考

这三份已有资料是当前来源资格测试的必需输入。此前被统一数据规则忽略，本轮按原字节纳入版本管理；没有重新生成参考、选择通过子集或改变门槛。

- `reference-14904.json.gz`：1684—2304年每年24个交点，共14904项。
- `reference-lichun-116.json`：2305—2420年所需的116个立春交点，不代表这些年份的全部节气已取得资格。
- `manifest.json`：原文件身份、年份集合、1秒TT门槛及0.0002秒数值根区间门槛。

参考使用独立Skyfield／原NASA DE440和已声明日期框架，生成过程未导入FateBridge。这些输入已经用于开发，不能称为盲测或新的物理观测。资料校验运行：

```bash
uv run --locked --extra dev python -m pytest -q tests/astronomy/test_vsop2013_projection_qualification.py
```

此命令检查固定资料和来源资格约束，不会在缺少可选原生库时冒称执行了15020次实际求根。实际求根还需要按[太阳后端](../../../../docs/solar-backends.md#vsop2013)构建并显式选择匹配的本地模型。完整队列和原生模型身份必须一起记录；数值一致、工具可用、来源复现、绝对民用钟与现实预测分别验收。

独立参考使用[NASA原DE440](https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440.bsp)。VSOP2013本身的地月质心级数及控制表来自[IMCCE原发布](https://ftp.imcce.fr/pub/ephem/planets/vsop2013/solution/README.pdf)，控制表TDB、动力学J2000和ICRS几何不能混作地心视太阳或TT交节参考。

# 地磁参考计算合同

[风水总览](fengshui.md) · [规范与来源](../skills/onda-fengshui/references/geomagnetic-reference.md) · [独立测试](../tests/test_fengshui_geomagnetic.py)

`fengshui_directions` 增加可选 `geomagnetic_reference`；其余六个入口及原始宅向合同不变。该分支用于核对真北／磁北换算依据。详细科学范围、误差含义与使用条件统一维护在上方规范引用中。

```json
{
  "bearing_degrees": 0,
  "north_reference": "true",
  "geomagnetic_reference": {
    "model_id": "wmm2025_v1",
    "latitude": 80,
    "longitude": 0,
    "height_km_wgs84": 0,
    "decimal_year": 2025.0,
    "evidence": "NOAA官方数值测试例；非真实房屋或实测方向"
  }
}
```

该输入对应东正磁偏角约1.281482°，原始真北0°保留；磁北换算候选约358.718518°。也可只提供地磁参考，不提供方位角。使用 `model_date` 时删除 `decimal_year`，两项不能同时非空。字段以实际Schema为准。

- REST：`POST /api/fengshui/directions`。
- MCP：`fengshui_directions`，请求相同。
- CLI：`uv run --locked --extra dev fatebridge fengshui_directions --request-file docs/examples/fengshui-geomagnetic.json`。
- 来源与条件投影：`fields=["layers.directions.bearing","layers.directions.geomagnetic_reference","rulesets","rule_trace"]`、`strict_fields=true`。

结果含七个主场量与输入、系数散列、独立规则来源、统计误差说明、方位适用状态和换算候选。未启用时保持旧输出。完整请求如返回 `result_delivery`，沿用同一运行读取完整结果；不为读取全文重新计算。可读摘要仍在既有“公共方位”节，保留候选未确认及未应用宅盘的含义。

当前规则 `geomagnetic_wmm2025_v1@1.0.1` 增加实际实现身份核对与回执，数值算法及系数不变。核对失败返回 `dependency_missing`、不可重试，REST状态503；不把运行环境问题归为用户输入错误。实际安装版本、源码散列和支持安装方式见上方规范；独立回归见[运行身份测试](../tests/test_fengshui_runtime_identity.py)。

## 外部数值核验

固定来源及SHA-256见原始数据目录（本地数据：`../tests/fixtures/fengshui_geomagnetic_v1/provenance.json`）。原始系数、12组简表和100组高精度表均不修改。运行：

```bash
uv run --locked --extra dev python scripts/audit_fengshui_geomagnetic.py > /tmp/fengshui-geomagnetic-audit.json
```

当前脚本预期退出1：12组简表84项吻合，100组高精度表700项中346项按发布精度吻合，354项差异保留；整体门槛因此为false。表内角度均吻合，小于0.001nT的差异集中在高精度场强项。

另从[NOAA当前官方Linux C发布包](https://www.ngdc.noaa.gov/geomag/WMM/data/WMM2025/wmm2025_Linux.zip)原样编译 `GeomagnetismLibrary.c`，不经海拔到椭球高转换，以同100组输入复算。官方C也复现原表差异；本实现与其700项全部在 `1e-7nT / 1e-9°` 的实现数值容差内。此门槛独立命名为 `official_c_implementation_agreement`，不能覆盖原表失败。没有使用场强差异去调整磁偏角或官方期望值。

复算器要求系统C编译器；原始C代码不纳入运行时依赖。取得并解压官方包后，运行：

```bash
uv run --locked --extra dev python scripts/build_fengshui_geomagnetic_c_reference.py --source-dir /absolute/path/wmm2025_Linux --output /tmp/noaa-c-reproduced.json
```

该脚本核对官方源文件和包装器散列，在临时目录编译，使用完整100组原输入，输出全部七个主场量。冻结的官方C复算记录（本地数据：`../tests/fixtures/fengshui_geomagnetic_v1/NOAA_C_100_main_field_values.json`）来自实际Linux x86_64；包装器不修改官方源文件。它不导出网格偏角和年度变化率。

数值实现的一致性、现场角度准确度、古典规则忠实度和风水现实预测有效性是不同验收项。后者仍未检验。

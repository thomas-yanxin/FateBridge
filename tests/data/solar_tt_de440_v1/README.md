# 独立 DE440 节气 TT 参考

`reference.json.gz` 保存 [Skyfield 1.53 官方 `solar_terms`](https://rhodesmill.org/skyfield/almanac.html#solar-terms)与[原始 JPL DE440](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/aa_checksums.txt)的完整固定参考。覆盖1699—2301年，每年24项，共14472项；1700—2300年对应当前打包太阳模型的公开输入范围，1699／2301只作相邻边界上下文。各行保留单JD的TT点及最终参考夹区间。

参考包同时保存生成源码全文及其身份、软件版本与模块身份、JPL内核网址和发布校验值、固定取样及求根方法。后续读取校验保存在包内的生成源码，不要求维护脚本永远停在生成时的字节。该包不导入FateBridge，不使用生产交点、钟时转换或结果选取输入括区间。参考包只供测试和审计，生产计算继续读取原始轨道系数。

生成入口：[build_solar_term_reference.py](../../../scripts/astronomy/build_solar_term_reference.py)；当前读取入口：[solar_term_reference.py](../../../scripts/astronomy/solar_term_reference.py)；完整回归：[test_solar_term_reference.py](../../astronomy/test_solar_term_reference.py)。

复现需要Python 3.12的独立环境及已准备的完整DE440内核。固定软件版本是Skyfield 1.53、jplephem 2.24、numpy 2.5.4、sgp4 2.27、certifi 2026.10.18；使用uv建立独立环境并安装这些明确版本，再运行：

```bash
uv run --no-project --python /absolute/path/reference-venv/bin/python python -I \
  scripts/astronomy/build_solar_term_reference.py \
  --kernel /absolute/path/de440.bsp --output /absolute/path/new-reference.json.gz
```

生成器核对完整内核的JPL公布MD5与既定SHA256，并拒绝覆盖现有输出。其TT月初1—12日及12—28日括区间、两端节气序号和40次矢量二分均在生成前固定。原始内核不随测试资料分发，可按[星历准备](../../../docs/ephemeris.md)取得。

该资料复用既有DE440事件；与旧Bazi／Ren参考重叠的行不增加独立天文观测数。原单JD参考保留约40.233微秒的浮点夹区间，不能据更多小数位宣称物理微秒准确度。TT实现对照、历史民用钟、原典和现实预测分别验收；旧侧件或旧来源身份缺失不会被写成已经恢复。

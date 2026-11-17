# 共享干支、五行与具名贵人配置参考

本包保存固定外部程序的实际输出，供便携回归使用；不依赖维护者机器上的研究环境。

- [6tail/lunar-python](https://github.com/6tail/lunar-python/tree/1645ad3b3653635e5cb31b0c6df22b5e4298f8ce)，1.4.9：未修改的`LunarUtil.py`实际计算全部60个甲子、旬首和旬空，读取10干、12支五行及100个十神配对。十神按明确的五类关系投影；100个干配对只有25种五行状态。
- [wlhyl/ganzhiwuxin](https://github.com/wlhyl/ganzhiwuxin/tree/0d46e789345882b571403204d38c60ac35647866)，v1.0.0：实际执行原干支、五行、六合、六冲和环序方法，覆盖60甲子、25五行配对、144支配对及24个顺逆起点。
- [wlhyl/daliuren](https://github.com/wlhyl/daliuren/tree/c16f2ff0802fa0b21f5d6c1670412798c8933666)：原`tianpan.go`、`tianjiang.go`与单独导出适配器编译运行，不是整应用构建。10日干×12月将×12时支×2显式昼夜共2880组，仅对应`探原/协纪`贵人表。天将缩写的12项别名在metadata中明列，不改变布置。与既有本项目符号输入重叠1440组，另有1440组显式昼夜输入；不是新的公历日期或天文观测。
- ICU 78.3以`zh_Hans_CN`的`%spellout-numbering`实际交付1至72的中文数字，只检验太乙局号的格式支持，不计作独立命理算法。
- 25项季节五态复用原`liuren_seasonal_v1`影印表，原manifest SHA-256为`bf5ba9b6fc53a6200a1b8948e605913823282df5f0be4091516064556ba7b010`；40个具名贵人起点复用原4320条独立布盘参考。复核不增加独立样本数，也不裁定季末十八日、星出星没或整书效力。

`reference.json.sha256`固定解压后JSON字节。预期值只由外部程序及原影印参考生成，没有读取FateBridge答案。`liuren_common_v1`与`探原/协纪`的20个日夜条件中有10处起点不同，不能把前者送到只实现后者的程序后改表取绿。

固定输入、完整原始输出、发布者Git blob核对、编译驱动、初始工具错误及前后实际调用记录保留在`/Users/thomas/.codex/artifacts/fatebridge-celestial-frame-20261114/metaphysics-primitives-and-sources-v1/`。Go与ICU只用于外部研究，未加入产品依赖。本包不认证独立物理精度、全部原典、现实预测或全算法SOTA。

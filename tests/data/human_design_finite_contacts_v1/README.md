# 有限太阳邻点的独立枚举参考

参考先于候选实现冻结，不导入FateBridge，也不使用产品的邻点、求根或残差函数。三个正TT量级、两个黄经原点和全部七点三值组合共13122个函数；逐个枚举48114个可用初始正到负相邻括区／精确零点，再用整数binary64编码展开固定四ULP窗口。

窗口内全部正到负相邻括区和精确零点按绝对精确有理残差、较早TT排序，记录实际端点及所选TT。反向交叉不能作为正向太阳弧根。窗口外的函数为每TT日一度的线性太阳，七点的残差为该黄经原点的−1／0／1 ULP。两个原点另覆盖出生太阳的自然360度环绕。完整描述符和每个初始窗口均保留，没有选择性筛掉模式。

`manifest.json`绑定解压后的原JSONL与压缩文件。`build_reference.py`只增加输出目录参数，枚举内容与阶段原生成器相同；重建命令为：

```bash
uv run --locked --extra dev python tests/data/human_design_finite_contacts_v1/build_reference.py --output-dir /tmp/fatebridge-finite-contact-reference
```

按清单核对原JSONL字节，再以gzip的mtime=0打包。本参考检验已观测有限集合中的数值选根；它不是第三方物理星历、连续域最优性、物理时刻或传统规则的认证。原244组严格Swiss选根门槛另行保留，不能被本参考替代。

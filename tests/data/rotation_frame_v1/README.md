# 同一天球矩阵的恒星时控制

`reference.json.gz` 保存预先固定的257个均匀日期、两种共同输入NPB矩阵，
共514项90位原点差／ERA控制；另含原作者C实现的257个共享默认钟时矩阵，
以及J2000、采用时窗、1960和民用边界附近的18个矩阵控制。
边界邻点用于坐标算术，不扩大公开历法或物理星历的输入范围。

原始框架来自固定Swiss源版本
`696bda432298d482d27e67a0cf1238920301a7dd`的完整C实现，未导入FateBridge。
同一物理太阳向量在完整146101日期上，经其NPB变换可重现原生赤道输出；
这验证源框架的组成，不是独立物理星历、观测或连续域认证。
完整IAU2006/2000A矩阵由ERFA2.0.1取得，两个模型分别保存。

独立高精度生成器解析ERFA原始`s06.c`的66项和六个多项式系数，读取原始
基本角C源码，以90位精度计算同一IEEE矩阵／TT／UT1操作数的原点差和ERA。
同输入ERFA结果另列。原0.001角秒线不变，并逐项比较相对独立高精度公式的误差。
没有候选输出参与参考生成，没有拟合、逐点修正或残差选点。

维护入口扩展原有生成器：

```sh
python scripts/western/gen_western_rotation_kernel_reference.py \
  --coherent-reference /absolute/path/coherent-frame-reference.npz \
  --clock-reference /absolute/path/matched-clock-reference.json \
  --sources /absolute/path/original-ERFA2.0.1-C-sources \
  --output /absolute/path/new-reference.json.gz
```

输入NPZ含全部146101个预定TT／UT1、原作者原生NPB及完整IAU矩阵，
伴随JSON锁定原始库和NPZ散列；钟时JSON来自独立原作者C过程。
包内保留生成器源码、散列、输入身份及矩阵操作数；完整原作者C编译、
源文件下载回执、逐日输入及结果保存在本次阶段证据中。
固定生成环境为Python3.12、pyerfa2.0.1.5、numpy2.5.4及mpmath1.3.0。

旧显式恒星时公式配合原生Vondrak矩阵，在146101个日期上有4885项
超过原毫角秒线；在相同浮点度数格式下，514项新标量控制全部不劣于同输入ERFA。
另保留ERFA原生弧度精度比较：510／514项不劣，另外4项即使取最接近真值的
浮点度数也无法匹配对应弧度输出的误差。这4项不改判为无条件逐点胜出。
原生框架与完整IAU模型仍有超线差异，未由组合一致性通过改判为SOTA或物理通过。

来源：[IERS第5章](https://iers-conventions.obspm.fr/content/chapter5/icc5.pdf)、
[ERFA gst06](https://github.com/liberfa/erfa/blob/v2.0.1/src/gst06.c)、
[原生框架源码](https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swephlib.c)。

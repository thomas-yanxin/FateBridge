# IERS 自转公式的独立高精度控制

`reference.json.gz` 保存实际采用的TT正负两世纪时窗内257个预先固定均匀点，
每点分别使用IAU与Swiss的章动／平均黄赤交角，共514项。它们来自独立生成器的
完整146101个逐日、确定二进制日内相位控制，不按候选残差挑点。

参考读取IERS2010 Table5.2e原文及ERFA2.0.1基本角C源码，以90位精度计算原表
十进制表达式；另用ERFA计算相同TT／UT1及角度输入，包含边界上的单位换算。
生成时不导入FateBridge，不读取候选输出。完整生成源码及其散列保存在包内，
维护入口仍为原有的[自转参考生成器](../../../scripts/western/gen_western_rotation_kernel_reference.py)。
默认模式继续复算原12项参考；新`--dense`模式生成完整逐日数据与此高精度小包。

```sh
python scripts/western/gen_western_rotation_kernel_reference.py \
  --dense --sources /absolute/path/original-IERS-and-ERFA-sources \
  --output /absolute/path/new-reference-directory
```

独立Python3.12环境使用pyerfa2.0.1.5、numpy2.5.4、mpmath1.3.0及pyswisseph2.10.3.2。
原文件目录须含`tab5.2e.txt`和`fal03.c`、`falp03.c`、`faf03.c`、`fad03.c`、`faom03.c`、
`fave03.c`、`fae03.c`、`fapa03.c`。IERS原文SHA256为
`a5c690b277108e35d88df9cc20fea4120dfbc10a81444bb41b15cf9c6edcd6cb`。

门槛保留原0.001角秒，另比较候选与同输入ERFA相对独立90位表达式的逐点误差。
原实现有243／514项不优于ERFA的记录保留；精确转数约简与最终有理数归一后514项
均不劣于ERFA，最大约1.023e-10角秒。没有逐点补偿或参考答案运行时依赖。

这些是公式算术控制。当前混合Swiss章动／平均黄赤交角对完整IAU2000A_R06模型的
146101点比较，仍有7116点超过同一毫角秒诊断线，最大约0.002590角秒；该差异保持未通过，
不由本包通过来改判。原表还省略低于截断线的项；完整参考系、钟时、连续域与物理观测分别验收。

来源：[IERS原表](https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.2e.txt)、
[ERFA2.0.1源码](https://github.com/liberfa/erfa/tree/v2.0.1/src)。

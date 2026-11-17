# DE441月球完整局部日速

固定参考包含4565行、4560个不同binary64时刻：前轮4340个位置输入、
原Horizons链97个时刻，以及事先由SHA256分层选择的128个公元1至9999年时刻。
它们是符号历元输入，不增加天文观测。重复时刻保留各自队列身份。

独立CALCEPH5.0.1读取完整原DE441文件，Skyfield1.55计算接收者、光行时和
视位置。分别保留`apparent(deflectors=())`与默认三偏折天体约定；前者对应
当前产品已经声明的月球省略太阳偏折约定，后者是另列的模型控制。
每个时刻固定13个TT探针，以15分钟和30分钟的七点模板交叉核对收敛。
不使用Skyfield未包含光行差／偏折变化的`Apparent.velocity`作为完整视导数。

日期显示框架由原Swiss源码提交`696bda432298d482d27e67a0cf1238920301a7dd`
中的完整Vondrak岁差、独立标量交角和77项Simon章动C实现取得；固定J2000
偏置来自ERFA2.0.1。框架模型的来源相同，执行代码独立于FateBridge。
两种日速都与实际产品的相同TT向量和黄经日速比较，未复制产品计算作为答案。

原有方向导数及显示日速门槛均为0.002角秒／TT日，参考不稳定者不能通过。
原始源TDB速度另核对预定`1e-12 AU/TDB日`及既有更严格的`1e-13`诊断线。
距离变化的1米／TT日是本轮另列的有限工程诊断，不冒充既有物理精度线。
参考环境使用Skyfield的TT／TDB钟，产品使用完整ERFA Fairhead地心钟；
模型、时标约定及原严格数值失败没有合并改判。

`reference.json.sha256`核对解压后JSON；包内数据只来自固定独立输出。
原始DE441文件内容针为既有独立记录，未声称NASA发布了该SHA256。
完整编译来源、输入冻结、13点探针、两次差分和每行结果保存在阶段证据中。
原Horizons97项中的7项差分不稳定记录仍保持；不以新参考代替原审计。
没有修改生产公式，也不宣称全时域、全部光学约定、真实观测或SOTA已完成。

来源：[JPL DE441原文件](https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/linux_m13000p17000.441)、
[DE440／441论文](https://doi.org/10.3847/1538-3881/abd414)、
[Skyfield视位置接口](https://rhodesmill.org/skyfield/api-position.html)、
[原Swiss框架](https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swephlib.c)。

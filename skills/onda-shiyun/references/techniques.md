# 时运技法按需参考

仅在用户点名技法、要求全生命周期或明确专家深度时读取；主流程与输入纪律见 [SKILL.md](../SKILL.md)。工具是否已连接、参数和返回以实际 Schema 为准，不能因本表存在就默认调用。

## 单技法

| 工具 | 技法与问题范围 |
| --- | --- |
| `solarreturn` | 太阳返照年运盘 |
| `lunarreturn` | 月返盘 |
| `transit` | 行星过境行运 |
| `solararc` | 太阳弧方向 |
| `givenyear` | 指定年盘 |
| `profection` | 年小限 |
| `pd` / `pdchart` | 主限及图 |
| `zr` | 黄道释放 |
| `firdaria` | 法达星限 |
| `decennials` | 十年星限 |

整体推运先用聚合，不重复已经返回的层。单技法只补用户需要且现有结果没有的依据；哪一层缺数据就说明哪一层。

## 全生命周期

| 工具 | 技法说明 |
| --- | --- |
| `astro_planetary_ages` | 行星年龄、七分期；可传分析日期标出当前段 |
| `astro_triplicity_rulers` | 三分主星、人生三阶段 |
| `astro_lunation_phase` | 月相推运 |
| `astro_distributions` | 界推运、分配法 |
| `astro_harmonic` | 调波盘 |
| `astro_balbillus` | Balbillus 129 年系统、主限 |
| `astro_keypoints` | 数字相位推运、120 年关键点 |
| `astro_yearsystem129` | 129 年系统、七星小年轮值 |
| `astro_planetaryarc` | 行星弧方向 |
| `astro_persiandirected` | 波斯向运、符号 1°／年 |
| `astro_agepoint` | 年龄推进点、Huber／Koch 宫 6 年 |
| `astro_vedicprog` | 恒星黄道二次推运 |
| `astro_jaynesprog` | 二次推运赤纬平行 |

这些结果是各传统的分期或共振结构，不能变成人生事件年表；某年具体问题仍选择对应时运层。完整时间线首次保留全量，再按同一 run 分页交付。

## 非个人盘

`astro_mundane` 用于年度节气入宫等世俗盘，`astro_extrareturns` 用于多重回归或事件多盘。两者不默认加入个人年运，也不据星盘推断政治、金融或灾害的确定结果。

返回[时运技能](../SKILL.md)，时间边界与取证粒度见[共享时间选择](../../_shared/timing-selection.md)。

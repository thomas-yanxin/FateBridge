# 河洛理数与邵子参评数：计算口径与使用

`heluo` 提供河洛本命卦与时运，`canping` 提供参评取数及具名配运方法。两者的取数、年代、原典与时间映射分别核对，不把河洛本命卦、皇极经世、铁板数和金锁银匙统称为一个已认证体系。

[文档中心](README.md) · [调用合同](contracts/README.md) · [可选太阳后端](solar-backends.md)

原典只覆盖指定底本的已读段落。逐爻解说、诗诀、疑字、引用卦爻与正式后天盘分别返回；未核内容保留待核，不按已核比例推定全书符合。参评时间线保持120条年序；具现代立春映射的方法保留121个边界，其他方法不补造未知的 UTC 映射。

民用钟时须结合地区时区与必要的明确偏移；重复钟时的两种瞬间不能互换。DE440／VSOP2013 的有限 TT 网格按原1秒线报告，原版 Swiss Moshier 的12个超差及历史失败继续保留；当前完整 Moshier 修订另按具名模型验收，见[太阳模型](solar-backends.md)。历法、原典、解释与现实预测各自验收，不因来源修复改判其他层。


## 调用

```bash
uv sync --locked --extra dev

uv run --locked --extra dev fatebridge heluo \
  --date 2026-06-21 --time 16:30:00 --zone Asia/Shanghai \
  --gender 女 --use-true-solar-time false --response-char-limit 0

uv run --locked --extra dev fatebridge canping \
  --date 1990-06-15 --time 09:33:00 --zone Asia/Shanghai \
  --gender 男 --method gu --use-true-solar-time false \
  --fields benming numerology_evidence --strict-fields true \
  --include-snapshot-text false --response-char-limit 0

uv run --locked --extra dev fatebridge heluo \
  --date 1990-06-15 --time 09:33:00 --zone Asia/Shanghai \
  --gender 男 --use-true-solar-time false --analysis-year 2028 \
  --month-index 3 --day-index 10 \
  --fields heluo_timing.selected_annual heluo_timing.selected_month \
    heluo_timing.selected_day heluo_timing.selected_texts heluo_timing.calendar_policy \
  --strict-fields true --response-char-limit 0

uv run --locked --extra dev fatebridge canping \
  --date 2026-02-06 --time 04:02:00 --zone Asia/Shanghai \
  --gender 女 --use-true-solar-time false \
  --dayun-method bazi_appendix_v1 \
  --analysis-datetime 2037-02-06T04:02:00+08:00 \
  --fields canping_timing numerology_evidence.selected_texts \
  --strict-fields true --include-snapshot-text false --response-char-limit 0

uv run --locked --extra dev fatebridge heluo \
  --date 2026-02-10 --time 12:00:00 --zone Asia/Shanghai \
  --gender 女 --use-true-solar-time false \
  --fields chart.tian chart.di judge.seasonal_numbers \
  --strict-fields true --include-snapshot-text false --response-char-limit 0
```

示例为虚构测试输入。`--use-true-solar-time false` 是显式选择；使用默认真太阳时应提供实际经度。REST 路径仍为 `/api/divination/heluo`、`/api/divination/canping`，MCP 工具名仍为 `heluo`、`canping`；请求与输出模型由同一工具目录发布。

两工具均须明确 `gender`，不能默认男命。河洛已知中英文性别别名归一化；缺失、未知或拼写错误直接报错，因为性别影响命卦和元堂。

两工具的 `time` 也必须是已知的当地钟时，空白、未知与夹带时区的字符串会拒绝；时区单独放 `zone`，显式 `00:00` 有效。`judge.deTime` 仅为卦属月匹配，另述窗口、来源及未决边界见 `judge.month_affinity`；其中月号暂按四柱月支解释，不等于农历月或精确节气区间。

真太阳时默认开启，须提供明确经度`lon`或数值`gps_lon`，0°有效；缺经度不再用上海缺省值。只在用户选择钟表时时明确传`use_true_solar_time=false`，不为绕过错误自动改换钟制。两工具的`birth_clock`视图可核对实际输入来源与所用钟面。

解释时先使用 `rule_trace` 和实际选中条文。`selected_texts` 仍可能同时包含葉者、不葉者、岁运等分支；现阶段没有完整综合判断，不能挑最有利的一段充当确定结论。

上面的 `month-index 3 / day-index 10` 是原典序号，不是3月10日。缺父级选择、超过卦序范围或无效序号会报错，不回退当前年或最后一步大运。完整年序位于 `heluo_timing.annual_rows`，月序位于 `monthly_rows`，日定式位于 `daily_template`；大结果按同次交付机制读取。

## 来源及版本限制

- [《河洛理數》卷一，识典古籍转录](https://www.shidianguji.com/book/NA09030/chapter/1m8od60nhc1me)：取数、五寄宫、元堂、后天卦、化工。正文有明显 OCR 错字和混排，例如第一例总数转录与分项运算不一致；参考夹具保留手算方法说明，未声称影印逐字校勘完成。
- [卷六转录](https://www.shidianguji.com/zh/book/NA09030/chapter/1m8od6rwizt4b)：金锁银匙五行算例，以及大运替时、流年用太岁与大运支的规则。金部明确给出同支十三位，可独立定位移植错误。
- [日本国立公文书馆卷四至七影印](https://www.digital.archives.go.jp/DAS/contents/pdf/lossy/03050271000050/0001.pdf)：核读PDF第50、105、106页，保存三张原页及散列。卷七把附入的子平运法与河洛六九年卦运明确区分；卷六的配运段落未唯一指定采用哪套时间轴。[馆藏目录](https://www.digital.archives.go.jp/file/3611497)记载明刊／清印，具体印年未定。
- [国家图书馆藏本影印 PDF 的公开镜像](https://upload.wikimedia.org/wikipedia/commons/4/4a/NLC416-13jh000625-42999_%E6%B2%B3%E6%B4%9B%E7%90%86%E6%95%B8.pdf)：提供后续底本校勘入口；整本图像核读尚未完成。
- [日本国立天文台 2026 年暦要項](https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html)：24 节气时刻，原表为日本标准时 UTC+9，测试按绝对时刻比较。
- [中央研究院中国文哲研究所维护的《参评秘诀金锁银匙歌》馆藏记录](https://hannom.openmuseum.tw/muse/digi_object/c814fd85d043d6e38fbb7ca4723db287)：该抄本记录编者不详。它是另一文献记录，不能据此确认本系统条文全部出自邵雍。

`numerology_evidence.selected_texts` 按实际条目分别标注爻辞、注文、诗歌的原页、核读状态及疑字。未校与独立复核未完成的部分继续保留未知，不按局部比例推定全本符合。内容摘要只标识所用资料，不能证明内容正确。

土用目前明确采用“四立前十八个连续日、左闭右开”的计算约定。卷一季月十八日的计日法、不同底本及纯卦阴阳令与其他月令术语的差异需继续核对，不能把工程边界测试当作版本争议已经解决。

## 规则与时间口径

1. **交节时刻**：按出生民用时刻代表的绝对瞬间判断节气和至点。真太阳时可调整四柱日时，不用调整后的墙钟重新判断太阳交节。参评年序仅求各年所需立春，复用共享求根、时标和来源校验；公开全年节气表仍返回24节气，不以预存日期或近似值代替计算。
2. **三元五寄宫**：由弘治十七年甲子（1504）上元起，六十年一元、180 年循环；2044 年回到上元。公历一月仍属于上一个干支年时，用该干支年确定寄宫。
3. **天地数归卦**：超过正数时只减一次 25／30，再按原文去十取零。例如天数 55 减 25 得 30，取 3。该扩展用例是规则推演，区别于书中四组现成算例。
4. **参评数同支**：卷六金部的申日申时例绕行一周，连首尾计十三位，结果 3322。顺逆均包含首尾；非同支按各自方向计数。
5. **默认方法**：`canping.method=gu` 使用日支，符合卷六该段不用月令的规则；显式 `ming` 为月支反向变法，输出保留其与该段原典的差别。未知方法拒绝。
6. **后天卦与纳甲**：先后天的实际六爻纳甲均参与匹配，并纳入乾坤借用。五卦原页已核对，其余按规则推演；不代替完整得势判断。
7. **参评时间线**：完整方法选择和边界见下节。120 行是年序覆盖范围，不是寿命预测。
8. **解释边界**：`judge.xie` 只表示元气或化工命中，不裁定综合葉否；天地数有余／不足只与 25／30 比较，相等称正数。`judge.seasonal_numbers` 列出至弱太过、十一数式和六个时令窗口；原文重叠不裁优先，得中数值条件为 `null`。缺条、空条和缺字标注语料状态。


## 当前结构与适用范围

`judge.deTi` 分列年柱纳音与先后天实际上下体、互体的有向五行关系，完整得体的 `present=null`。无元气且卦体生纳音的条件，与另一原页记载的反向关系分别返回；不以日干查卦替代这一关系层。

`judge.line_conditions` 按先后天实际元堂列出二五位、五同一异众宗式与爻位偏好。`yuanTang.position_polarity_match` 只比较爻位与阴阳，原典阴月当位另在 `source_dangwei` 保留定义待核、`match=null`，两者不能混用。

岁运按阳爻九年、阴爻六年的小象游变；每一大限按实际交运首年的干支阴阳判断。奇数月递进，偶数月从对应奇数月取应爻；三十日定式的五个六日块分别从原月卦变出。日序尚未与实际节月长度、寄刻接合，输出序号不冒充公历或农历日期。`changed_pos` 是变爻，`pos` 是选文爻位。

参评默认 `bazi_appendix_v1`、连续折算 `bazi_continuous_v1` 与命宫顺排 `legacy_minggong_v1` 均保留。卷六未唯一指定配运法；日计数、生日加整年与立春年界是具名计算约定。`analysis_datetime` 须含明确时区；实际交运时刻拆分流年段，未起运不套第一运。`reading_context` 保留所选方法、钟制、底本、页码与引用角色。

源资料包括当前 `tests/data/heluo`、`tests/data/canping`、`tests/data/solar` 的字面读数、独立太阳参考，以及原始影印页、PDF与来源记录。退役源码、整盘快照及旧执行日志不作为当前计算的预期答案；来源冲突、无法判定的文字与独立参考超线继续保留。

## 核验

```bash
uv run --locked --extra dev pytest -q \
  tests/numerology/test_heluo_body_depth.py tests/numerology/test_heluo_line_conditions_depth.py \
  tests/numerology/test_canping_timing_depth.py tests/numerology/test_numerology_clock_depth.py

uv run --locked --extra dev python -m scripts.numerology.audit_numerology \
  --output /tmp/numerology-current-audit.json
```

审计按具名有限规则与来源检查给出结果，失败保留非零退出码。`--require-three-dimensions` 与 `--require-four-dimensions` 对应的完整门槛仍未完成；工程测试通过不替代整本校勘、独立复核、解释评估或预测效度。

## 参评取数和条文的完整职责核对

本轮完整审读 `core/numerology/canping.py` 与 `core/numerology/canping_texts.py` 原32个定义。移除没有生产调用者的 `_tiaowen` 缓存转发和 `_lookup` 字符串转发后，现30个定义（含3个嵌套函数）细分为141项计算、资料、来源及支持职责；这些不是141种独立算法。测试直接使用条文模块已有所有者，未新增计算层，取数、配运规则与条文数据均未改动。

对12日支、12时支及五部的全部720组形式输入，另外编写不导入本项目的逐支环行程序，按已读卷六规则分别复算顺逆数；当前结果全部相符。实际执行[Horosa原模块](https://github.com/Horace-Maxwell/horosa-skill)同一批输入，仍有60组同支差异：其顺数停在一位，本项目按卷六金部示例绕行十三位。原差异全部保留，不为追求软件一致而改写原典规则。另有288组日宫选择、144组命宫、60个纳音年柱和1296组名义运序与该模块一致。移植来源相同限制了比较的独立性；720组是规则推演，既有印刷算例仍只有5个，不是720个原书实测或现实预测样本。`ming` 月支变法、命宫运序与卷六日支取数分别保留来源资格。

上述取数可达540个不同的五行／编号组合。逐一读取男、女、共用岁运栏共1620格，再加540个未选性别控制，合计2160次查找。所选格中1079格为目校可读，23格原页局部圈空、21格原页圈空、47格仍有疑读，另450格在本地语料中缺行。主选编号表的1170格与全部可达所选格不是同一个分母；本地缺行不证明原书没有该条。通过第三方1440次实际 `calculate` 调用取得对应文字后，315条字面差异全部保留，包含底本、编号更正与转录差别，未把差异统判为任一方错误，也未用继承文字覆盖目校或疑读。

固定12个公开场景显式组合 `gu/ming`、三种配运方法及男女，重复钟时明确指定偏移。原安装包、修改后源码和新安装包各经REST、独立CLI与新建stdio MCP调用36次，共108次；完整业务结果只排除 `run_metadata`，各环境内部及跨环境72组逐端比较一致。该结果验证这批输入的调用和交付，不证明全部历法分支、原典解释、物理精度或已部署连接。

相同9个相关测试文件修改前后均为226项通过，节点集合保持。13格字面原文、来源身份、疑读和故障注入等检查仍在；仅去掉一条重复验证已退役字符串转发的断言。历史记录中的首行回执选择器在当前文件选择到0项，退出码5；这是旧节点已不匹配，不能据此宣告历史两项哈希差异已经修复。原始失败、输入、现行来源边界与独立日期精度继续分别核对。

## 参评配运时轴与太阳投影的职责核对

`canping_timing.py` 和 `canping_solar.py` 的15个定义已完整审读，细分103项计算、区间、来源许可及支持职责；15个均由实际公开调用路径触发。附录方法按出生时区的民用日期计日、余一舍余二借，连续方法委派共享八字时间轴。周年采用已声明的重复钟时取第一次、缺失钟时向后平移政策；零整岁的首运保留已确认出生的实际次序。立春年序按UTC瞬间裁到出生并在每个交运边界切段，未起运、覆盖缺口和超范围查询分别处理。

上述 15 个定义是原审计快照。现行附法与连续法共用大运周年边界解析。附法先核对参考节令的当地日期是否存在，再按原日期规则折算。两法生成的首运和后续十年边界均在解析实际钟面后检查地区时区资料，未定义钟面返回结构化错误。 [参考节令对照](precision-acceptance.md#exact-replay-start-and-canping-date-round66) · [周年钟面对照](precision-acceptance.md#canping-generated-anniversary-clock-round66)

独立运行Temporal 0.5.1，对597个时区的237720组边界标签保留全部结果。363组差异来自参考运行时IANA 2026a与项目固定2026f的数据差别；另取完整2026a数据回放这363组，均与原Temporal结果相符。[IANA更新记录](https://data.iana.org/time-zones/tzdb-2026f/NEWS)包括古巴、加拿大、摩洛哥及历史日期更正。原363组差异未回写为通过，未降级项目数据以求一致。19791组明确的民用日折算与另写的Temporal参考相符；这是具名日期约定的检查，不证明全书唯一的日内折算法。

两个投影审计脚本与一个测试仍要求已退役的独立压缩包存在，基线因而出现216通过、1失败。现改为核对实际所选来源与冻结DE440原始内核身份，保留冻结参考文件、全部120／121个TT交点、1440／1452条状态查询以及原1秒、0.0001公里、0.00001公里每日门槛。两交点队列重叠20个，两状态队列重叠240条，不能相加冒作全新样本。修订后同8个测试文件217项通过；旧压缩包约束已退役，原失败另存，不声称旧文件恢复或旧存储布局验收通过。

在仓库外构建AA1996、VSOP2013并取得校验过的原始DE440及Swiss资料后，八种来源模式在源码和安装包中均运行了两种日期配运方法，共32次完整REST调用。新执行的两个Skyfield立春交点与32次模型／环境计算在原1秒TT线内，最大差约0.183秒；另核对NAOJ公布的两个分钟级时刻。这些重复运行只有两个新参考事件，Skyfield与部分模型共享DE440轨道来源。另有8个固定场景的48次三端调用完整结果一致。

八模式完整REST对照中，SPK的两种方法共266处来源字段报告了不同的NumPy实际版本，数值字段无差异。使用完整官方NumPy 2.2.6另起源码进程后，两份完整结果与安装包一致。原来的两项完整相等门槛仍保留失败，不删除或伪造实际依赖版本；同版控制也不增加独立精度样本。

此前实际配置AA1996时，2200年出生的两种方法都在2205年起触发 `solar_aa1996_range`，无法完成原定120年序。1.2.0沿用既有派生立春机制，在来源所属边界增加2205—2320年逐年315度、2月1—12日 TT 括区资格；原120年序、121个边界、公开1800—2200年、完整节气1784—2204年及普通工作 TT 区间均保持原范围，轨道和归算源码未变。全部116个所需立春与原独立 Skyfield/DE440 参考均在原1秒线内，最大约0.876秒。

**完整太阳算法精度仍未通过。** [完整原队列](../tests/data/solar/aa1996-projection/README.md)保留2200至2320年全部24交点及1799立春，共2905项，包括19项超过原1秒线、最大约1.274秒。逐分量及仅替换地月质心轨道的诊断表明，主要差距来自AA1996轨道近似；该替换只用于归因，没有以AA1996名义发布，也没有写入参考事件时刻。派生立春的原有用途与完整24节气的未通过结果分别记录，不能据此宣称全部算法达到SOTA。

现实预测需在结果揭晓前登记政策、样本、可判定事件、时间窗、基线与主要指标，保存已发预测及独立观测，并报告漏报、弃权、缺失和负结果。当前没有据此完成的河洛／参评现实预测认证。

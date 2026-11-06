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

1. **交节时刻**：按出生民用时刻代表的绝对瞬间判断节气和至点。真太阳时可调整四柱日时，不用调整后的墙钟重新判断太阳交节。
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

现实预测需在结果揭晓前登记政策、样本、可判定事件、时间窗、基线与主要指标，保存已发预测及独立观测，并报告漏报、弃权、缺失和负结果。当前没有据此完成的河洛／参评现实预测认证。

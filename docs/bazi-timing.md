# 八字时运：时钟、关系与限定投影

大运、流年、流月、流日、流时和节气时间线使用已确认出生瞬间与实际分析时刻。日期查询以起止瞬间选运，区间含起点、不含终点；尚未起运返回 `before_dayun` 与空当前柱。显式年龄查询标明 `explicit_age_reference`，不能当作某个日期的同义输入。

## 交运口径

`three_days_one_year_calendar_v1` 以[《三命通会·论大运》](https://zh.wikisource.org/zh-hant/三命通會/卷二#論大運)的三日折一年、十年一运为依据。年干阴阳与已确认性别决定顺逆；顺行取严格晚于出生的下一节，逆行取不晚于出生的上一节。十二节与中气不能混用。

出生至参考节使用名义UTC标签间隔，`elapsed_scale=nominal_utc_label_seconds`、`leap_second_policy=not_counted`；它不宣称跨闰秒的均匀SI历时。每秒折120个名义秒，以360日一年、30日一月分解，再按公历年月日一次加到出生民用日期。这是秒级软件延拓，原典没有认证秒级应期。

每步十年边界从首运锚点分别计算，避免闰日逐次截断。派生重复钟时取有效的 `fold=0`，缺失钟时向前过缺口；首运不得早于已确认出生瞬间，必要时取符合这一条件的较晚一次，否则明确失败。原始出生的重复或缺失钟时仍须调用者消歧，不猜选。

`start_age_unrounded` 是未舍入折算，`start_age_precise` 是两位展示，整数起运岁数按原始量向上取整且至少1。它们不反算交运日；实际选运使用 `start_at/end_at`。365.2425日折年的显示年数不参与选运。

## 关系与作用范围

`interaction_analysis` 区分原局四柱及各时间层，保留重复干支的实际位置。天干合克、地支冲合刑害、三合三会、半合及同柱重见各有规则、参与位置、作用域和状态。关系几何与实际合化、通关、救应和吉凶不等同；流时关系不能扩展解释全年。

`timing_roots` 记录时间柱干与支中藏干对原局根位的触点。`root_effects` 与 `stem_roots` 保留实际归属；未知力道不转换为零或确定值。单层剩余原局根预算投影只对该层已声明关系计算，不把多层结果相加；`blocked` 代表存在尚不能量化的关系前提。

唯一时间干与原局非日干的合绊投影使用既有原局预算，保留根与原字身份。投影不重写本命评价，也不宣称已裁定古典有效根力、从格或化格。

## 范围与检验

未知时刻与出生时间范围按候选传播，不猜生时。范围中的连续完备性、未解析事件与未来当地时钟均需读取对应状态，有限采样不能证明全部极值。

当前独立数据包括香港天文台发表到分钟的节气表、JPL太阳时资料、DE440的TT根及IANA钟时参考。它们分别检验历法、时标或地区钟时，不能互相替代。原版 Swiss Moshier 的96个独立TT对照仍有12项超出1秒门槛。当前 `native` 的完整 Moshier 修订按独立模型身份验收，已过有限内部队列，仍不能推广为全时域通过；默认随包 DE440 也单独报告，见[太阳模型](solar-backends.md)。数值求根的相邻浮点跨越控制不消除物理模型误差。

```bash
uv run --locked --extra dev python -m scripts.astronomy.audit_solar_model_reference --output /tmp/solar-model-audit.json
uv run --locked --extra dev pytest -n0 tests/bazi/test_bazi_dayun_initial_fold.py tests/bazi/test_bazi_timing_roots.py tests/bazi/test_bazi_timing_cache_isolation.py
```

首个审计会对未过的1秒门槛返回非零退出状态。当前来源分歧与独立专家、实际预测缺口见[八字旺衰](bazi-assessment.md)；准确的时间换算不证明现实事件预测有效。

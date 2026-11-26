# Feng Shui Engine Reference

FateBridge's `fengshui` family computes deterministic, source-bounded structural facts across 8 tools (`directions`, `minggua`, `bazhai`, `jinsuo`, `annual_stars`, `monthly_stars`, `xuankong_house_chart`, `assess`) with zero prescriptions, cures, or fortune verdicts.

## Modules (`src/fatebridge/core/fengshui/`)

1. `models.py` — Consolidated Pydantic v2 request models & projection-compatible per-tool output schemas (`<6 KB`), decoupling `AssessRequest` from `AnnualRequest` mutual exclusion (`effective_year` + `query_at` supported together).
2. `directions.py` — Posterior-Heaven 8 directions, LuoShu numbers, 24 mountains, 3-Yuan polarity, `sitting_from_facing`, exact `Fraction` interval support, and 24-mountain sub-band / void-line classification (`zhengxiang`, `jianxiang_lower`, `jianxiang_replacement`; `da_kongwang`, `yinyang_chacuo`, `xiao_kongwang`).
3. `geomagnetic.py` (+ `core/geomagnetic_field.py`) — Pure IEEE-754 `float64` spherical harmonics for **WMM2025 (`2025.0–2030.0`, degree 12)** and **IGRF-14 (`1900.0–2030.0`, degree 13)** (~0.1 ms/call).
4. `calendar.py` — Lichun year boundary, 12-`节` solar month windows, DE440 historical crossings, and ZiBai 6-segment solstice/jieqi anchors (`冬至/雨水/谷雨/夏至/处暑/霜降`).
5. `bazhai.py` — 1864-anchor MingGua (`male` `1 - Δ`, `female` `5 + Δ`, `5 -> 坤2/艮8`), 8×8 `大游年` XOR table, `游年星宫生克`, and **阳宅三要** (`door` / `master_room` / `stove` trigram relations & East/West 4-house coherence).
6. `jinsuo.py` — `金锁玉关` 8-palace (`1234` sand / `6789` water) and 24-mountain sand/water polarity mapping.
7. `zibai.py` — Unified **Annual** (+ `annual_afflictions`: `太岁`/`岁破`/`三煞`/`五黄`/`二黑`), **Monthly** (`12 节`), **Daily** (`《紫白诀》` 3-Yuan JiaZi), and **Hourly** (`子午卯酉`/`辰戌丑未`/`寅申巳亥` × `冬至`/`夏至`) ZiBai flying stars + 4-layer `palace_overlay`.
8. `xuankong.py` — Zhongzhou XuanKong natal charts (`下卦`/`替卦`, 13 replacement mountains, 5-yellow borrowing period's same-yuan polarity without replacement), `连珠三般卦`, `父母三般卦`, `七星打劫` (`离`/`坎` trines), `令星入囚` (natal + evaluation period), evaluation-period `到山到向`/`上山下水`/`双星` distribution, pure-geometric `正/副城门` (`primary`/`secondary`), fixed `零正`, timeliness (`王亭之`), and host/guest (`沈氏`).
9. `assess.py` — Multi-layer layout assessment and 4-layer palace overlay without remedies or CAD geometry.

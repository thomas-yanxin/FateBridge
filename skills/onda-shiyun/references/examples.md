## 样例

以下使用虚构资料。在已安装并激活的仓库虚拟环境中运行，环境准备见[引擎调用](../../_shared/fatebridge-engine.md#怎么调引擎)。已有 MCP 时直接调用，无需执行本地命令。
```bash
# 综合首轮：保留实际分析时间、时区及节气换月边界
python3 -m fatebridge.cli --no-metadata timing_analysis \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 \
  --analysis-year 2026 --analysis-month 10 --analysis-day 14 \
  --strict-fields --no-include-snapshot-text \
  --fields dayun_analysis liunian_analysis liuyue_analysis comprehensive_summary personal_info.analysis_datetime personal_info.time_adjustment analysis_calendar.analysis_date_context.timezone analysis_calendar.analysis_date_context.current_solar_term analysis_calendar.analysis_date_context.next_solar_term analysis_calendar.analysis_date_context.bazi_month_boundary

python3 -m fatebridge.cli --no-metadata liunian_analysis \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 --target-year 2026

python3 -m fatebridge.cli --no-metadata profection \
  --name 我 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-minute 30 \
  --birth-latitude 39.90 --birth-longitude 116.40 --birth-place 北京 --analysis-year 2026

# 生命周期：行星年龄，保留实际段界与主星条件
python3 -m fatebridge.cli --no-metadata astro_planetary_ages \
  --strict-fields --no-include-snapshot-text --fields analysis_context planetary_ages natal_reference \
  --name 我 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-minute 30 \
  --birth-latitude 39.90 --birth-longitude 116.40 --birth-place 北京 --analysis-year 2026

# 月相推运：本命月相 + 八相时间轴（默认看到 90 岁）
python3 -m fatebridge.cli --no-metadata astro_lunation_phase \
  --name 我 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-minute 30 \
  --birth-latitude 39.90 --birth-longitude 116.40 --birth-place 北京

# 紫微运限：第三套时运体系，看目标时间点的六层运限+动态四化
python3 -m fatebridge.cli --no-metadata ziwei_horoscope \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 \
  --target-year 2026 --target-month 6 --target-day 19 --target-hour 14 --fields summary
```

## 可复核示例

CLI 示例使用已安装并激活的仓库虚拟环境，准备方法见[引擎调用](../shared/fatebridge-engine.md#怎么调引擎)。

以下为虚构问题与指定时间，不是“现在”。已有 MCP 时直接调用。

```bash
python3 -m fatebridge.cli meihua_analysis --question "是否先做小规模项目试点" \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15 --analysis-minute 20 \
  --analysis-timezone Asia/Shanghai --strict-fields --no-include-snapshot-text \
  --fields analysis_context meihua.base_hexagram.name meihua.seed.moving_line meihua.changed_hexagram.name meihua.body_use_relation interpretation.action_hint interpretation.risk_hint

python3 -m fatebridge.cli qimen \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15 \
  --strict-fields --no-include-snapshot-text --fields analysis_context qimen.ju_text qimen.dun_type qimen.zhifu qimen.zhishi qimen.palaces

python3 -m fatebridge.cli tongshefa --fields summary

python3 -m fatebridge.cli sixyao --question "这个项目试点有什么需要留意" \
  --date 2026-06-18 --time 15:00:00 --seed 20260618 \
  --strict-fields --no-include-snapshot-text --fields input_normalized nongli current_hexagram changed_hexagram moving_lines lines hexagram_info

python3 -m fatebridge.cli astro_horary --category career \
  --question-year 2026 --question-month 6 --question-day 18 --question-hour 15 \
  --longitude 116.40 --latitude 39.90 --timezone-name Asia/Shanghai --fields summary
```

生辰参评、河洛本命卦等已有能力按[数术方法参考](../README.md)核对，不用出生条文替代本次问事卦。

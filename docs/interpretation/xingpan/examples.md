## 可复核示例

CLI 示例使用已安装并激活的仓库虚拟环境，准备方法见[引擎调用](../shared/fatebridge-engine.md#怎么调引擎)。

以下为虚构资料；已有 MCP 时直接调用，不先运行 CLI。

```bash
python3 -m fatebridge.cli astro_chart \
  --name Mia --birth-year 1995 --birth-month 6 --birth-day 1 --birth-hour 8 --birth-minute 20 \
  --birth-latitude 31.23 --birth-longitude 121.47 --birth-place 上海 --birth-timezone Asia/Shanghai \
  --strict-fields --no-include-snapshot-text --fields chart_profile angles planets aspects

python3 -m fatebridge.cli astro_relative_chart \
  --inner-name 我 --inner-birth-year 1995 --inner-birth-month 6 --inner-birth-day 1 --inner-birth-hour 8 \
  --inner-birth-latitude 31.23 --inner-birth-longitude 121.47 --inner-birth-place 上海 \
  --outer-name TA --outer-birth-year 1993 --outer-birth-month 11 --outer-birth-day 3 --outer-birth-hour 7 \
  --outer-birth-latitude 39.90 --outer-birth-longitude 116.40 --outer-birth-place 北京 \
  --strict-fields --no-include-snapshot-text --fields relationship_profile synastry_aspects in_to_out_aspects out_to_in_aspects compatibility
```

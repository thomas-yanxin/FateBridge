## 样例

以下使用虚构资料。在已安装并激活的仓库虚拟环境中运行，环境准备见[引擎调用](../shared/fatebridge-engine.md#怎么调引擎)。已有 MCP 时直接调用，无需执行本地命令。
```bash
python3 -m fatebridge.cli --no-metadata bazi_romance \
  --gender 女 --birth-year 1995 --birth-month 4 --birth-day 12 --birth-hour 20 --birth-place 成都

python3 -m fatebridge.cli --no-metadata two_person_compatibility \
  --person1-name 我 --person1-gender 女 --person1-birth-year 1995 --person1-birth-month 4 --person1-birth-day 12 --person1-birth-hour 20 \
  --person2-name TA --person2-gender 男 --person2-birth-year 1993 --person2-birth-month 11 --person2-birth-day 3 --person2-birth-hour 7 \
  --relationship-type general --strict-fields --no-include-snapshot-text \
  --fields summary strengths challenges traditional_compatibility detailed_analysis recommendations person_info element_relationship
```

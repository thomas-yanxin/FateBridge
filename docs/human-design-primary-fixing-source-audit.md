# 固定极性的署名资料复核

[人类图说明](human-design.md) · 本轮记录（本地数据：`validation/human-design-primary-source-followup-verification.json`） · 固定书面参考（本地数据：`../tests/fixtures/human-design-primary-fixing-2024.json`）

本轮补充了可追溯的书面核对和原始音频线索，没有改动计算规则。原38项专业要求、原失败案例、完整解释门槛和2角秒位置容差继续保留；新增有限样本不替代原有验收。

## 可用于有限核对的书面依据

IHDS官方博客刊载的[《How to use the Rave I’Ching》](https://ihumandesignschool.com/how-to-use-the-rave-iching/)正文署名Lynda Bunnell，由Ruth Brennan于2024年6月12日发布。文中11.4的示例给出月亮上升极性、太阳下降极性，并说明同门、谐振端和两极同时固定。它是署名教学说明，不能称为Ra原稿、完整384线校定本或出版勘误。

新增审计核对两项书面星体事实和14个明示的开发案例：其中两项将文中直接示例实例化，十项使用明确披露的简化激活组合演示通用规则，另两项保护2001正文附加的金星依据。这些组合不是官方完整命盘、盲测或真实出生样本；初步探查先于本轮参考冻结，记录中明确保留这一点。

文中举出月亮不等于排除金星。审计检查正面事实是否包含在原典星体集合中，不用一篇简短教学文章覆盖原2001正文。14项组合及预期值在新增审计实现前固定并绑定散列；删除案例或改预期值会被拒绝。若计算不符，失败行与其他行一起返回，不能缩小集合取得通过。

原有[Jovian 2026说明](https://jovianarchive.com/blogs/chart-interpretations-components/line-fixing-in-human-design-exaltation-detriment-and-juxtaposition)的作者简介说明文章由AI Ra撰写并由分析师编修。该文保留其实际来源身份；本轮增加2024署名材料作有限交叉核对，不把官方域名或AI辅助文章当作Ra原典认证。运行时来源字段和旧回执没有改写。

```bash
uv run --locked --extra dev python scripts/check_human_design_primary_fixing.py
uv run --locked --extra dev python scripts/check_human_design_primary_fixing.py --require-full-acceptance
```

第二条命令即使14项全部吻合，也返回退出码1，因为完整384线和全部固定状态仍未认证。总专业审计另附这份诊断；原38项要求的定义和判断不变，新增诊断失败也会使命令退出为失败。

## 音频属于研究线索

从[IHDS免费资料库](https://www.ihdschool.com/resources/free-library)的正常公开播放器取得《Introduction to Line Fixing》《Exaltations》《Detriments》三段讲座，分别记录原音频字节数、散列和工作转写时间位置。没有保存下载链接的临时签名，也没有将音频或完整转写复制到仓库。

本地FasterWhisper工作转写把同门／谐振规则定位到第一段约225至263秒，把上升／下降不等于好坏的说明定位到第二段约43至95秒。这些线索与署名书面说明相容，但没有经过人工音频核听或作者认证，不能充当新增验收真值。第三段约58至87秒叙述60门水星下降极性；将其进一步标为60.1依赖其他文本对应，不能冒称音频直接报出的线号或新增官方命盘。

音频研究回执（本地数据：`validation/human-design-primary-source-followup/audio-research-receipt.json`）保留软件版本、模型版本、模型文件散列、时间位置和证据限制。初始缺少依赖、旧音频API参数不兼容、旧版本缺少本机安装包的三次失败日志均保留。最终在项目依赖之外的临时隔离环境完成转写，没有改变`uv.lock`或生产音频处理。

## 计算精度与原典分歧仍保留

[Swiss Ephemeris文档](https://www.astro.com/swisseph/swisseph.htm)把Moshier描述为DE404的近似。找到的[JPL DE403文件](https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de403.bsp)前131072字节显示所有15段止于2199年6月22日，无法覆盖原2230年最大超差点；DE403本身也不是DE404。只读取文件前缀检查范围，没有完成DE404与现代模型的误差分解，没有更换DE440参考、放宽2角秒门槛或删除228个Moshier超差点。前缀与解析记录（本地数据：`validation/human-design-primary-source-followup/de403-prefix-inspection.json`）可单独复核。

IHDS新取得的周期课程预览与已有文件散列完全相同，新增独立周期示例为0。人格／设计周期起点、逆行多次交会优先级、29.1／29.2印刷边界冲突，以及原15项和扩展86项名称失败仍然存在。免费入门书第4页补充了人格／设计与88度计算的出版方链接依据，但不解决这些争议。出版物复核记录（本地数据：`validation/human-design-primary-source-followup/publication-followup.json`）分别保存其来源和散列。

本轮没有新做模型咨询或现实预测。固定模板重放、有限书面例子、任意模型解释和现实效度仍分别判断；完整解释验收与现实预测都不能由上述研究记录代替。

# 宿曜原典影像清单核验

`scripts/inspect_sukuyo_iiif.py`只读取本地冻结清单，绑定原字节SHA及声明版本，保留完整解析对象。它分别处理嵌入式IIIF Presentation 2和3：第2版读取全部sequences/canvases，第3版读取items。版本未知、混合版本、缺结构或只给外链注释页会显式报错，不把未读取当0页。它不是完整JSON-LD或IIIF合规验证器，不联网，不代替实际取图和逐字校勘。

```bash
uv run --locked --extra dev python scripts/inspect_sukuyo_iiif.py \
  --manifest tests/fixtures/sukuyo-iiif-manifests-v1/Kyoto-RB00012918-manifest-first.json \
  --sha256 03c8ded962bca19929fa688db129bf8105cf7e7e930a8c1b278b8e990bfd0353 \
  --source-version '京都大学2026-10-28实际响应' \
  --output /tmp/sukuyo-iiif-new-inspection.json
```

输出路径必须尚不存在。版本声明是调用方文字，不由指纹认证。位置同时保存序列、顺序、canvas ID、标签和annotation的on/target；不以任意一个编号静默替换另一个。精确字符串不同比较不是语义无效结论，SpecificResource等非字符串目标保持原值并列未比较。完整原对象可继续核对超出本工具支持范围的字段。

本入口仅支持嵌入式Image body。Choice、缺失或未知类型、非图片body均显式拒绝，不把未处理内容计为非图片并返回零；混合清单含一处不支持body时也不发布部分总数。复杂选择或混合媒体需要另行研究，本工具不认证其完整语义。

三份修改前冻结的实际清单分别有40、4、36个canvas。100178256的40条on与所在canvas ID存在逐项差异，应结合实际资源URI和图像字节定位。京都RB00012918的第3版清单有36帧，不能按第2版的空默认记成0；图像body URI含2000像素宽度请求，但body同时列6480×4320。工具只报告这些声明和URI，实际像素尺寸保持null、状态为not_fetched；需另外完整解码实际下载字节。清单不证明已经取得36张原尺寸图。

canvas出现次数、唯一ID、图像注释数、实际取得／解码／阅读数、实物叶数和独立见证数分别登记。题签卷次、正文内题、卷末、题记和目录说明也分别核验，不能只按现代大正卷号排除古本，更不能把同名书或石山寺关联直接认证为CBETA【石】的同一具体底本。

规范依据：[IIIF Presentation3](https://iiif.io/api/presentation/3.0/)、[Image3](https://iiif.io/api/image/3.0/)。本工具增加来源定位能力，不修改历法或配宿、不增加公开MCP／REST接口，也不认证古代日界、半日、闰小月先后、全本校勘或现实效力。

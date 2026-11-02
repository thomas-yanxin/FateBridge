# 未定半日的个人日与事项证据

半日或闰小月重建次序未定时，历日主宿继续为null。`sukuyo.candidate_mansion_days`按已经列出的候选宿分别交付个人三九日、上下卷见证、宿性、逐宿／七曜／方向条文及所问事项证据；每支的`applied_to_primary`为false。候选宿不回填主结果或顶层事项，也不当作现实吉凶。

例如Hinoo档案下2024-08-04为七月初一，前半候选星、后半候选张。本命室分别顺数得到安与危。两支保留各自的三九日条文和出行条件；未知半日不再导致这些可计算的条件证据一起缺失。已知09:00不自动证明前半。明确提供前半或后半时，继续交付单一主宿与原有事项证据。

`conditions`绑定实际半日槽；闰月交叠时另外保留每个现代重建的ID及查表计算。两种现代重建不升级为原典明定算法，不能把一支内容当成共同结论。没有槽位依据时明确保留未绑定；`candidate_set_complete_under_declared_reconstructions=false`不改成穷尽古法。具体日界、半日钟时和两条规则先后仍未由这些字段确定。

`candidate_days`仍表示跨参考日期的分支。每个日期子项拥有自己的`candidate_mansion_days`；一层日期已展开，不代表另一层宿候选已确定。所问事项与已确认细节在所有支中沿用相同选择器，缺少方向、远近、行旅身份或启程事实时继续保留条件文。支内的匹配状态只描述这一条件下的文献，不代表顶层汇总或现实行动许可。

公开`activity`、`profiles`、`personal_day_witnesses`、`clothing`等字段卡包含新增字段。读取时同时保留同run的calendar、personal_day、activity_assessment和reading_text；完整结果可沿用原有结果交付方式。`suzhan`可省略time或给null，未知钟时的日期候选由公开接口直接保留；chart和astronomy为null，星图及天文宿位未计算。本地REST／MCP／CLI与当前聊天已连接的MCP进程分别验收。

规则依据为[T1299三九日](https://cbetaonline.dila.edu.tw/zh-tw/T1299)的上卷0391b19–25、下卷0397c25–0398a17，以及[T2465闰月与小月分宿段](https://21dzk.l.u-tokyo.ac.jp/SAT/ddb-sat2.php?mode=detail&s=&useid=2465_%2C01)0030c13–26。新增层复用领域查表与事项选择器，不采用模型重写计算、择有利见证、投票或概率换算。它补交条件解释，不裁定尚缺原页的古籍异文，也不证明现实预测有效。

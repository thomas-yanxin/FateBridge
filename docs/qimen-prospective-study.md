# 奇门前瞻研究的计算证据绑定

`scripts/audit_qimen_study.py` 将每条预测绑定到实际问时、明确的排局口径、完整奇门结果和冻结解释策略，然后逐案重算再交给通用二元结果评估器。它检查研究记录的一致性，不是已经验证的预测模型，也不提供权威认证。

目前没有可核验的真实奇门预测队列。随附第九轮2.6.0规则演示报告（本地数据：`validation/qimen-study-synthetic-v9/report.json`）使用明确标为 `synthetic` 的三个人工案例、全部弃权和空结果列表，可评估数为0，现实效度为 `not_tested`。演示中的目标、日期、主体、记录哈希和时间戳都不是外部登记或经验材料。2.5.0规则演示仍保留在 `qimen-study-synthetic/`；后续规则也只做本地合成重放，不增加真实样本。不同冻结版本须用各自环境重放，不能改写旧记录冒充新版本预测。

## 已补齐的检查

- `StudyInput` 须包含完整 `plan/policy/castings`。当前v3沿用v2的完整输入绑定，并纳入逐例基线的概率、发布时刻、相同目标／窗口及来源记录。计算错误和弃权留在队列；仅同步删除所有列表里的弃权案例或改基线，不能沿用原证据哈希通过评估。
- 每条起局须明确带时区的物理时刻、时区名、经度、记录时刻和问事原始档案的引用及哈希。当前计算接口只有分钟精度，拒绝静默截去秒数；不猜地点和时区。记录只接受注册后、目标窗口前的实际问时，不用于未来候选择时盘。
- 策略冻结置闰／拆补、八神章节、旺衰章节、真太阳时开关及原典分歧处理方式。模型指纹绑定整个包的源码及数据、项目锁文件、Python与平台、依赖版本、关键历法依赖实际文件、Swiss原生模块和配置搜索路径中的星历文件清单。实际盘面还包含所用时区规则指纹。无关包文件变化也会使研究环境失配，需要在独立固定环境重放。
- 发布预测只读取问事记录与盘面，不读取结果标签。规则概率是研究者事前明确冻结的假设值，`null` 是弃权；程序不把格局数、吉凶、旺衰或传统规则分换算为概率。这个接口不提供经过验证的概率映射。
- 解释策略采用有序的首条匹配规则，`all_of` 为合取。规则条件有真、假、未知三态；已知假能排除一条规则，可能匹配却含未知的较早规则会弃权，不能跳到后面的有利规则。日甲身份未明时，伏干／飞干特征为未知，不会把未输出格局当作不存在；其他已知门星神仍可独立使用。
- 格局名命中与附加条件已观察到是两种不同特征。计算保留整条格局证据、同宫冲突及源文限定；附加条件字段未评估时返回未知。`pattern_conditions_observed=true` 只表示至少一个匹配结构的已记录条件满足，不是全盘吉或现实成功。
- 真实数据封存使用当前本地时钟，不接受手填历史发布时间。计算期间源码或星历改变、时钟倒退，或实际封存时目标窗口已经开始，均拒绝。合成演示才允许注入时刻。
- 评估先重算每个实际奇门盘及策略决策，再检查预测、证据哈希与已封存结果。重放检查预测是否由该策略算得；全包指纹另核对是否仍是事前封存的那份计划及预测。真实研究必须提供从独立登记或可信存档取得的事前全包指纹，拒绝缺失或不匹配。仅靠重放不能发现整个计划、基线、队列和收据被一致重做；合成演示可以省略外部指纹，但报告明确标为未锚定的合成包。

第二十一轮采用 `qimen_forecast_commitment_v3`，对应常数／逐例基线二选一的新研究输入。旧v1及v2必须在原固定环境重放，保留当时协议的范围；禁止自动补新字段、重算旧收据后把它当成原来的封存。`study_input_sha256` 在封存时绑定完整输入，不证明计划在问事发生前已经外部登记。

盘级 `qimen.source_disagreements` 可预先固定为 `source_disagreement_action=abstain` 或 `use_declared_rules`。前者保留该例并弃权，后者保留该例分歧并按已声明规则计算；不能看过结果再切换。这个开关不等于所有原典范围、释读和优先未决项都已完成自动裁决或自动弃权。整条引用或冻结条件的检查不认证任意自由文本解释。

## 可复现的合成演示

源码环境先执行 `uv sync --locked --extra dev`。以下目录须是尚未生成过这些文件的新目录；命令拒绝覆盖已有封存记录。

```bash
uv run --locked --extra dev python scripts/demo_qimen_study.py \
  --output-dir /tmp/fatebridge-qimen-synthetic-demo

uv run --locked --extra dev python scripts/audit_qimen_study.py fingerprint \
  --policy /tmp/fatebridge-qimen-synthetic-demo/policy.json \
  --output /tmp/fatebridge-qimen-synthetic-demo/fingerprint.json

uv run --locked --extra dev python scripts/audit_qimen_study.py seal \
  --study /tmp/fatebridge-qimen-synthetic-demo/study.json \
  --synthetic-at 2026-12-31T00:00:00+00:00 \
  --output /tmp/fatebridge-qimen-synthetic-demo/resealed.json \
  > /tmp/fatebridge-qimen-synthetic-demo/reseal-receipt.json

uv run --locked --extra dev python scripts/audit_qimen_study.py evaluate \
  --commitment /tmp/fatebridge-qimen-synthetic-demo/resealed.json \
  --outcomes /tmp/fatebridge-qimen-synthetic-demo/outcomes.json \
  --as-of 2027-03-01T00:00:00+00:00 \
  --expected-commitment-sha256 "$(uv run --locked --extra dev python -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["commitment_sha256"])' \
    /tmp/fatebridge-qimen-synthetic-demo/reseal-receipt.json)" \
  --output /tmp/fatebridge-qimen-synthetic-demo/replayed-report.json
```

预期：注册案例数3、可评估数0、覆盖率0、`real_world_efficacy=not_tested`、`authority_certified=false`。其中一例保留《演义》已知分歧，一例保留日甲未决身份，一例检查纽约重复钟时的明确偏移。当前实现保留 `casting_at` 对应的实际UTC时刻及IANA时区，全部弃权仍无可评估结果。旧版本把第三例报为计算错误的封存原件仍保留，不能改写旧收据。合成时间可设在未来，不代表已经收集到未来资料。

`seal` 的标准输出提供 `commitment_sha256/study_input_sha256`；演示脚本也保存 `seal-receipt.json`。上面只演示读取封存时另存的本地收据，未进行真实外部登记。该指纹计算自经模型验证后的规范化JSON，不是对磁盘JSON文件直接执行 `sha256sum` 的结果；缩进和对象键顺序不影响指纹。

第十五轮修复明确实际时刻转换成当地字段后丢失偏移的问题。公开奇门接口可同时给 `analysis_timezone=America/New_York` 和 `analysis_utc_offset=-04:00`（或该重复小时的 `-05:00`）；偏移须与该命名时区在指定钟时的规则一致，不会把全年时区换成固定偏移。研究接口从已知 `casting_at` 自动提取偏移，历史整秒偏移也保留；裸重复钟时和不存在的钟时继续拒绝。输出 `qimen.calendar_policy.civil_clock_resolution` 保留原偏移、核对后的偏移、fold和实际UTC时刻，正文同步显示。

实际时刻的先后统一换成UTC比较，原记录不改写。包含同一个ZoneInfo对象的重复小时也要遵守注册、起局、记录、发布及结果窗口顺序；窗口未结束或结果记录晚于评估时刻时不能计入。新增回拨对抗案例是软件回归，不是现实预测样本。

## 实际研究输入

输入结构可参照合成 study.json（本地数据：`validation/qimen-study-synthetic-v9/study.json`），不能沿用其中虚构资料当作实测资料。完整机器字段由 `StudyInput`、`FrozenQimenPolicy`、`Condition` 和通用 `StudyPlan/Outcome` 定义。

| 部分 | 必须事先明确的内容 |
| --- | --- |
| `plan` | `data_kind=real_world_submission`、目标定义、注册时刻、共同结果窗口、完整队列、基线及冻结时刻、训练主体（无也须显式 `[]`）、样本与停止规则、计划检验次数、模型与解释策略指纹、真实外部登记引用 |
| `policy` | 排局／章节口径、冲突处理、唯一规则ID、有序条件、每条规则的冻结概率或弃权、显式兜底概率或弃权 |
| `castings` | 队列中每例的 `case_id/subject_id/casting_at/timezone_name/longitude/recorded_at/question_record_sha256/question_record_reference` |
| `outcomes` | 每例独立判定的是否发生；发生时刻（阳性必需）、完整窗口结束后的记录时刻、原始结果档案哈希和引用 |

`plan.model_sha256` 使用 `fingerprint` 输出的模型指纹，`plan.interpretation_policy_sha256` 使用该命令输出的策略指纹。指纹生成只是本地草稿，不替代事前外部登记。登记后不得改写目标、队列、基线、概率映射、样本量或停止规则；变更须作为新研究或明确的探索分析。真实研究封存命令去掉 `--synthetic-at`，真实评估也拒绝未来的 `--as-of`。

真实研究封存后、目标窗口开始前，应将完整封存包及其规范化指纹提交可信独立登记或存档，并在评估时从该记录取得 `--expected-commitment-sha256`。不得在看过结果后从当前待评文件新算一个指纹，再把它称为事前外部锚。程序核对调用者提供的指纹是否吻合，不能自行认证它何时、由谁保存，故 `expected_digest_provenance_authenticated/external_registration_authenticated` 仍为false；指纹吻合不等于预注册、盲法或独立结果核验已经完成。

条件目录限定为全盘星／门伏吟反吟、五不遇、所选卷二六组时干支入墓，指定外八宫的门／主星／神、主星旺衰、门迫、时旬空亡范围，以及已经实现的格局存在／已记录附加条件。`hour_branch_tomb` 是字面时柱条件，不检查天盘时干的墓宫。不能给任意JSON路径，不能读取结果或主体ID，也不能给中宫补门星神。岁格、月朔格可使用 `year_stem_block/lunar_month_start_block`；年界、甲身份或历法锚点未解决时返回未知，不能把缺项当阴性。`stem_pair` 表示已实现干对类别中的任意命中，不是某个格名或总体吉凶。

目前研究接口仅支持共同窗口下的二元事件、每例一个独立主体，重复主体会拒绝；重复观察、聚类、连续结果、不同结果窗口、人工自由解释盲评及打乱问时对照需要另行预注册和实现。独立的现实信息基线与对照不能由本程序凭空补出。

三奇入墓的正式匹配固定为卷二王璋列举。段首文字的另一种字面读法只在证据中作为未采纳候选，不会进入 `pattern_present` 的正式匹配，也没有生产取法参数。不能在看到结果后采用候选以挽救失败预测；未来采用不同映射的研究须明确冻结新的模型与解释政策，不改写既有封存记录。

2.9.0规则的六仪击刑暂定保留广义六仪落刑宫匹配，另列本时直符窄读候选，范围尚未裁定。`pattern_present` 及该格的 `pattern_conditions_observed` 据暂定广义几何条件，不等于窄读已匹配或原典范围已经认证；仪自身的六甲身份与本时旬首分别保留。窄读候选没有生产切换参数，不能在看到结果后换取法。使用这个特征的研究应事先披露并冻结采用的广义范围，不能把盘级分歧弃权开关当成该范围已经验收。

2.10.0规则为门迫补上方向明确的条件证据。`door_pressure` 及该格的条件观察仍按歌诀门克宫，不把正文的“吉迫”当作吉利事件、把“和／义”当作结果标签，也不把歌诀门迫为否当成宫克门不存在。增加的正文关系名只是同一盘面关系的来源说明；既有冻结策略不会自动取得经过验证的预测概率。缺失附加条件的旧式证据仍判未知，不能从格名补出条件成立。

2.11.0增加 `true_deception/heavy_deception/rest_deception` 三个正式完整组合特征，可用于 `pattern_present/pattern_conditions_observed`。它们读取现行盘面天盘奇（含寄奇）、开休生门和对应太阴／九地／六合三层同宫；部分三要素缺项不能命名完整组合，正式未匹配不等于该方传统解释必凶。歌诀得二亦吉与正文有阴无奇不利的优先未裁定，不能从缺项反向补出概率。原文的十分／七分只保留为文献语境，没有经过验证的概率映射。

丁休太阴命中人遁又命中真诈时，两者共享盘面事实，`overlapping_evidence_group/overlapping_rule_ids` 保留这一关系，不能当两份独立印证叠加权重。具名完整组合可与门迫等同时出现，`condition_observed` 只表示命名所需三层俱全，不能用它证明全盘限制已经满足。新增特征须事前写入冻结策略，并使用对应的包指纹和固定环境；旧封存不得按新名称回填预测。

2.12.0补入 `heaven_jia/earth_jia/spirit_jia/ghost_jia` 四条五假完整组合，按天盘主寄干、实际门、所选八神匹配：景门乙丙丁九天；杜／伤／死门丁己癸九地。`human_jia` 是已知而尚不能裁定的原文格名，`pattern_present/pattern_conditions_observed` 对它始终返回未知；不将“未正式命名”转换成false，不以己候选或改字六壬挽救结果。两条杜门临六合／太阴旁例没有正式地假名称。规则的已记录完整条件仍不表示全盘吉或真实成功，新增格名不带经过验证的概率。

## 证据边界

预注册、区分探索与验证、预留未参与开发的数据以及报告所有预定结果，依据[开放科学中心的预注册方法说明](https://www.cos.io/initiatives/prereg)。本地实现复用通用评估器的完整覆盖、Brier分、相对冻结基线、校准、准确率及区间、多次计划检验处理与统计门槛，不新增一个可自行刷高的“权威分”。

本地哈希不证明问时真实、时钟可信、档案存在或不可回写，也不证明外部登记的内容一致、盲法执行、纳入规则执行、样本独立、主体同意、无人泄露结果、未试过其他未披露策略或结果判定公正。包源码与依赖文件指纹也不证明进程内代码未被篡改。研究应在独立固定检出和新进程中运行，并由可信登记和独立结果核验补足这些边界。即使全部程序门槛通过，也只得到提交记录的有限统计结果，不能据此宣称普遍预测有效、100%总体准确或最权威系统。


真太阳时版本还应冻结 `calendar_policy.solar_time_adjustment` 所载实际分项与方法。当前UTC近似UT1，不将距换时／换日的秒数当作误差界或确定性；独立太阳钟在5秒核对容差内仍有一例边界不能认证。每条研究证据绑定整个返回，修正依据变化会改变证据及引擎指纹；旧封存必须沿用其固定环境，不能据传统规则仍为2.12.0补写新回执。


## 逐例现实信息基线

`plan.baseline_probability` 是事前固定的全队列常数；它只是常数参照，胜过它不等于胜过现实信息模型。v3也支持 `plan.baseline_forecasts`：两者必须且只能选择一种，逐例模式将 `baseline_probability` 省略或设为null。每条逐例基线必须包含 `case_id/probability/issued_at/target_definition/window_start/window_end/source_sha256/source_reference`，完整且唯一覆盖计划队列。概率不可为空或非有限数；每条发布时刻不得晚于统一 `baseline_frozen_at`，统一冻结不得晚于预注册。每条目标字符串及实际窗口必须与研究完全相同，不能拿不同事件或不同期限的概率比较。

计算按case ID配对同一批可评估事件，模型及参考分别计算平均Brier损失，再取 `1 - BS_model / BS_reference`；不得先平均参考概率、按列表位置错配、为缺项退回0.5，或删掉参考表现较好的事件。准确率和既有校准表仍描述同一可评估子集，完整覆盖门槛继续约束整个队列。原有配对Hoeffding／Bonferroni保守界保持，固定参考可逐例不同，仍要求主体独立、事前冻结、计划检验次数与完整覆盖，不对相关天气站或重复主体自动作独立性认证。

方法参考[ECMWF概率预报检验报告](https://www.ecmwf.int/sites/default/files/elibrary/2006/74335-application-and-verification-ecmwf-products-member-states-and-co-operating-states_0.pdf)中逐个预报—观测对及参考预报的Brier定义，以及[Hoeffding原论文](https://doi.org/10.1080/01621459.1963.10500830)的独立有界和。来源记录及冻结时间只是声明；`baseline_comparison.source_provenance_authenticated/reference_strength_certified` 均为false，程序不能证明来源内容真的给出了该概率、参考足够强或研究已公开登记。研究者仍须事前选择与目标相称的现实信息参照，由独立方核验，不在看到结果后换基线。

可在新目录运行完全合成、全部弃权的逐例流程，查看真实写出的本地参考档案及对应文件字节哈希：

```bash
uv run --locked --extra dev python scripts/demo_qimen_study.py \
  --output-dir /tmp/fatebridge-qimen-per-case-demo \
  --baseline-kind per-case
```

该示例的每例概率0.5、目标、主体与来源均为人工演示；三个档案的存在和哈希吻合不成为真实外部基线。预期注册3例、可评估0例、现实效度未测试，不填补目前真实队列为0的缺口。逐例基线、完整封存及独立预存指纹均须在真实研究开始前落实，不能借新模式改写旧封存。

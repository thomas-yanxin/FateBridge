# 十二阶段的实际计算口径

综合、根命盘和九专题的`classical_root_profile.life_stage_profile`现在公开实际查表参数：十二支顺序、十二阶段顺序、十干长生起点与行向，以及这些参数的`lookup_sha256`。这是已有算法的回执，没有另建一套阶段计算，也没有修改旺衰权重。

当前选择阳顺阴逆，戊随丙寅生、己随丁酉生。十干起点为甲亥、乙午、丙寅、丁酉、戊寅、己酉、庚巳、辛子、壬申、癸卯。所选《三命通會》卷二〈論天干陰陽生死〉书影对应原PDF10、12、14、16、17–20、21、23、25、27页；封存的十条锚点（本地数据：`../tests/fixtures/bazi_stage_profile_v1/source-anchors-first.json`）记录页序、章节散列与阅读范围。

原PDF29–30还讨论土的体用及其他说法。当前选择不能包装成所有古籍唯一一致的土长生口径。完整原书指纹、作者、版本、页序和这一限制随回执返回；保留章节（本地数据：`../tests/fixtures/bazi_month_duty_identity_v1/chapter9-36.pdf`）依次为原PDF9–36。原件来自[四库本书影](https://archive.org/details/06066038.cn)，通行电子转录只作辅助。阴阳顺逆与阶段含义另对照《秘本子平真诠》PDF15–17；根类的有限形式化另取该书PDF22–23，两个来源的作用分别标明。

阶段名不能代替实体藏干、根力或受生能力：

- 戊在申为“病”，申中实际藏戊仍须保留，不能删根，也不能在此口径下称为阳长生强根。
- 癸在申为“死”，申藏壬仍是同五行的实体水根；有效力量还需要另行核对条件。
- 癸在卯为“长生”，卯中没有水藏干，阴长生的原典参考不能补造成实体水根。

身、印的实际藏根和未取整工程分量继续分列。司令的相对日序与实际出生瞬间分别核对；19例中只有ML-02给出“立春后六日、戊司令”，均缺可唯一复算的公历出生瞬间。阶段、根类或相生路径存在，都不能自动认证有效通关。相关裁定继续保持`not_adjudicated`，原有19个旺衰分歧保留。逐例依据与验证（本地数据：`validation/bazi-stage-profile-v1.md`）

公开工具的`stage_profile`是字段卡名称，调用时复制其`fields`，不把视图名称作为参数。数组根回执须整体读取，不能用`.roots.pillar`等路径深入数组成员。`force_roots`字段卡也包含阶段口径。按需合同由生成器更新，未手改生成文件。

例如读取虚构工程输入的口径与根回执：

```bash
uv run --locked --extra dev fatebridge bazi_birth \
  --birth-year 1993 --birth-month 12 --birth-day 12 --birth-hour 12 \
  --gender 男 --birth-timezone Asia/Shanghai --use-true-solar-time false \
  --fields bazi_birth.structure_profile.evidence_chain.classical_root_profile.life_stage_profile \
    bazi_birth.structure_profile.evidence_chain.classical_root_profile.roots \
  --strict-fields true --include-snapshot-text false
```

若返回`result_delivery`，按同次运行的交付继续读取并核对散列。工程验收显式使用完整回执检查三端一致，不能据此改判原8192字符无分页门槛。参数散列只检测参数是否相同，不证明来源真实、原典全文无分歧、独立专家认可或现实预测有效；现实预测继续为`not_tested`。

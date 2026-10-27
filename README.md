# research-roundup：调研整理与分工技能

一个给 Claude 用的技能（Skill）。队友整理文献、仓库、数据集、网页、别人写的调研报告时，让 Claude 按同一种版式产出文档，三段：

1. **信息列表**：把报告拆成一条条陈述逐条核实，每条给判定词（属实 / 大体属实 / 有误 / 无法核实 / 不判定）和证据；技术结论带"证据强度"；仓库、数据、评估方法各一张固定字段的表。
2. **分工**：谁看什么、每项"要回答"哪几个问题；需要有人拍板的事写成决定块（带推荐默认）；费 token、磁盘的任务写成指令卡交给执行者。
3. **交接**：要登记进总表的行、未解决问题（写明谁来了结）、证据放在哪里。

文档最前面是"先说结论"，可以单独转发。

这个版式来自一个多人科研项目里反复使用的调研文档。本仓库**只包含通用的方法、模板、检查脚本和虚构样例**，没有任何项目数据、内部路径或凭据。

## 什么时候会用到

在对话里出现下面这类需求时，Claude 会自动调用它（也可以手动输入 `/research-roundup`）：

- "帮我核对一下这份调研报告 / 群消息里的说法对不对"
- "这几个仓库和论文，帮我整理成清单，再分给我们几个人读"
- "写一份调研文档 / 交接文档 / 资料归档"
- "上一份调研有个数字写错了，怎么更正"

资料很少（少于 5 项）时它会用精简版：先说结论、核对表、资源表、每人一小段"要回答"、未解决问题，不硬凑决定块和指令卡。

## 安装

**Claude Code（命令行或桌面版的 Code 页签）**：把本仓库里的 `research-roundup/` 文件夹整个复制到下面任一位置。

| 范围 | 位置 |
|---|---|
| 只给自己，所有项目都能用 | `~/.claude/skills/research-roundup/`（Windows：`%USERPROFILE%\.claude\skills\research-roundup\`） |
| 只给某个项目，随项目仓库共享 | `<项目根目录>/.claude/skills/research-roundup/` |

复制后重开一个会话。文件夹里必须直接看到 `SKILL.md`，不要多套一层目录。

**Claude 桌面版 / 网页版**：在 Claude 的"技能"设置里上传打包好的 `.skill` 文件（入口名称随版本变化，以当前界面为准）。`.skill` 就是一个 zip，里面最上层是 `research-roundup/` 文件夹。没有现成文件时，自己打包：

```bash
zip -r research-roundup.skill research-roundup -x "research-roundup/evals/*"
```

Windows 没有 `zip` 命令时，用 PowerShell：

```powershell
Compress-Archive -Path research-roundup -DestinationPath research-roundup.zip
Rename-Item research-roundup.zip research-roundup.skill
```

## 怎么用

把材料交给 Claude，说清楚四件事：材料是什么、几个人分工、什么时候要用、哪些事不能做（能不能下载、运行代码、登录）。例子：

> 同事转发了一份 AI 写的调研报告（下面粘贴），原始资料在 `data/` 里。请逐条核对，整理成分工文档：我们两个人，A 看论文，B 看仓库和许可，下周五选型会前要定用哪个方法。

> 这三个链接帮我用精简版过一遍：哪些值得读，怎么分给我们两个人。

> 旧文档第 2 条的数字写错了，复算结果在 `recompute.txt`，按惯例处理这个更正。

Claude 交付时会说清三件事：文档在哪、哪些事没做到（没登录、没下载、没运行、没复算）、需要你拍板的事是哪几件。

想先看成品长什么样：`research-roundup/references/example.md` 是一份缩小的完整样例（**内容全部虚构**）。

## 自查脚本

`research-roundup/scripts/check_doc.py`：交付前检查一份调研文档（只读，不执行文档里的任何内容；Python 3.8 以上，只用标准库）。

```bash
python -I research-roundup/scripts/check_doc.py 文档.md --root 证据目录
```

检查：表格每行列数一致、有无残留占位符、`§` 引用能否在本文找到标题、编号是否递增、每节的行数和判定词统计（拿来核对开头的计数行）、反引号里的证据路径是否存在、相对链接是否有效。`--strict` 会把模板里的【填】也当作占位符；`--ignore 正则` 可以忽略仓库内路径。有错误返回 1，只有警告返回 0。

## 目录

```
research-roundup/
├── SKILL.md                 # 工作流、证据强度、硬规则、文风
├── references/
│   ├── structure.md         # 文档骨架和每张表的字段
│   ├── verification.md      # 拆陈述、判定、复算、口径冲突、身份与同名
│   ├── assignment-handoff.md# 决定块、优先级、指令卡、交接六项
│   └── example.md           # 缩小的虚构样例
├── assets/
│   ├── template.md          # 空白起点（【填】占位）
│   └── checklist.md         # 交付前自查清单
├── scripts/check_doc.py     # 自动检查
└── evals/                   # 三个评测用例（见下）
```

## 评测用例

`research-roundup/evals/` 里有三个用例，按 skill-creator 的格式写成（`prompt.md`、`case.yaml`、`graders/`、`files/`）：

| 用例 | 测什么 |
|---|---|
| `verify-report-and-assign` | 六条陈述的报告对照原始文件核实：算出 11.4%、发现许可证冲突、标出无法核实的一条；先说结论的计数与表一致；决定块有推荐默认；不下法律结论 |
| `three-links-no-network` | 三个读不到的链接：不编造内容，写明没读，用精简版 |
| `append-correction-not-edit` | 更正走追加勘误，不改旧文，不重排编号 |

**这些用例还没有跑过**。断言是按预期写的，跑起来可能要调。有 Claude Code 的人可以按 skill-creator 的说明在 `research-roundup/` 目录下运行（会产生真实计费的模型调用）：

```bash
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
```

## 已验证 / 未验证

- 已验证：`check_doc.py` 在一份约 700 行的真实调研文档上跑过（0 个错误，只报出两个确实没存副本的证据路径）；在 `example.md` 上 0 个错误；在 `template.md` 上加 `--strict` 会按预期报出所有占位符。
- 未验证：技能被触发的准确度、不同模型下产出的质量，都没有做过自动评测。

## 修改

- 改 `SKILL.md` 或 `references/` 后，在 `example.md` 上再跑一遍 `check_doc.py`，确认没有新错误。
- 判定词、证据强度的说法写在 `SKILL.md`、`references/verification.md`、`assets/template.md` 和 `check_doc.py` 的 `DEFAULT_VERDICTS`，改一处要把四处一起改。
- 重新打包（有 skill-creator 时）：`python -m scripts.package_skill research-roundup 输出目录`（从 skill-creator 目录运行）。

## 使用前

- 内部项目的文档里常有路径、人名、未公开的结果。交付前先问一句"这份能不能外传"，别把项目数据提交到公开仓库。
- 技能要求"只读"：不运行别人的代码，不下载大文件和模型权重，不登录。需要这些才能看到的内容，会被写进"没做到"。

## 许可

MIT，见 `LICENSE`。

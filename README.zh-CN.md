<div align="center">

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          ██╗      █████╗ ███╗   ██╗ ██████╗                   ║
║          ██║     ██╔══██╗████╗  ██║██╔════╝                   ║
║          ██║     ███████║██╔██╗ ██║██║  ███╗                  ║
║          ██║     ██╔══██║██║╚██╗██║██║   ██║                  ║
║          ███████╗██║  ██║██║ ╚████║╚██████╔╝                  ║
║          ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝   flynn           ║
║                   M I G R A T I O N                           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
ClawHub: [https://clawhub.ai/suifei/lang-migration](https://clawhub.ai/suifei/lang-migration)

Skillhub:[https://skillhub.cn/skills/lang-migration](https://skillhub.cn/skills/lang-migration)

# 编程语言迁移（lang-migration）

**一套正式的、证据驱动的AI程序翻译方法论**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![支持语言对: 14](https://img.shields.io/badge/Language_Pairs-14-blue)](#语言对)
[![阶段: P0–P6](https://img.shields.io/badge/Phases-P0_through_P6-green)](#六阶段流水线)
[![防作弊](https://img.shields.io/badge/Anti--Cheating-Protocol_Enforced-red)](#核心创新证据义务)
[![兼容工具](https://img.shields.io/badge/Works_With-Claude_Code_|_Cursor_|_Copilot_|_OpenCode-purple)](#运行环境)
[![版本: 1.2](https://img.shields.io/badge/Version-1.2-blue)](#阶段门禁复盘-pgr--v12)

**[English](README.md) | 中文**

*跨编程语言迁移任何开源代码库 — 保证结构完整性、持久化状态管理，并提供AI实际完成工作的可验证证明。*

### ✨ **v1.2 新增：阶段门禁复盘（PGR）**

每个阶段流转前，必须通过**自主自审循环**才能推进。AI枚举所有预期产出，逐项审计，修复发现的问题，再次审计——直至**零发现**。
只有这时，阶段才被标记为完成。全程无需人类干预，杜绝橡皮图章式推进。[了解更多 →](CHANGELOG.md#v12--2026-05-15)

</div>

---

## 无人谈论的问题

当开发者要求LLM"将我的Python项目迁移到Go"时，通常会发生这三种情况之一：

1. **LLM生成看似合理的代码，但无声地丢失行为。** 类型语义、精度契约、排序不变量 — 全部消失。没人注意到，直到线上出问题。

2. **LLM报告完成，但其实没做任何工作。** 它标记任务完成，生成占位符内容，然后继续。这不是漏洞 — 这是对模糊完成标准的理性回应。

3. **上下文窗口崩溃。** 50,000行代码无法装进任何单个提示。LLM在翻译到一半时失去连贯性，整个迁移变成了一场"到底翻译了什么"的考古学。

**lang-migration** 是对这三种失败模式的结构化响应 — 不是通过更好的提示词，而是通过正式的方法论。

---

## 这是什么

`lang-migration` 是一个 **AI技能** — 一份可迁移的、与代理无关的规范，它告诉任何有能力的LLM *确切地* 如何迁移代码库、按什么顺序进行、需要什么证据、以及如何证明工作确实完成了。

它不是你运行的工具。它是你安装到AI编码代理中的协议。

可以把它想象成一份**研究方法论**，就像研究生遵循实验室协议一样 — 除了这份实验室协议是专门设计来检测和防止研究生（和LLM）倾向于走捷径的方式。

---

## 核心创新：证据义务

这个方法论的中心创新是我们称之为**证据义务**的原则 — 即*任何工作单元直到AI生成只有通过实际完成工作才能生成的工件时才算完成*。

这不同于要求AI"要彻底"。彻底是道德呼吁。证据义务是结构性约束。

### 实践中的工作方式

考虑第3阶段（IPO分析），AI必须在翻译前记录每个函数。在朴素提示下，LLM会在几秒内为数百个函数生成看似合理的文档 — 没有一个针对实际源代码验证过。

在证据义务下，AI必须在填写任何条目前生成 `READ_EVIDENCE` 块：

```
READ_EVIDENCE for agent_loop.py::run_step:
  file_read: "agent_loop.py:42-89"
  first_statement: "outcome = self._dispatch_tool(tool_call)"
  last_statement:  "return StepOutcome(data=result, next_prompt=follow_up)"
  literal_count:   3
  call_count:      7
  branch_count:    4
```

这些值 — 第一个和最后一个可执行语句的确切文本、数字字面量的精确计数、分支点数 — 不能在不读取文件的情况下捏造。幻觉的块会产生错误的行号、错误的计数、错误的语句文本。这在验证期间变得可检测。

AI还必须为每个函数生成 `BEHAVIOR_PROOF`：

```
BEHAVIOR_PROOF for calculate_entropy:
  happy_path:    "Given data=[0.3,0.3,0.4], base=2 → returns 1.5710 (bits)"
  edge_case_1:   "Given data=[0.0, 1.0], filters 0.0 (epsilon=1e-10), returns 0.0"
  would_fail_if: "sum(data) >> 1.0 — inferred invariant violated, results meaningless"
```

通用答案（"给定有效输入返回预期结果"）被禁止。具体数值需要真正的理解。

---

## 六阶段流水线

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  P0  引导启动      检测语言对，初始化工作空间                      |
│   │                                                             │
│  P1  资源扫描      每个文件已分类 — 没有遗漏                       │
│   │                                                             │
│  P2  生态系统映射  每个导入/类型已映射，附带证据                    │
│   │                                                             │
│  P3  IPO分析       每个函数：输入、处理、输出                      │
│   │                强制执行READ_EVIDENCE + BEHAVIOR_PROOF        │
│   │                                                             │
│  P4  翻译          从IPO规范翻译，不是源代码                      │
│   │                每个函数强制target_lines                      │
│   │                                                             │
│  P5  验证          真实测试、真实数据 — 永远不模拟                 │
│   │                                                             │
│  P6  间隙报告      随时调用："还差什么？"                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 为什么从IPO翻译，而不是源代码？

第4阶段有个不寻常的约束：AI从**IPO注册表**翻译，而不是直接从源代码翻译。可以咨询源代码以获得澄清，但IPO条目是契约。

这种分离是有意的。当AI读取源代码并立即写入目标代码时，它会产生一个*风格近似* — 捕获表面语法，同时无声地丢弃语义契约、魔法数字用途和推断的不变量。通过强制一个两步过程（理解 → 记录 → 翻译），方法论创建了一个检查点，其中丢失的信息在翻译前变得可见，而不是之后。

---

## 持久化状态作为一级关注

每次迁移都在 `migration_workspace/` 中的五个YAML文件中：

```
migration_workspace/
├── migration-state.yaml             ← 会话入口点。始终先读这个。（含 phase_gates 追踪块）
├── asset-inventory.yaml             ← 每个源文件、其迁移策略、其状态
├── ecosystem-map.yaml               ← 每个库/类型/习用语映射到目标等价物
├── ipo-registry.yaml                ← 每个函数：输入、处理步骤、输出
└── retrospective-checklist.yaml     ← P4/P5 每次修复的根因记录（第五个工作区文件）
```

这些文件是迁移的"记忆"。任何AI代理 — Claude Code、Cursor、GitHub Copilot、OpenCode — 都可以通过读取 `migration-state.yaml` 在会话中间接续迁移。状态不在AI的上下文窗口中；它在磁盘上。

这使迁移**可恢复、可审计且可转移**。在一个工具中启动的迁移可以在另一个工具中继续。被上下文崩溃中断的迁移可以恰好从停止的地方恢复。

### 状态机

```yaml
# migration-state.yaml (摘录)
phases:
  P0_bootstrap:     DONE
  P1_asset_scan:    DONE
  P2_ecosystem_map: IN_PROGRESS
  P3_ipo_analysis:  TODO
  P4_translation:   TODO
  P5_verification:  TODO

current_task:
  phase: P2_ecosystem_map
  item_id: "numpy.random.default_rng"
  status: BLOCKED
  block_reason: "RNG算法不同（Mersenne Twister vs PCG64）；不可能输出完全相同"
  human_input_required: |
    统计等价性充分，还是需要完全相同的种子行为？
```

当 `status: BLOCKED` 时，AI立即停止，向操作员呈现结构化阻塞，并等待。它不继续、不标记并继续、不无声地替代猜测。

---

## 生态系统映射：跨语言的类型系统契约

在任何翻译开始之前，源中使用的每个库符号、类型和stdlib函数必须被映射到其目标等价物、按等价性类型分类，以及 — 至关重要的 — 用表明映射实际被研究过的证据进行注释。

```yaml
- id: "numpy.random.default_rng"
  source_semantics: "PCG64 PRNG，可种子化，跨平台可重现"
  target_equivalent: "math/rand/v2.New(rand.NewPCG(seed, 0))"
  equivalence_type: structural
  precision_delta: none
  gap_notes: "Go 1.22+使用PCG的rand/v2；1.22前使用不同算法"
  confirmation_evidence:
    source_behavior:  "NumPy default_rng自NumPy 1.17起使用PCG64，128位状态"
    target_behavior:  "math/rand/v2 PCG源：算法相同，相同种子输出相同"
    verified_from:    "numpy.org/doc/stable/reference/random/generator.html + pkg.go.dev/math/rand/v2"
```

对于每个 `CONFIRMED` 映射，`confirmation_evidence` 块是强制性的。空的证据字段被视为 `NEEDS_REVIEW`，无论 `status` 字段如何。这防止了常见的失败模式，其中AI确认数百个映射而不查看任何一个。

---

## 语言对

这个方法论包含14个预构建的语言对模块，涵盖常见的迁移路径。每个模块包含：

- 预映射的标准库和生态系统符号
- 已知的语义差异和补偿策略
- 语言特定的反模式在翻译期间要避免
- 测试工具链映射
- CI/CD适配模板

| 源语言 | 目标语言 | 难度 | 主要挑战 |
|--------|---------|------|---------|
| Python | **Rust** | ★★★★ | 所有权、GC→借用检查、特征系统 |
| Python | **Go** | ★★★ | 错误处理习用语、goroutine、接口鸭子类型 |
| Python | **C** | ★★★★ | 手动内存、指针运算、没有stdlib集合 |
| Python | **C++** | ★★★ | RAII、模板元编程、priority_queue方向 |
| Python | **Zig** | ★★★★ | 显式分配器、comptime泛型、错误联合 |
| Python | **TypeScript** | ★★ | `undefined` vs `null`、结构类型、工具类型 |
| Python | **Bun (JS)** | ★★ | 数字精度差异、没有可种子化RNG |
| Rust | **Python** | ★★ | 所有权 → 注释、Result → 异常 |
| Go | **Python** | ★★ | 多返回值 → 异常、defer → 上下文管理器 |
| C | **Python** | ★★ | 指针对 → 单个对象、字符串编码 |
| C++ | **Python** | ★★ | RAII → `__del__`/contextmanager、模板 → TypeVar |
| Zig | **Python** | ★★ | 分配器消失、comptime → TypeVar |
| Bun | **Python** | ★★ | 数字消歧、`undefined` 映射 |
| TypeScript | **Python** | ★ | 近1:1类型映射、工具类型 → 数据类 |

可以使用 `TEMPLATE.md` 添加新的语言对 — 方法论在设计上是与语言无关的。

---

## P6：间隙报告 — 连续完整性审计

大多数迁移工具回答问题"我们做了什么？"。间隙报告回答更难的问题：**"什么是真正缺失的，为什么？"**

这是唯一可以随时调用的阶段 — P5前、P3期间，或AI声称迁移完成后。实际上，它最有用的时候恰恰是AI*已经*声称完成时，因为那正是隐藏间隙最危险的时候。

调用方式：*"还差什么" / "gap report" / "显示迁移状态"*

### 五个维度

该报告不计算单一的完成百分比。它运行五个独立审计，每个都可以揭示不同的失败类别：

**维度1 — 文件覆盖**：交叉引用`asset-inventory.yaml`中的每个条目与目标目录中磁盘上的实际文件。一个在注册表中`status: DONE`但在磁盘中不存在的`translate`策略文件是关键间隙 — AI更新了YAML但从未写入代码。这个维度会捕获这个。

**维度2 — 函数覆盖**：扫描`ipo-registry.yaml`寻找标记为`translation_status: DONE`但`target_lines`字段为空的函数。这是批量捏造问题的标准特征：AI标记函数完成但没有产生或定位实际实现。报告将这些称为"DONE but no evidence"（完成但无证据）并标记为需要重新验证。

**维度3 — 目录结构间隙**：独立遍历源和目标目录树，然后识别源目录在目标中没有对应项的部分。这捕获文件级检查遗漏的结构性遗漏 — 被跳过的整个模块树、没有目标等价物的测试固件子目录、在P1中记录但在P4中从未处理的内部包。

**维度4 — 非代码资源覆盖**：检查`direct_use`文件（测试固件、二进制数据、静态资源）是否确实被复制到目标。也检查资源清单中标记为`p3_required: true`的每个文件是否实际在IPO注册表条目中被引用。一份本应为IPO分析提供信息但从未被引用的设计文档不是小过疏忽 — 这意味着它描述的函数可能在没有完整上下文的情况下被分析过。

**维度5 — 跳过分类**：区分三个失踪文件类别，具有根本不同的含义。*记录在案的故意跳过*（在`decisions_log`中）不需要操作。*平台特定跳过*（Streamlit、PyQt5、tkinter、ultralytics）由关键字自动检测，不需要操作。*意外间隙* — 资源清单中`status: DONE`但没有目标文件且没有记录原因的文件 — 是关键发现。它们代表AI声称已完成但可证明尚未完成的工作。

### "真正的1:1完成"指标

```
═══════════════════════════════════════════════════════════════
迁移完整性审计 — genericagent → malaclaw
生成时间: 2026-05-15  |  python → go  |  150个源文件
═══════════════════════════════════════════════════════════════

文件覆盖
  translate文件:   49/52  (94.2%) — 缺失3个
  adapt文件:       15/15  (100%)
  direct_use文件:  54/57  (94.7%) — 缺失3个

函数覆盖
  真正完成:        138/142 (97.2%)
  ⚠️  完成但无证据:   4       ← 需要重新验证
  被阻塞:          0

目录覆盖
  源目录已映射:    11/14 (78.6%)
  未映射源:        3个目录

非代码资源
  目标中的固件:    54/57
  P3文档引用:      8/11

跳过分类
  故意跳过:        9个 (已记录)
  平台特定:        7个 (Streamlit, PyQt5, tkinter...)
  ⚠️ 意外间隙:     2个       ← 需要注意

───────────────────────────────────────────────────────────────
真正的1:1完成: 94.8%
───────────────────────────────────────────────────────────────

优先行动项:
  🔴 严重: 4个函数标记完成但无target_lines — 需要重新验证
  🔴 严重: 缺失2个源文件，无记录原因
  🟡 重要: genericagent/memory/L4_raw_sessions/ 无目标等价物
  🟢 轻微: 3份p3必需文档从未在IPO注册表中被引用
```

真正的1:1完成指标故意保守。它只在目标文件在磁盘上存在时才计为完成。它只在`translation_status: DONE` AND `target_lines`非空时才计函数为完成。YAML中的自我报告状态永远不被直接接受 — 文件系统是绝对真实。

这种保守主义是重点。一个乐观的完成指标信任AI的自我评估不是完成指标；它是AI所声称的记录。只有基于物理工件的指标 — 存在的文件、填充的行范围 — 才能回答人类真正关心的问题。

---

## 为什么不直接用转译器？

现有的自动化转译器（如 `py2many`、`Transcrypt` 或语言特定的工具）在语法上操作 — 它们将AST节点映射到AST节点。它们对简单情况通常快速且正确。

当以下情况发生时它们系统性地失败：

- **语义契约跨越库边界。** `numpy.float64` 不仅仅是"一个浮点数" — 它承载广播语义、NaN传播规则和精度保证，没有语法转换可以发现。

- **魔法数字承载领域知识。** 熵函数中的字面量 `1e-10` 不是随机常数 — 它是一个epsilon底限防止 `log(0)`，源自作者对数值稳定性的理解。没有转译器记录这个。我们的方法论要求在翻译前记录它。

- **推断的不变量塑造正确性。** 代码通常工作是因为调用者遵循不成文的规则。一个在没有保护的情况下除以 `len(data)` 的函数工作只是因为每个调用者这些年来一直传递非空列表。转译器无法发现这个。我们的IPO分析要求在翻译前记录它。

- **建筑意图丢失。** 当Python类使用 `collections.OrderedDict` 时，作者选择了有序迭代。转译器将其映射到 `map[K]V` 并无声地丢失排序契约。我们的生态系统映射要求这个差异被记录和补偿。

---

## 无模拟原则

迁移项目中的每个测试都使用真实实现对真实数据。

这不是理想主义 — 这是正确性要求。通过基于模拟的测试套件的迁移只证明了什么关于行为等价性。它只证明了模拟被正确连接。

当没有真实依赖的情况下测试无法运行时（数据库、硬件设备、第三方API），方法论不模拟它。它阻塞、记录缺失的依赖、等待操作员提供真实环境。测试保留在套件中，标记为需要真实依赖，当该依赖变得可用时通过。

这很不舒服。它也是唯一知道迁移是否正确的方式。

---

## 运行环境

该方法论是代理无关的。它被设计为在以下环境中运行：

| 环境 | 模式 | 说明 |
|------|------|------|
| **Claude Code** | `full_mode` | Bash + 文件系统；直接运行扫描脚本 |
| **OpenCode** | `full_mode` | 与Claude Code相同 |
| **Cursor** | `editor_mode` | 仅文件系统；脚本手动运行 |
| **GitHub Copilot** | `editor_mode` | 与Cursor相同 |

在 `full_mode` 中，AI直接运行 `scan_assets.py` 和 `gap_report.py`。
在 `editor_mode` 中，AI手动生成文件列表并指导操作员运行脚本。

---

## 安装

```bash
# 克隆到你的项目的 .agents/skills 目录
mkdir -p .agents/skills
git clone https://github.com/suifei/lang-migration-skill.git .agents/skills/lang-migration-skill
```

然后告诉你的AI代理：

```
/lang-migration  source: my-python-project/  target: my-go-project/  pair: python-go
```

代理读取 `SKILL.md`，初始化 `migration_workspace/`，并开始第1阶段。

---

## 仓库结构

```
lang-migration/
├── SKILL.md                              ← 代理入口点和编排协议
├── CHANGELOG.md                          ← 版本历史
├── templates/
│   ├── migration-state.yaml              ← 会话状态机（含 phase_gates 追踪块）
│   ├── asset-inventory.yaml              ← 文件分类注册表
│   ├── ecosystem-map.yaml                ← 库/类型映射注册表
│   ├── ipo-registry.yaml                 ← 函数IPO规范注册表
│   └── retrospective-checklist.yaml      ← 修复根因记录（第五个工作区文件）
├── references/
│   ├── schemas.md                        ← 所有五个YAML文件的完整字段定义
│   ├── phase-0-bootstrap.md              ← P0 工作区初始化参考
│   ├── phase-1-asset-scan.md
│   ├── phase-2-ecosystem-map.md
│   ├── phase-3-ipo-analysis.md           ← 证据义务协议在这里
│   ├── phase-4-translation.md
│   ├── phase-5-verification.md
│   ├── phase-6-gap-report.md
│   ├── phase-gate-review.md              ← PGR 自主闭环协议（v1.2）
│   ├── tdd-retrospective.md              ← 修复复盘协议（v1.1）
│   └── lang-pairs/
│       ├── TEMPLATE.md                   ← 扩展到新语言对
│       ├── python-rust.md
│       ├── python-go.md
│       ├── python-c.md
│       ├── python-cpp.md
│       ├── python-zig.md
│       ├── python-bun.md
│       ├── python-typescript.md
│       ├── rust-python.md
│       ├── go-python.md
│       ├── c-python.md
│       ├── cpp-python.md
│       ├── zig-python.md
│       ├── bun-python.md
│       └── typescript-python.md
└── scripts/
    ├── scan_assets.py                    ← 第1阶段文件扫描器
    └── gap_report.py                     ← 第6阶段完整性审计器
```

---

## 贡献

最有价值的贡献是**新的语言对模块**和**真实迁移报告**。

**新语言对**：复制 `references/lang-pairs/TEMPLATE.md`，填写所有章节，提交PR。专注于非明显的差异 — 源语言的资深开发者会假设但目标语言的开发者不会知道查找的东西。

**迁移报告**：如果你在真实项目上使用这个方法论，我们想知道：间隙报告捕获了什么？预构建模块中的哪些生态系统映射是错误的？什么样的阻塞决策出现了？

方法论通过累积的案例知识改进。每一个报告反馈的真实迁移都使下一个更可靠。

---

## 开放问题（研究方向）

这个方法论提出了我们还没有完全回答的问题：

**关于语义等价性**：`BEHAVIOR_PROOF` 要求要求AI为每个函数指定具体输入输出对。这是*行为契约*的较弱形式。这些契约可以使用基于属性的测试框架（Hypothesis、proptest）自动检查以正式验证跨语言边界的等价性吗？

**关于证据线索**：`READ_EVIDENCE` 和 `BEHAVIOR_PROOF` 块目前是短暂的 — 它们出现在AI的响应中但不存储。可以捕获它们并用来构建一个持久的*理解证明*档案，在会话间存活吗？

**关于非确定性**：当源函数使用具有可重现种子的RNG时，迁移必须记录是否需要比特相同输出或统计等价充分。这目前是人工决策。可以通过分析非确定性输出的下游消费者来自动化吗？

**关于多代理并行性**：当前方法论是顺序的 — 一个AI代理，一次一个函数。对于大型代码库（100k+行），多个代理可以在依赖图的独立子树上并行工作，由协调器合并其IPO注册表吗？

---

## 许可证

MIT。自由迁移。

---

<div align="center">

*"看起来有效"和"有效"之间的差异是大多数迁移所在的地方。*
*这个方法论是一次使那个差异可见、可测量和可闭合的尝试。*

**如果你曾经收到一份"迁移完成"的报告，但其实没有，请给这个项目点星。**

</div>

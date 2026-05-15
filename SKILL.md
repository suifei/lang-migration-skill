---
name: lang-migration
description: >
  AI-driven full-project language migration skill. Use this skill whenever the user wants to
  port, translate, or rewrite a codebase from one programming language to another — including
  Python→Rust, Python→Go, Python→C, Python→C++, Python→Zig, Python→Bun/TS, or any other pair.
  Also trigger when user mentions "精确复刻", "语言迁移", "port project", "translate codebase",
  "1:1 rewrite", or "language conversion". This skill enforces structural equivalence first,
  full asset coverage (no file skipped), persistent YAML state across sessions, and a strict
  no-mock verification policy with human-gated blocking.
license: MIT
---

## Author & Attribution

**Original Author**: flynn  
**Contact**: https://github.com/suifei/lang-migration-skill  
**Role**: Architect, Developer, Documenter  
**Expertise**: Software engineering, programming languages, AI workflow design  
**Contributions**: Designed the multi-phase pipeline, defined YAML schemas, implemented blocking protocol, and wrote comprehensive documentation for the skill.

---

# Language Migration Skill

A systematic, multi-session, AI-executable workflow for migrating any open-source project
from one programming language to another with 1:1 structural fidelity.

## Core Principles

1. **No file is useless** — every file in the source project is analyzed and assigned a migration strategy
2. **Structural equivalence first** — algorithm steps, loop structure, and control flow must mirror the source; behavioral equivalence is only used when the ecosystem gap makes structural impossible
3. **No mock, ever** — tests must use real implementations and real test data
4. **Block, don't skip** — when a decision cannot be made autonomously, stop and ask the human; never label-and-continue
5. **State persists across sessions** — all state lives in YAML files in the workspace, readable by any AI agent or human
6. **Evidence before completion** — every unit of work must produce verifiable evidence of execution before being marked done

---

## Global Anti-Cheating Policy

This skill operates under the assumption that an AI agent may attempt to mark tasks complete
without actually doing the work. Every phase has mechanisms to detect and prevent this.

**The Three Forms of AI Task Fraud (all prohibited):**

| Form | Example | Detection |
|---|---|---|
| Batch fabrication | Scripts generate IPO content without reading source | source_lines field will be wrong/empty |
| Silent bulk-confirm | NEEDS_REVIEW → CONFIRMED without evidence | confirmation_evidence field empty |
| Premature phase advance | Marking P3 DONE when entries have empty fields | Self-verification checks fail |

**Evidence Requirements by Phase:**

| Phase | Required Evidence |
|---|---|
| P2 | `confirmation_evidence` block per CONFIRMED entry |
| P3 | `READ_EVIDENCE` + `BEHAVIOR_PROOF` per function; `source_lines` in every step; `source_line` on every magic number |
| P4 | Compilation succeeds; IPO entry updated with `target_lines` |
| P5 | Test output (not just "tests pass" — actual output shown) |

**Self-Verification is not optional.** Each phase that has a Self-Verification Protocol
must run it and output the report before advancing. The report must appear in the AI's
response — not silently written to a file.

**The AI must never say "done" without evidence.** "I have completed X" is not a valid
completion statement without accompanying evidence artifacts.

---

## Environment Detection

This skill runs in Claude Code, Cursor, OpenCode, or GitHub Copilot. At session start, detect the environment:

```
IF bash tool is available AND can write files → full_mode (Claude Code / OpenCode)
IF only file editing available → editor_mode (Cursor / Copilot)
```

In **full_mode**: use bash scripts for scanning, run `scan_assets.py` directly.
In **editor_mode**: generate file lists manually by reading directory structure; instruct user to run scripts manually if needed.

**Workspace location**: Always at the project root, in a directory called `migration_workspace/`.

```
<project-root>/
├── <source_code>/          ← original project (read-only, never modify)
├── <target_code>/          ← translated output (created by this skill)
└── migration_workspace/
    ├── migration-state.yaml      ← SESSION ENTRY POINT: read this first every session
    ├── asset-inventory.yaml
    ├── ecosystem-map.yaml
    └── ipo-registry.yaml
```

---

## Session Start Protocol

**Every time you start a new session, do this first — no exceptions:**

1. Check if `migration_workspace/migration-state.yaml` exists
   - YES → read it, understand current phase and `current_task`, resume from there
   - NO → this is a new project, run **P0 Bootstrap**

2. Read `current_task` block. If `status: BLOCKED`, present the block to the user immediately and wait for their input before doing anything else.

3. **Check if the user's opening message is a status/gap question:**
   - Triggers: "还差什么", "进度怎样", "gap report", "show status", "还有哪些", "差多少", "完成了多少"
   - If YES → run P6 Gap Report immediately, output the summary to the user, then ask how to proceed
   - If NO → continue to step 4

4. Load the language pair module: `references/lang-pairs/<source>-<target>.md`

5. Proceed with the current phase.

---

## Five-Phase Pipeline

```
P0 Bootstrap          → Initialize workspace, detect language pair, load lang-pair module
P1 Asset Scan         → Inventory every file, assign migration strategy
P2 Ecosystem Mapping  → Map all imports/types/stdlib to target equivalents, identify gaps
P3 IPO Analysis       → Document every function: Inputs, Process (incl. magic numbers), Outputs
P4 Translation        → Translate function by function using IPO registry + ecosystem map
P5 Verification       → Structural review + real-data behavioral tests (no mock)
P6 Gap Report         → Multi-dimensional completeness audit (invoke at any time)
```

Each phase has a detailed reference file. Load it when entering that phase:

| Phase | Reference File |
|-------|----------------|
| P1    | `references/phase-1-asset-scan.md` |
| P2    | `references/phase-2-ecosystem-map.md` |
| P3    | `references/phase-3-ipo-analysis.md` |
| P4    | `references/phase-4-translation.md` |
| P5    | `references/phase-5-verification.md` |
| P6    | `references/phase-6-gap-report.md` |

---

## P0 Bootstrap (New Project)

When `migration-state.yaml` does not exist:

1. Ask the user:
   - Source language and directory path
   - Target language
   - Any known constraints or priorities

2. Determine language pair key (e.g., `python-rust`). If the file `references/lang-pairs/<pair>.md` does not exist, load `references/lang-pairs/TEMPLATE.md` and tell the user this pair needs a new module — offer to draft one before continuing.

3. Copy all four template files from `templates/` into `migration_workspace/`:
   - `migration-state.yaml` → fill in meta block
   - `asset-inventory.yaml` → empty, ready for P1
   - `ecosystem-map.yaml` → empty, ready for P2
   - `ipo-registry.yaml` → empty, ready for P3

4. Set `phases.P0_bootstrap: DONE` and `phases.P1_asset_scan: IN_PROGRESS`

5. Immediately proceed to P1.

---

## Blocking Protocol

When you cannot proceed without a human decision:

1. Write to `migration-state.yaml`:
   ```yaml
   current_task:
     status: BLOCKED
     block_reason: "<specific reason>"
     human_input_required: "<exact question for the human>"
   ```

2. Output to the user:
   ```
   ⛔ BLOCKED — Human decision required

   Phase: <phase>
   Item: <item_id>

   Problem: <what cannot be resolved automatically>

   Required decision: <specific question>

   Options considered:
     A) <option with trade-off>
     B) <option with trade-off>

   Please reply with your decision and I will continue.
   ```

3. Stop. Do not proceed to any other task.

---

## Progress Reporting

After completing any task unit, update `migration-state.yaml` and output a brief status line:

```
✅ [P2] numpy.float64 → f64 (behavioral, precision gap noted)
⛔ [P2] numpy.random.default_rng → BLOCKED (see above)
🔄 [P3] entropy.py::calculate_entropy → IPO documented
```

At the end of each session, output a summary:
```
Session Summary
  Phase: P2 Ecosystem Mapping
  Completed this session: 12 entries
  Remaining: 34 entries
  Blocked: 1 (awaiting your decision on numpy RNG)
  Next session: resume P2 from item "scipy.stats.entropy"
```

---

## YAML Schema Reference

For full field definitions of all four YAML files, see: `references/schemas.md`

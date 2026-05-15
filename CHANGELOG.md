# Changelog

All notable changes to the lang-migration skill are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v1.2] — 2026-05-15

### Major Features

#### 🔁 Phase Gate Review (PGR) — Autonomous Inter-Phase Closure

Every phase transition now requires passing an autonomous self-auditing loop before the AI is allowed to advance. The pipeline becomes:

```
P0 → [PGR-0] → P1 → [PGR-1] → P2 → [PGR-2]
  → P3 → [PGR-3] → P4 → [PGR-4] → P5 → [PGR-5] → DONE
```

**Core rule**: A phase is not complete when the AI says it is complete. A phase is complete when `PGR-N` passes with zero findings and writes a `passed_at` timestamp.

**The PGR loop** (autonomous, no human required):
1. Enumerate all expected outputs of the completed phase
2. Audit each output against its evidence requirement
3. For each FINDING: fix it autonomously, log the fix
4. Re-run the full audit from step 1
5. Repeat until zero findings
6. On zero findings: set `phase_gates.PGR_N.status: PASSED`, then and only then set `phases.PN_xxx: DONE`

**Per-phase audit criteria** (see `references/phase-gate-review.md`):

| Gate | Verifies |
|------|---------|
| PGR-0 | All 5 workspace files exist; `meta` block fully populated; lang pair module loaded |
| PGR-1 | Every source file in inventory; no empty `purpose` fields; no AUTO-CLASSIFIED notes surviving |
| PGR-2 | Every import/symbol in ecosystem map; all entries `CONFIRMED` with non-empty `confirmation_evidence` |
| PGR-3 | Every function in IPO registry; all `source_lines` non-empty; no `DONE` status (P3 never translates) |
| PGR-4 | Every translate-strategy file exists on disk; all `target_lines` populated; build passes |
| PGR-5 | TEST OUTPUT EVIDENCE present; gap report run; zero accidental gaps; retrospective checklist complete |

**Session consistency check**: At every session start, for each phase marked `DONE`, the corresponding `phase_gates.PGR_N.passed_at` must be non-empty. If a phase is `DONE` but `passed_at` is empty, PGR-N is re-run before advancing.

#### 📋 Fifth Workspace Template: `retrospective-checklist.yaml`

The retrospective checklist is now formally initialized at P0 Bootstrap alongside the other four YAML files. Previously it was described as "auto-grows" with no starting template. Now:
- `templates/retrospective-checklist.yaml` ships as the fifth template
- P0 Bootstrap copies all five templates to `migration_workspace/`
- PGR-0 verifies all five files exist

#### 📁 Phase 0 Reference File: `references/phase-0-bootstrap.md`

P0 Bootstrap now has a dedicated reference file matching the pattern of P1–P6. Contains:
- Full step-by-step Bootstrap instructions (gather info → resolve lang pair → initialize workspace → fill meta → trigger PGR-0)
- Exit criteria checklist
- Common failure modes table (missing `source_version`, target_dir = source_dir, missing lang pair module)

---

### Quality Fixes (11 items)

#### Script Bugs

| ID | File | Fix |
|----|------|-----|
| B-1 | `gap_report.py` | Action message for unexpected target dirs used the list object instead of the count integer |
| B-2 | `gap_report.py` | Platform-specific skip reason was hardcoded as "no Go equivalent"; now reads `target_lang` from `migration-state.yaml` |
| B-3 | `scan_assets.py` | `os.makedirs` raised `FileNotFoundError` when output path had no directory component (bare filename) |

#### Design Improvements

| ID | Fix |
|----|-----|
| D-1 | `scan_assets.py`: add PyYAML import error handling with install hint (matches `gap_report.py` behavior) |
| D-2 | `templates/retrospective-checklist.yaml`: correct init comment from "P4 start" to "P0 Bootstrap"; `SKILL.md` P0 Bootstrap updated to list 5 templates |
| D-3 | `gap_report.py`: warn prominently (stdout + report header) when `--target` directory does not exist, preventing silent misread as 0% completion |
| D-4 | `gap_report.py`: add `todo_list_truncated: true` flag to dim2 output when list is capped at 20 entries |

#### Documentation

| ID | Fix |
|----|-----|
| Doc-1 | `RELEASE_NOTES_v1.1.md`: replaced 172-line duplicate content with 20-line redirect index pointing to CHANGELOG |
| Doc-2 | `references/phase-0-bootstrap.md`: new dedicated P0 reference file (114 lines); added to phase reference table in SKILL.md |
| Doc-3 | `README.md`: removed unclosed nested `<div align="center">` (HTML malform) |

#### Minor

| ID | Fix |
|----|-----|
| M-1 | `scan_assets.py`: unified `.yml` and `.yaml` to same default type `environment_config`; previously `.yml` defaulted to `ci_config` causing inconsistent strategies for same-purpose files |

---

### Updated Components

| File | Changes |
|------|---------|
| `SKILL.md` | PGR protocol section; updated pipeline diagram; phase reference table includes P0 and PGR; P0 Bootstrap copies 5 templates; session start checks `passed_at` consistency |
| `references/phase-gate-review.md` | New file: full PGR protocol with per-phase audit criteria PGR-0 through PGR-5 |
| `references/phase-0-bootstrap.md` | New file: dedicated P0 reference |
| `references/phase-{1-5}-*.md` | Each has "Phase Exit: Trigger PGR-N" section at end |
| `templates/migration-state.yaml` | New `phase_gates` block with PGR_0–PGR_5 tracking fields |
| `templates/retrospective-checklist.yaml` | Corrected init comment; ships as 5th template |
| `references/schemas.md` | `phase_gates` block documented; updated "five persistence files" |
| `scripts/gap_report.py` | B-1, B-2, D-3, D-4 fixes |
| `scripts/scan_assets.py` | B-3, D-1, M-1 fixes |
| `README.md` | Doc-3 fix; version updated to 1.2; workspace shows 5 files; repo structure updated |
| `README.zh-CN.md` | Same updates in Chinese |

---

### Migration Path (v1.1 → v1.2)

**No breaking changes.**

- All existing migration YAML files remain valid
- Add `phase_gates` block to any existing `migration-state.yaml` (copy from updated template)
- Copy `retrospective-checklist.yaml` from `templates/` if not already present
- New sessions automatically use PGR; existing in-progress migrations can run PGR retroactively on completed phases

---

## [v1.1] — 2026-05-15

### Major Features

#### 🔄 Retrospective Integration into P4 & P5

The **TDD Retrospective Protocol** is now fully integrated into P4 (Translation) and P5 (Verification),
creating a continuous improvement loop that prevents recurring root causes across both phases.

**What Changed:**

- Every fix in P4 (compilation errors, `vet` failures) now **mandatorily triggers** the retrospective protocol
- Every fix in P5 (structural deviations, test failures) now **mandatorily triggers** the retrospective protocol
- Fixes are no longer isolated patches; they are now systemic improvements detected via **scope scanning**
- After each fix, the **full test suite must be re-run** (not just the failing test); new failures trigger independent retrospectives
- At phase-end, a **Checklist Summary** is generated identifying the most common root cause categories

**Nine Root Cause Categories:**
- `ecosystem_gap_unapplied` — known gap in ecosystem map not applied
- `semantic_contract_lost` — implicit contract of source type not preserved
- `invariant_not_transferred` — P3 inferred invariant missing in target
- `magic_number_decontextualized` — constant translated without context
- `control_flow_collapsed` — IPO steps merged or reordered
- `error_class_narrowed` — specific exception generalized to generic error
- `side_effect_dropped` — documented side effect not replicated
- `ipo_source_lines_wrong` — P3 analysis based on wrong line range
- `test_fixture_mismatch` — fixture format changed between source/target
- `other` — describe precisely if no category fits

### Updated Components

- `SKILL.md` — Global Anti-Cheating Policy enhanced; retrospective triggers added
- `references/phase-4-translation.md` — Retrospective Protocol section added
- `references/phase-5-verification.md` — TEST OUTPUT EVIDENCE requirement; full suite re-run mandate
- `references/tdd-retrospective.md` — Formally integrated (was pre-existing)
- `README.md` / `README.zh-CN.md` — v1.1 announcement

### Migration Path (v1.0 → v1.1)

No breaking changes. Existing migrations can add retrospectives on new fixes going forward.

---

## [v1.0] — 2026-05-01

**Initial stable release** with core six-phase pipeline:
P0 Bootstrap, P1 Asset Scan, P2 Ecosystem Map, P3 IPO Analysis (Evidence Obligation),
P4 Translation, P5 Verification, P6 Gap Report.

14 pre-built language pair modules, no-mock verification principle, persistent YAML state,
block-on-uncertainty protocol.

---

### Version Index

| Version | Tag | Date | Highlights |
|---------|-----|------|-----------|
| v1.2 | `v1.2` | 2026-05-15 | Phase Gate Review (PGR); 5th workspace template; phase-0-bootstrap.md; 11 quality fixes |
| v1.1 | `v1.1` | 2026-05-15 | TDD Retrospective Integration into P4/P5 |
| v1.0 | `v1.0` | 2026-05-01 | Initial stable release |


### Major Features

#### 🔄 Retrospective Integration into P4 & P5

The **TDD Retrospective Protocol** is now fully integrated into P4 (Translation) and P5 (Verification),
creating a continuous improvement loop that prevents recurring root causes across both phases.

**What Changed:**

- Every fix in P4 (compilation errors, `vet` failures) now **mandatorily triggers** the retrospective protocol
- Every fix in P5 (structural deviations, test failures) now **mandatorily triggers** the retrospective protocol
- Fixes are no longer isolated patches; they are now systemic improvements detected via **scope scanning**
- After each fix, the **full test suite must be re-run** (not just the failing test); new failures trigger independent retrospectives
- At phase-end, a **Checklist Summary** is generated identifying the most common root cause categories

**Core Design Principles:**

##### 1. Root Cause, Not Phenomenon

Traditional bug tracking records **what failed** (test_loop_tool_order FAILED, expected order [search,read,write]).
This captures a symptom, not a cause. The same underlying problem will manifest differently next time.

The retrospective captures **structural root causes** (e.g., `ecosystem_gap_unapplied`),
meaning:
- Next migration to the same target language can consult the checklist
- When translating any Python dict, check the "dict iteration order" rule BEFORE translation fails
- Errors are prevented, not just fixed

**Nine Root Cause Categories** (from `retrospective-checklist.yaml`):
- `ecosystem_gap_unapplied` — known gap in ecosystem map not applied
- `semantic_contract_lost` — implicit contract of source type not preserved
- `invariant_not_transferred` — P3 inferred invariant missing in target
- `magic_number_decontextualized` — constant translated without context
- `control_flow_collapsed` — IPO steps merged or reordered
- `error_class_narrowed` — specific exception generalized to generic error
- `side_effect_dropped` — documented side effect not replicated
- `ipo_source_lines_wrong` — P3 analysis based on wrong line range
- `test_fixture_mismatch` — fixture format changed between source/target
- `other` — describe precisely if no category fits

##### 2. Scope Scan Must Be Defined BEFORE Execution

The methodology enforces an anti-cheating rule: **write the search pattern before scanning**.

This prevents the common LLM failure of:
1. Scanning the entire codebase
2. Seeing results
3. Retroactively defining "the scope that matches our findings"

Under this protocol:
- Root cause is identified → search pattern written (with `scope_scan_query`)
- Pattern executed → results classified as FIXED, OK, or DEFERRED
- Each finding gets a written justification, not a silent assumption

**Example:**
```
Root cause: Python dict with insertion-order-dependent iteration

Scope scan query (BEFORE scanning):
  grep -rn "map\[string\]" internal/ --include="*.go"
  THEN cross-reference each result with source dict iteration patterns

This query is written BEFORE execution and appears in the retrospective entry.
```

##### 3. Fix All Instances Consistently in One Pass

Once the scope is identified, all instances with the same root cause are fixed simultaneously
using the same fix strategy. This prevents:
- The same bug reappearing in a file you haven't looked at yet
- Maintenance inconsistency where different parts of the code handle the same issue differently

**Rule:** After a scope scan fix is complete, the full test suite runs. Any new failures trigger independent
retrospectives — they are not merged into the same entry.

##### 4. Self-Improving Ecosystem Mappings

The checklist entry `ecosystem_map_update_required` flag triggers automatic updates to `ecosystem-map.yaml` at phase-end.

Example flow:
1. P4: `dict` ordering bug discovered and fixed
2. Retrospective identifies `ecosystem_gap_unapplied` for "dict[K,V]"
3. Checklist entry sets `ecosystem_map_update_required: true`
4. P4 end: ecosystem map updated with stronger guidance on dict ordering
5. **Next migration to the same language pair benefits from this update** — the same class of error is harder to commit

This means **each migration improves the language pair modules for subsequent migrations.**

---

### Updated Components

#### SKILL.md

- **Global Anti-Cheating Policy**: Enhanced with mandatory retrospective triggers in P4 and P5
- **Evidence Requirements table**: Now explicitly lists retrospective artifacts as required evidence for fixes
- **Pipeline orchestration**: Clarifies retrospective triggers at compile/vet errors and test failures

#### phase-4-translation.md

- New section: "**Regression Strategy + TDD Retrospective Protocol**"
- Integration point: every compilation/vet error now triggers `RCA → scope_scan → fix → test`
- Entry guard strengthened: samples 10 IPO entries to verify P3 quality before translation begins

#### phase-5-verification.md

- New section: "**Regression Strategy + TDD Retrospective Protocol**"
- Behavioral test failures and structural deviations now mandatory trigger retrospectives
- New requirement: After each retrospective fix, **full test suite must be re-run** (not just failing test)
- New output format: **Test Output Evidence** — prevents claims of "tests pass" without actual output

#### README.md & README.zh-CN.md

- New "**Retrospective Integration (v1.1)**" section in Core Innovations
- Link to `CHANGELOG.md` for detailed feature explanations
- Version notice: "Now at v1.1 with integrated TDD retrospectives"

---

### Files Added

- `CHANGELOG.md` — this file
- (retrospective-checklist.yaml and tdd-retrospective.md were already present; now formally integrated)

---

### Impact Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Bug response** | Fix the bug, move on | Fix → RCA → scope scan → consistent fix across codebase |
| **Reusability** | Each migration isolated | Checklist exported → improves next migration of same pair |
| **Traceability** | Error logs | Structured retrospective entries with root cause categories |
| **Prevention** | Reactive | Proactive — checklist rules prevent errors in future translations |
| **Ecosystem map** | Static, pre-built | Auto-updated from migration experience |

---

### Migration Path (v1.0 → v1.1)

**No breaking changes.**

- Existing v1.0 migrations can continue by simply running retrospectives on any new fixes
- Existing retrospective-checklist.yaml entries from v1.0 remain valid
- New sessions should use the v1.1 SKILL.md for full retrospective integration

---

## [v1.0] — 2026-05-01

**Initial stable release** with core six-phase pipeline:

- P0: Bootstrap
- P1: Asset Scan
- P2: Ecosystem Map
- P3: IPO Analysis (with Evidence Obligation)
- P4: Translation (basic)
- P5: Verification (basic)
- P6: Gap Report

14 pre-built language pair modules, no-mock verification principle, persistent YAML state,
block-on-uncertainty protocol.

---

### Tags & Versioning

- `v1.0` — stable baseline, core methodology without retrospective integration
- `v1.1` — adds retrospective protocol to P4/P5, checklist summary, ecosystem map auto-update

# Changelog

All notable changes to the lang-migration skill are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

# Phase 3: IPO Analysis

**Goal**: Document every callable unit in the source project using the IPO framework
(Input → Process → Output). This registry becomes the specification that Phase 4 translates from.

The IPO registry is the single source of truth for "what the source code does".
Phase 4 must not read the source code directly — it must translate from the IPO registry.
This separation ensures that structural equivalence is maintained, not incidentally achieved.

---

## ⛔ ABSOLUTE PROHIBITION: No Batch Script Generation

**The following is strictly forbidden and constitutes task fraud:**

- Using any script, loop, or template to batch-generate content fields in `ipo-registry.yaml`
- Copying the same `process.steps`, `purpose`, or `notes` text across multiple functions
- Filling `magic_numbers`, `inferred_invariants`, or `side_effects` without reading the actual source
- Marking any function `translation_status: DONE` in P3 (P3 only sets up registry; translation is P4)

**Scripts are ONLY permitted for generating the empty skeleton** (id, source_file, signature, source_lines).
Every content field — steps, magic_numbers, invariants, side_effects, calls, outputs — MUST be
filled by the AI after physically reading the source file for that specific function.

The AI must treat each function as a unique, isolated analysis task.

---

## Anti-Cheating Protocol: Mandatory READ_EVIDENCE

Every IPO entry must be preceded by a `READ_EVIDENCE` block in the AI's response.
This block contains artifacts that can ONLY be produced by actually reading the source.

**Before filling any IPO entry, output this in the response (not stored in YAML):**

```
READ_EVIDENCE for <function_id>:
  file_read: "<source_file>:<start_line>-<end_line>"
  first_statement: "<exact text of the first executable line in the function body>"
  last_statement:  "<exact text of the last executable line>"
  literal_count:   <number of numeric/string literals in the body>
  call_count:      <number of distinct function/method calls made>
  branch_count:    <number of if/elif/else/for/while/try/except branches>
```

If the AI cannot produce this block with accurate values, it has not read the file.
**Do not proceed to fill the IPO entry without outputting READ_EVIDENCE first.**

This acts as a reading receipt. A fabricated block will produce wrong line numbers,
wrong literal counts, or wrong statement text — detectable during P5 verification.

---

## Anti-Cheating Protocol: Mandatory BEHAVIOR_PROOF

After filling each IPO entry, the AI must output a `BEHAVIOR_PROOF` block:

```
BEHAVIOR_PROOF for <function_id>:
  happy_path:   "Given <specific concrete input>, returns/does <specific concrete output>"
  edge_case_1:  "Given <boundary input>, the function <raises X / returns Y / does Z>"
  edge_case_2:  "Given <another boundary>, <specific behavior>"
  would_fail_if: "<specific condition that violates an inferred invariant>"
```

Values must be SPECIFIC and CONCRETE — no generic statements.

❌ BAD (proves nothing — could be fabricated):
```
happy_path: "Given valid input, returns the expected result"
```

✅ GOOD (proves understanding — cannot be fabricated without reading):
```
happy_path: "Given data=[0.3, 0.3, 0.4] and base=2, returns 1.5710 (Shannon entropy in bits)"
edge_case_1: "Given data=[0.0, 1.0], filters 0.0 (below epsilon=1e-10), returns 0.0"
would_fail_if: "sum(data) >> 1.0 — inferred invariant violated, mathematically wrong output"
```

If the AI cannot write specific concrete values, it has not understood the function.
Block and re-read before continuing.

---

## Entry Criteria

- `phases.P2_ecosystem_map: DONE`
- `ecosystem-map.yaml` has no entries with `status: BLOCKED`

## Exit Criteria

- Every function in every `translate`-strategy source file has an entry in `ipo-registry.yaml`
- Every step has `source_lines` populated (not empty)
- Every magic number has `source_line` populated (not 0)
- Every inferred invariant has `[inferred from: ...]` evidence
- Self-verification report passed (see below)
- `phases.P3_ipo_analysis: DONE`, `phases.P4_translation: IN_PROGRESS`

---

## Execution Protocol: One Function at a Time

**Maximum: 5 functions per AI response.** No exceptions.

For each function, execute this exact sequence — no steps skipped, no order changed:

```
Step A: Read the source file for this specific function
Step B: Output READ_EVIDENCE block in response
Step C: Fill IPO entry fields (steps, magic_numbers, invariants, side_effects, calls, outputs)
Step D: Output BEHAVIOR_PROOF block in response
Step E: Write updated entry to ipo-registry.yaml
Step F: Move to the next function
```

Steps B and D are not optional. They are the primary mechanism preventing task fraud.

---

## IPO Documentation Field Rules

### process.steps — source_lines is MANDATORY

Every step must include the line range that implements it:

```yaml
steps:
  - step: 1
    desc: "Filter probabilities below epsilon to avoid log(0)"
    source_lines: "45-47"        # MANDATORY — leave empty = task fraud
    magic_numbers:
      - value: 1e-10
        source_line: 46          # MANDATORY — exact line of the literal
        type: threshold
        purpose: "epsilon floor: probabilities below this treated as zero"
        origin: inferred_from_context
```

### magic_numbers — source_line is MANDATORY

For EVERY numeric or string literal (except 0, 1, -1 as loop increments):

```yaml
magic_numbers:
  - value: 1e-10
    source_line: 46           # mandatory — exact line number
    type: threshold
    purpose: "specific purpose — not 'a threshold value'"
    origin: inferred_from_context
```

`origin: unknown` = automatic BLOCK. Do not continue to next function until resolved.

### inferred_invariants — evidence bracket is MANDATORY

```yaml
inferred_invariants:
  - "caller guarantees sum(data) ≈ 1.0 [inferred from: no normalization in body + test fixtures always sum to 1.0]"
  - "input list non-empty [inferred from: line 43 divides by len(data) with no guard]"
```

The `[inferred from: ...]` bracket is mandatory. It proves the invariant was observed, not invented.

### side_effects — line references are MANDATORY

```yaml
side_effects:
  - "writes to file: {path_param}/output.csv [line 67]"
  - "mutates: self.cache (dict) [line 54]"
  - "reads env var: DATABASE_URL [line 23]"
```

### calls — must be populated by scanning function body

An empty `calls: []` is valid only for confirmed leaf functions.
Wrong `calls` list = broken topological order in P4 = structural errors downstream.

---

## Context Sources (Priority Order)

Before analyzing any function:

1. **The function itself** — code, inline comments (produces READ_EVIDENCE)
2. **Docstring / JSDoc / godoc** — formal documentation
3. **All files with `p3_required: true`** — algorithm notes, design documents
4. **Callers of this function** — what do they pass in?
5. **Test files that exercise this function** — reveal edge cases and expected behavior
6. **Git commit messages** (if accessible) — explain why the code is shaped this way

Never analyze a function in isolation.

---

## Execution Order

Topological sort by `calls` graph — leaf functions first, callers after callees.
This ensures that when documenting a caller, all callees are already understood.

---

## P3 Self-Verification Protocol

**Before marking P3 DONE**, the AI must run and report all three checks:

### Check 1: source_lines Coverage Scan

Scan every entry in ipo-registry.yaml:
- Count entries where ANY step has empty `source_lines`
- Count magic_numbers where `source_line` is 0 or empty

```
CHECK 1 RESULT:
  total_functions: <N>
  steps_missing_source_lines: <X>   ← must be 0
  magic_numbers_missing_source_line: <Y>   ← must be 0
  action: <re-analyzed X functions / none required>
```

### Check 2: Invariant Evidence Scan

Scan every `inferred_invariants` entry:
- Count entries missing `[inferred from: ...]` bracket

```
CHECK 2 RESULT:
  invariants_missing_evidence: <X>   ← must be 0
  action: <re-analyzed X functions / none required>
```

### Check 3: Spot-Check Recall Test

Randomly select 5 functions. Without re-reading source, write BEHAVIOR_PROOF for each from memory.
If any answer is vague/generic, those functions must be re-analyzed.

```
CHECK 3 RESULT:
  spot_check_functions: [fn1, fn2, fn3, fn4, fn5]
  fn1_happy_path: "<specific concrete value>"
  fn2_happy_path: "<specific concrete value>"
  fn3_happy_path: "<specific concrete value>"
  fn4_happy_path: "<specific concrete value>"
  fn5_happy_path: "<specific concrete value>"
  spot_check_result: PASS / FAIL
  action: <re-analyzed X functions / none required>
```

**All three checks must pass before `phases.P3_ipo_analysis` is set to DONE.**
The self-verification report must appear in the AI's response — not silently in YAML.

---

## Quality Checklist Before Exiting P3

- [ ] Every function has an IPO entry
- [ ] Every step has non-empty `source_lines`
- [ ] Every magic number has non-zero `source_line`
- [ ] No `origin: unknown` without a blocking note
- [ ] Every `inferred_invariant` has `[inferred from: ...]`
- [ ] Every side_effect has a line reference
- [ ] `calls` graph populated (enables P4 topological ordering)
- [ ] `non_deterministic: true` entries have `non_determinism_source`
- [ ] Self-verification CHECK 1: PASS
- [ ] Self-verification CHECK 2: PASS
- [ ] Self-verification CHECK 3: PASS

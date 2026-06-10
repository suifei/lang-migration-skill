# AST Bridge Protocol (tree-sitter)

**Goal**: Replace probabilistic LLM reading with machine-generated ground truth for all
*structural* facts, and bootstrap P4 with mechanically generated draft code.

The bridge uses [tree-sitter](https://tree-sitter.github.io/tree-sitter/) — incremental
parsers with grammars for every language this skill supports. The AI writes
project-specific scripts that call tree-sitter; the skill does not ship a universal
transpiler because node types differ per grammar.

**Two stages, two integration points:**

| Stage | Phase | Artifact | Status |
|---|---|---|---|
| Stage 1: AST Index | P3 pre-pass | `migration_workspace/ast-index.yaml` | **REQUIRED in full_mode** |
| Stage 2: AST Skeleton Transform | P4 bootstrap | Draft target files with `TODO(migrate)` markers | **RECOMMENDED in full_mode** |

In **editor_mode** (no script execution): skip both stages; fall back to the manual
protocols in `phase-3-ipo-analysis.md` and `phase-4-translation.md`. Record the skip in
`migration-state.yaml` `decisions_log` with reason `editor_mode: no script execution`.

---

## Division of Labor — The Core Principle

```
MACHINE (tree-sitter script)          LLM (IPO-driven analysis)
─────────────────────────────         ─────────────────────────────
function boundaries + line numbers    purpose, behavior, edge cases
branch counts                         step descriptions (what each branch MEANS)
call graph (who calls whom)           invariants + evidence
literal extraction + line numbers     magic number PURPOSE and origin
comment/docstring text + location     semantic translation decisions
signature shapes                      type mapping beyond core table
control-flow shell generation         error model conversion
TODO marker placement                 ecosystem API mapping
```

**⛔ The script must NEVER attempt semantic translation.** Error-model conversion
(exceptions → error returns), ecosystem API mapping (numpy → gonum), and type inference
beyond the lang-pair core type table stay LLM + IPO driven. A script that tries to be
smart produces silently wrong code that *looks* translated — the worst failure mode
this skill exists to prevent.

---

## Stage 1: AST Index (P3 Pre-Pass)

### Step 1.1: Write the extraction script

The AI writes a project-specific script (Python with `tree-sitter` bindings, or Node.js
with `tree-sitter` npm packages) at `migration_workspace/scripts/ast_extract.<py|js>`.

Grammar packages for supported source languages:

| Source language | Python binding | Node package |
|---|---|---|
| Python | `tree-sitter-python` | `tree-sitter-python` |
| Go | `tree-sitter-go` | `tree-sitter-go` |
| Rust | `tree-sitter-rust` | `tree-sitter-rust` |
| TypeScript/JS | `tree-sitter-typescript` / `tree-sitter-javascript` | same |
| C | `tree-sitter-c` | `tree-sitter-c` |
| C++ | `tree-sitter-cpp` | `tree-sitter-cpp` |
| Zig | `tree-sitter-zig` | `tree-sitter-zig` |

The script must extract, for every function/method in every `translate`-strategy file:

| Field | Source AST nodes (Python grammar example) |
|---|---|
| `id` | `<file_stem>::<class>.<name>` or `<file_stem>::<name>` |
| `file`, `start_line`, `end_line` | `function_definition` node range |
| `signature` | `parameters` node text + return annotation |
| `parent_class` | enclosing `class_definition` name (empty for free functions) |
| `branch_count` | count of `if_statement`, `elif_clause`, `else_clause`, `for_statement`, `while_statement`, `try_statement`, `except_clause`, `match_statement`, `case_clause` nodes in body |
| `call_sites` | all `call` node function names in body (deduplicated, with line numbers) |
| `literals` | all `integer`, `float`, `string` nodes in body with line numbers (excluding docstring) |
| `comments` | all `comment` nodes + docstring with line numbers and text |
| `decorators` | decorator names (affect translation strategy) |

### Step 1.2: Validate the script before trusting it

**⛔ A buggy extraction script poisons everything downstream.** Before running on the
full project:

```
AST SCRIPT VALIDATION:
  validation_file: "<one source file, manually chosen, ≥3 functions>"
  For 2 functions in that file:
    manual_branch_count:  <counted by reading the source>
    script_branch_count:  <from script output>
    manual_call_sites:    [<read from source>]
    script_call_sites:    [<from script output>]
    match: YES / NO
  If NO: fix the script, re-validate. Do not run on full project until 2/2 match.
```

This validation block must appear in the AI's response.

### Step 1.3: Run and generate ast-index.yaml

```bash
python migration_workspace/scripts/ast_extract.py \
  --source <source_dir> \
  --files-from migration_workspace/asset-inventory.yaml \
  --output migration_workspace/ast-index.yaml
```

`ast-index.yaml` is a **derived artifact** — regenerable at any time from source. It is
not one of the five persistence files; never hand-edit it. If source changes, regenerate.

### Step 1.4: Integration with P3

Once `ast-index.yaml` exists:

1. **Execution Order**: the topological sort uses `call_sites` from the index — the
   shallow-grep Pre-Step in `phase-3-ipo-analysis.md` is replaced by the index.
2. **READ_EVIDENCE cross-check**: the AI still reads every function body (semantic
   understanding cannot be mechanized), but the structural fields of READ_EVIDENCE
   (`file_read` range, `literal_count`, `call_count`, `branch_count`) MUST match the
   index. A mismatch means either the script or the AI is wrong — resolve before
   filling the IPO entry. `first_statement` / `last_statement` remain manual-read
   proof that the body was actually read.
3. **magic_numbers completeness**: every literal in the index entry must either appear
   in the IPO entry's `magic_numbers` or be explicitly exempt (0, 1, -1 as loop
   increments; log message strings). Unaccounted literals = incomplete analysis.
4. **steps_count ≥ branch_count**: PGR-3-G now compares against `ast-index.yaml`
   `branch_count` (mechanical, exact) instead of re-counting by reading.
5. **PGR-3-A function completeness**: every function in the index must have an IPO
   entry or `translation_status: SKIP` — mechanical diff instead of re-extraction.

---

## Stage 2: AST Skeleton Transform (P4 Bootstrap)

### Step 2.1: Write the transform script

The AI writes `migration_workspace/scripts/ast_transform.<py|js>`: walks the source AST
and emits one draft target-language file per source file.

**What the script generates per function:**

1. **Signature**: mapped via the lang-pair core type table ONLY (e.g., `str → string`,
   `list[T] → []T` for Python→Go). Types not in the core table → emit the target
   language's placeholder (`any` / `interface{}` / `auto`) **plus a TODO marker**.
2. **Control-flow shell**: every `if/elif/else/for/while/try` branch becomes the
   corresponding target-language branch — empty-bodied but present. This mechanically
   guarantees `branch_count` parity (the B2/Trap-2 failure class becomes impossible
   to introduce silently).
3. **Statement TODO markers**: every statement the script cannot mechanically map
   becomes a comment preserving the original text and location:
   ```go
   // TODO(migrate): summary = f"... | {unread}条用户未读消息, ..." [source: conductor.py:278]
   ```
4. **Comments migrated**: every source comment and docstring is emitted as a
   target-language comment at the structurally corresponding position.
5. **File header**:
   ```go
   // AST-GENERATED DRAFT — DO NOT SHIP.
   // Every function below must be completed per its ipo-registry.yaml entry.
   // Generated from <source_file> by ast_transform at <timestamp>.
   ```

**What the script must NOT generate** (⛔ guardrails):

- No error-model conversion (no guessing which calls return `(T, error)`)
- No ecosystem API calls (no `numpy.sum → gonum` guesses — emit TODO instead)
- No removal or merging of branches, even "obviously dead" ones
- No `translation_status` changes in any YAML

A draft that fails to compile is **expected and acceptable**. The draft is scaffolding,
not a translation.

### Step 2.2: Record the mapping in ipo-registry.yaml

For each function the transform emits, add an `ast_bridge` block to its IPO entry:

```yaml
ast_bridge:
  skeleton_generated: true
  skeleton_file: "internal/loop/loop.go"
  skeleton_lines: "34-89"            # where the draft function landed
  todo_count_initial: 12             # TODO(migrate) markers emitted for this function
  todo_count_remaining: 12           # decremented as P4 fills them; must reach 0
```

This gives the next LLM round (or next session) an exact work queue:
`grep -rn "TODO(migrate)" <target_dir>` lists every unfinished statement with its
source file:line provenance.

### Step 2.3: P4 becomes "fill the TODOs per IPO contract"

The standard P4 protocol applies unchanged, with one reframing: instead of writing each
function from scratch, the AI:

1. Opens the skeleton function
2. Reads the IPO entry (still the contract — the skeleton is NOT the spec)
3. Replaces each `TODO(migrate)` with the correct target code, consulting:
   - the IPO step that covers that source line
   - the ecosystem map for any API calls
   - the lang-pair module for patterns (error handling, class mapping)
4. Decrements `todo_count_remaining`
5. When the function compiles and has zero TODOs: standard P4 completion
   (`target_lines`, retrospective on any fix, etc.)

**⛔ Filling a TODO with code that contradicts the IPO entry is a translation error**,
even if it matches the raw source text — the IPO entry may encode invariants and
ecosystem compensations the raw text doesn't show.

### Step 2.4: Completion gate

P4 cannot exit while any `TODO(migrate)` marker remains:

```bash
grep -rn "TODO(migrate)" <target_dir> | wc -l   # must be 0
```

This is enforced by PGR-4-F (see `phase-gate-review.md`). Markers must be *resolved*,
never deleted-without-implementation. Deleting a marker without writing the
corresponding code is task fraud (detectable: the IPO step has no target_lines coverage).

---

## Failure Modes and Responses

| Failure | Response |
|---|---|
| No tree-sitter grammar for source language | Skip AST Bridge entirely; document in decisions_log; use manual protocols |
| Grammar exists but script crashes on some files | Index what parses; list failed files in ast-index.yaml `parse_failures`; analyze those manually |
| Script branch_count disagrees with manual count during validation | Trust neither — re-read grammar node types; common cause: `elif` chains counted as nested vs flat |
| Transform produces garbage for a construct (e.g., Python decorators) | Narrow the transform: emit whole-function TODO for that construct class; never ship half-mechanical output |
| Source changes mid-migration | Regenerate ast-index.yaml; diff against old; re-open IPO entries for changed functions |

---

## Why This Strengthens (Not Replaces) the Methodology

The historical failure cases this skill encodes (B1–B5, conductor) were all *semantic*:
dropped side effects, collapsed branch meanings, implicit capability assumptions. AST
transformation alone would have prevented exactly one of them (B2 branch collapse) and
silently shipped the rest — they all parse fine.

The bridge therefore automates what machines verify well (structure) to free LLM
attention for what only it can do (semantics) — and turns the anti-cheating checks
from "LLM re-reads and re-counts" into "mechanical diff against machine truth."

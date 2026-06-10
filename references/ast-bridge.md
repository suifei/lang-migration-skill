# AST Bridge Protocol (tree-sitter)

**Goal**: Replace probabilistic LLM reading with machine-generated ground truth for all
*structural* facts, and bootstrap P4 with mechanically generated draft code.

The bridge uses [tree-sitter](https://tree-sitter.github.io/tree-sitter/).
**The skill SHIPS the toolchain**: `scripts/ast_bridge.py` — a single-entrypoint CLI the
AI calls directly. Do NOT write your own extraction script unless the toolchain reports
your language as unsupported (see Fallback section).

**Two stages, two integration points:**

| Stage | Phase | Command | Artifact | Status |
|---|---|---|---|---|
| Stage 1: AST Index | P3 pre-pass | `ast_bridge.py index` | `migration_workspace/ast-index.yaml` | **REQUIRED in full_mode** |
| Stage 2: AST Skeleton Transform | P4 bootstrap | `ast_bridge.py skeleton` | Draft target files + `skeleton-map.yaml` | **RECOMMENDED in full_mode** |

In **editor_mode** (no command execution): skip both stages; fall back to the manual
protocols in `phase-3-ipo-analysis.md` and `phase-4-translation.md`. Record the skip in
`migration-state.yaml` `decisions_log` with reason `editor_mode: no script execution`.
Note: if your editor agent CAN run terminal commands (e.g., Cursor agent mode), treat
this as full_mode for the AST Bridge — the toolchain is plain CLI.

---

## Toolchain Reference (`scripts/ast_bridge.py`)

Designed LLM-first: no interactive prompts, deterministic YAML output, actionable errors.
Exit codes: `0` = clean, `1` = findings/work remaining, `2` = usage/environment error.

| Command | Purpose | When |
|---|---|---|
| `doctor --langs <src>,<tgt> [--install]` | Check/install tree-sitter deps for the pair | P0 bootstrap, before P3 |
| `index --source <dir> --lang <src> [--files-from asset-inventory.yaml] --output ast-index.yaml` | Stage 1: extract machine truth | P3 entry |
| `verify --index ast-index.yaml --registry ipo-registry.yaml [--strict-literals]` | Mechanical PGR-3-A/G (+literal coverage) checks | inside PGR-3, any time during P3 |
| `skeleton --index ast-index.yaml --target-dir <dir> --map-output skeleton-map.yaml` | Stage 2: emit drafts + mapping | P4 entry |
| `todos --target-dir <dir> [--verbose]` | Count remaining `TODO(migrate)` markers | PGR-4-F gate, P4 progress |

### Installation (tree-sitter)

The skill does NOT vendor compiled grammars (platform-specific binaries). Grammars are
installed on demand as precompiled wheels — no C compiler needed:

```bash
python3 skills/lang-migration/scripts/ast_bridge.py doctor --langs python,go --install
# equivalent to: pip install tree-sitter pyyaml tree-sitter-python tree-sitter-go
```

Run `doctor` once at P0 bootstrap. If pip is blocked by network policy, `doctor` exits 1
with the exact command for the human to run; if installation is impossible, fall back to
the manual protocols and record the decision.

### How each environment calls the toolchain

| Environment | Invocation |
|---|---|
| Claude Code / Codex CLI / OpenCode | Run the commands above directly via the shell tool |
| Cursor (agent mode with terminal) | Run directly; treat as full_mode |
| Cursor / Copilot (edit-only) | Print the exact commands and ask the human to run them; parse the YAML outputs they paste/commit |

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

### Step 1.1: Run the shipped extractor

```bash
python3 skills/lang-migration/scripts/ast_bridge.py index \
  --source <source_dir> \
  --lang <source_lang> \
  --files-from migration_workspace/asset-inventory.yaml \
  --output migration_workspace/ast-index.yaml
```

The index contains, for every function/method in every `translate`-strategy file:
`id`, `file`, `start_line`/`end_line`, `signature`, `parent_class`, `branch_count`,
`call_sites` (with lines), `literals` (with lines, docstrings excluded), `comments`
(docstring flagged), `decorators`. Full schema: `references/schemas.md`.

Language support tiers (run `doctor` to confirm):
- **full** (index + skeleton source): python, go
- **index** (index only): rust, javascript, typescript, c, cpp
- anything else → toolchain reports unsupported → use the Fallback section

### Step 1.2: Spot-validate the output

The toolchain is shipped and tested, but grammars evolve and projects hit edge cases.
Before trusting the full index:

```
AST INDEX VALIDATION:
  validation_file: "<one source file, manually chosen, ≥3 functions>"
  For 2 functions in that file:
    manual_branch_count:  <counted by reading the source>
    index_branch_count:   <from ast-index.yaml>
    manual_call_sites:    [<read from source>]
    index_call_sites:     [<from ast-index.yaml>]
    match: YES / NO
  If NO: report the discrepancy as a toolchain bug; analyze the affected
  construct class manually; do not silently trust either count.
```

This validation block must appear in the AI's response. Also check
`meta.parse_failures` — any file listed there must be analyzed manually.

`ast-index.yaml` is a **derived artifact** — regenerable at any time from source. It is
not one of the five persistence files; never hand-edit it. If source changes, regenerate.

### Step 1.3: Integration with P3

Once `ast-index.yaml` exists, the mechanical checks become one command, runnable at any
point during P3 and mandatory inside PGR-3:

```bash
python3 skills/lang-migration/scripts/ast_bridge.py verify \
  --index migration_workspace/ast-index.yaml \
  --registry migration_workspace/ipo-registry.yaml \
  --strict-literals
# exit 0 = clean; exit 1 = findings printed in PGR format (PGR-3-A / PGR-3-G / PGR-3-C*)
```

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

### Step 2.1: Run the shipped skeleton generator

```bash
python3 skills/lang-migration/scripts/ast_bridge.py skeleton \
  --index migration_workspace/ast-index.yaml \
  --source-lang python --target-lang go \
  --target-dir <target_dir> \
  --map-output migration_workspace/skeleton-map.yaml
```

The toolchain ships skeleton generation for the **python→go** pair (the validated pair).
For other pairs it exits with code 2 and a message — use the Fallback section or
translate manually per phase-4.

**What the generator emits per function:**

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

**What the generator must NOT emit** (⛔ guardrails — these are built into the shipped
toolchain and apply equally to any fallback implementation):

- No error-model conversion (Python `try` blocks become a single TODO block — converting
  to `(T, error)` returns is LLM work)
- No ecosystem API calls (no `numpy.sum → gonum` guesses — emit TODO instead)
- No removal or merging of branches, even "obviously dead" ones
- No `translation_status` changes in any YAML

A draft that fails to compile is **expected and acceptable**. The draft is scaffolding,
not a translation.

### Step 2.2: Merge skeleton-map.yaml into ipo-registry.yaml

The generator writes `migration_workspace/skeleton-map.yaml` — one entry per function
with `skeleton_file`, `skeleton_lines`, `todo_count_initial/remaining`. The AI merges
each entry into the corresponding IPO entry as its `ast_bridge` block:

```yaml
ast_bridge:
  skeleton_generated: true
  skeleton_file: "internal/loop/loop.go"
  skeleton_lines: "34-89"            # where the draft function landed
  todo_count_initial: 12             # TODO(migrate) markers emitted for this function
  todo_count_remaining: 12           # decremented as P4 fills them; must reach 0
```

This gives the next LLM round (or next session) an exact work queue:

```bash
python3 skills/lang-migration/scripts/ast_bridge.py todos --target-dir <target_dir> --verbose
```

lists every unfinished statement with its source file:line provenance.

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
python3 skills/lang-migration/scripts/ast_bridge.py todos --target-dir <target_dir>
# exit 0 = zero markers (gate passes); exit 1 = markers remain (listed per file)
```

This is enforced by PGR-4-F (see `phase-gate-review.md`). Markers must be *resolved*,
never deleted-without-implementation. Deleting a marker without writing the
corresponding code is task fraud (detectable: the IPO step has no target_lines coverage).

---

## Fallback: Unsupported Language or Pair

When `doctor` reports a language as unsupported, or `skeleton` rejects the pair:

1. **Index fallback**: write a project-specific extraction script that produces YAML
   matching the `ast-index.yaml` schema in `references/schemas.md` exactly (so `verify`
   still works against it). Validate it with the AST INDEX VALIDATION block on 2
   functions before a full run — for a hand-written script this validation is mandatory,
   not optional.
2. **Skeleton fallback**: either translate manually per phase-4 (always safe), or write
   a transform honoring every ⛔ guardrail above and emitting the same `TODO(migrate)`
   marker format (so `todos` and PGR-4-F still work).
3. Prefer extending `scripts/ast_bridge.py` (add a language config block to `CONFIGS`)
   over writing a separate script — then propose the config upstream as a skill
   improvement.

---

## Failure Modes and Responses

| Failure | Response |
|---|---|
| `doctor` reports no grammar for source language | Use the Fallback section, or skip AST Bridge; document in decisions_log |
| pip install blocked by network policy | `doctor` prints the exact command for the human; if impossible, manual protocols |
| Grammar exists but some files fail to parse | Index what parses; failed files listed in `meta.parse_failures`; analyze those manually |
| Index branch_count disagrees with manual count during validation | Trust neither — report as toolchain bug; analyze that construct class manually |
| Skeleton output is garbage for a construct (e.g., decorators) | The construct arrives as a TODO marker anyway — resolve it manually per the IPO entry |
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

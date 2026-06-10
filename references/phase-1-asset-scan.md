# Phase 1: Asset Scan

**Goal**: Produce a complete `asset-inventory.yaml` where every file in the source project
has an entry with a migration strategy. Zero files omitted.

---

## Entry Criteria

- `migration-state.yaml` exists
- `phases.P0_bootstrap: DONE`
- `phases.P1_asset_scan: IN_PROGRESS`

## Exit Criteria

- Every file in the source project has an entry in `asset-inventory.yaml`
- Every entry has `status: DONE` (or `BLOCKED` — which requires human resolution first)
- `migration-state.yaml` stats block is updated
- `phases.P1_asset_scan: DONE`, `phases.P2_ecosystem_map: IN_PROGRESS`

---

## Execution Steps

### Step 1: Generate File List

**In full_mode** (Claude Code / OpenCode with bash):
```bash
cd <source_dir>
find . -type f | sort > /tmp/source_file_list.txt
wc -l /tmp/source_file_list.txt
```

Also run the scan script if available:
```bash
python migration_workspace/../skills/lang-migration/scripts/scan_assets.py \
  --source <source_dir> \
  --output migration_workspace/asset-inventory.yaml
```

**In editor_mode** (Cursor / Copilot):
- Read the directory tree by exploring the file system
- Manually enumerate all files
- Do not guess — if you cannot see a directory, say so

### Step 2: Classify Each File

For each file, determine:
1. **type** — use the type table in `references/schemas.md`
2. **purpose** — read the file; write a one-line description of what it does
3. **migration_strategy** — apply the decision tree below
4. **p3_required** — true if this file contains algorithm descriptions, mathematical derivations, or explanations not present in the code

### Strategy Decision Tree

```
Is this a source code file (.py, .go, .c, etc.)?
  YES → translate

Is this a test code file (test_*, *_test.*, spec.*, etc.)?
  YES → translate (tests are first-class citizens; migrate them too)

Is this a test fixture / data file used by tests?
  YES → direct_use (copy as-is; test data must remain identical)

Is this a dependency manifest (requirements.txt, go.mod, Cargo.toml, package.json)?
  YES → adapt (recreate for target ecosystem using ecosystem-map)

Is this a build config (Makefile, CMakeLists, build.gradle, pyproject.toml)?
  YES → adapt (rebuild for target toolchain)

Is this a CI config (.github/workflows/, .gitlab-ci.yml, Jenkinsfile)?
  YES → adapt (update build commands, keep pipeline structure)

Is this a Dockerfile or docker-compose?
  YES → adapt (update base image and build commands)

Is this documentation or algorithm notes (README, docs/, *.md, *.rst, *.tex)?
  Does it contain algorithm detail, mathematical derivations, or design notes needed during P3?
    YES → reference_only; set p3_required: true
    NO  → preserve
  
Is this a binary asset (image, .npy, .pb, .pkl, compiled output)?
  YES → direct_use if it's input data; generated if it's build output

Is this a configuration file (.env, .yaml, .json config, .ini)?
  YES → direct_use (format-compatible) or adapt (if syntax must change)

Cannot determine purpose?
  → preserve; write what you observe in notes; DO NOT skip
```

### Step 3: Record Dependencies

For each `translate` or `adapt` file, read the imports/includes and list them in `depends_on_ecosystem`. These feed directly into P2.

```yaml
# Example
- path: "src/core/entropy.py"
  depends_on_ecosystem:
    - numpy
    - scipy.stats
    - collections
    - typing
```

### Step 3.5: Detect Directory-Load Patterns

Static import analysis (Step 3) only captures explicit `import`/`require` statements.
Some codebases — especially agents, CLIs, and data pipelines — load files by scanning
entire directories at runtime (e.g., `os.listdir("skills/")`, `glob("references/*.md")`).
These patterns create **implicit runtime dependencies** on every file in those directories,
but no single file appears in any import statement.

**Why this matters for migration**: if a source agent scans `skills/lang-migration/references/*.md`
at runtime to load documentation, every `*.md` file in that directory is a runtime dependency.
Without this step, those files would be classified as `reference_only` (never migrated) even
though the target agent also needs them present and loadable.

#### In full_mode (Claude Code / OpenCode with bash)

Run scan_assets with the `--dirload-report` flag:

```bash
python3 skills/lang-migration/scripts/scan_assets.py \
  --source <source_dir> \
  --output migration_workspace/asset-inventory.yaml \
  --dirload-report
```

The script automatically:
1. Scans all source code files for the following pattern families:
   - **Python**: `os.listdir`, `os.scandir`, `os.walk`, `glob.glob`, `glob.iglob`, `Path.glob`, `Path.rglob`, `Path.iterdir`, `importlib.resources.files`, `pkgutil.iter_modules`
   - **Go**: `os.ReadDir`, `filepath.WalkDir`, `filepath.Walk`, `filepath.Glob`, `ioutil.ReadDir`
   - **JavaScript/TypeScript**: `fs.readdirSync`, `fs.readdir`, `glob.sync`, `fast-glob.sync`
   - **Ruby**: `Dir.glob`, `Dir[]`
   - **Rust**: `fs::read_dir`, `glob`
2. Extracts the base directory from each call site (strips wildcard suffix from glob patterns)
3. Tags every file under detected directories with `runtime_dependency: true`
4. Upgrades strategy from `reference_only` or `preserve` → `direct_use` for tagged files
5. Writes a `dirload_summary` block in `asset-inventory.yaml` listing every detected directory
   and the code sites that reference it

#### In editor_mode (Cursor / Copilot — no bash)

Manually search for the following patterns across the source tree. For each match, identify
the directory being scanned and mark every file inside it as `runtime_dependency: true` with
strategy `direct_use`:

```
# Search for these terms in source code files:
os.listdir    os.scandir    os.walk
glob.glob     glob.iglob    rglob(     iterdir(
os.ReadDir    filepath.Walk filepath.Glob
fs.readdir    Dir.glob      fs::read_dir
```

For each match, record the loaded directory in the file's notes field:
```yaml
notes: "RUNTIME-DEPENDENCY: directory 'references/' is scanned at runtime by skills/loader.py:47"
runtime_dependency: true
runtime_dependency_dir: "references"
```

#### Strategy upgrade rules for runtime-loaded files

| Original strategy | File type | Action |
|---|---|---|
| `reference_only` | `*.md`, `*.rst`, `*.txt` docs | Upgrade to `direct_use`; target must include unchanged |
| `preserve` | `*.yaml`, `*.json`, `*.toml` data | Upgrade to `direct_use`; check if format must also be adapted |
| `reference_only` with `p3_required: true` | algorithm docs | Keep `p3_required: true`; strategy becomes `direct_use` (load + read during P3) |
| `translate` | source code in scanned dir | No change — already correct |

**Exception**: if the file is generated output (e.g., a lock file in a dist/ directory scanned by a cleanup script), keep `generated` — the directory scan is incidental, not a content dependency.

#### When to escalate to BLOCKED

Block (do not guess) when:
- The loaded path is a variable or interpolated expression (e.g., `os.listdir(self.skills_dir)`) — you cannot statically determine which directory; add a `BLOCKED` entry with `block_reason: "runtime path computed from variable; cannot determine which files are dependencies"`
- The directory exists but contains files of wildly mixed types (source code + docs + binaries together) — annotate each file individually before deciding

### Step 4: Set p3_required

Mark `p3_required: true` for:
- Files with algorithm descriptions (docs, comments files)
- Files with mathematical derivations
- Any file whose content is referenced in source code comments
- Project wiki exports, research notes, design documents

### Step 5: Update State

Two summary blocks must BOTH be updated and must be consistent with each other:

```yaml
# In migration-state.yaml — overall counts
stats:
  assets_total: <count>
  assets_done: <count>   # all DONE (not counting BLOCKED)
  assets_blocked: <count>
phases:
  P1_asset_scan: DONE
  P2_ecosystem_map: IN_PROGRESS
```

```yaml
# In asset-inventory.yaml — counts per strategy (verified by PGR-1-E)
by_strategy:
  translate: <count>
  adapt: <count>
  direct_use: <count>
  preserve: <count>
  reference_only: <count>
  generated: <count>
```

`stats.assets_total` must equal the sum of all `by_strategy` values.
`stats.assets_done` must equal the count of entries with `status: DONE` across all strategies.

---

## Blocking Rules

Block (do not skip) when:
- A file exists but cannot be read or accessed
- A file type is completely unrecognizable and the name gives no clues
- Two files appear to conflict in purpose (e.g., two different configs for the same tool)

Present the block using the standard blocking protocol from `SKILL.md`.

---

## Quality Checks Before Exiting P1

- [ ] File count in `asset-inventory.yaml` matches `find . -type f | wc -l`
- [ ] No file has `migration_strategy: ""` (empty)
- [ ] All test fixture files are `direct_use`
- [ ] All documentation files are `reference_only` or `preserve` (or `direct_use` if runtime-loaded)
- [ ] `depends_on_ecosystem` is populated for all `translate` files
- [ ] Step 3.5 was run: source code was scanned for directory-load patterns
- [ ] All `runtime_dependency: true` entries have been AI-reviewed to confirm `direct_use` is correct
- [ ] Any variable-path directory-load patterns that could not be statically resolved are BLOCKED

---

## Phase Exit: Trigger PGR-1

When you believe P1 is complete, do NOT mark it DONE yet.

Load `references/phase-gate-review.md` and run PGR-1 using the audit criteria defined there.
Only set `phases.P1_asset_scan: DONE` after PGR-1 passes with zero findings.

The PGR-1 loop will:
1. Verify every source file is in `asset-inventory.yaml` (including a fresh re-scan)
2. Verify every entry has a non-placeholder `purpose`
3. Verify every entry has a confirmed `migration_strategy`
4. Verify every entry has a valid `status`
5. Verify `by_strategy` counts match actual entry counts
6. Fix any findings autonomously and re-audit from scratch until zero findings remain

`phases.P1_asset_scan: DONE` is set by PGR-1 as its final action — never set it directly.

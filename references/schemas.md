# YAML Schemas Reference

Complete field definitions for all four persistence files.
Load this file when you need to validate or extend the YAML structures.

---

## migration-state.yaml

| Field | Type | Description |
|-------|------|-------------|
| `meta.source_lang` | string | Source programming language (lowercase) |
| `meta.target_lang` | string | Target programming language (lowercase) |
| `meta.source_dir` | string | Relative path from workspace root to source project |
| `meta.target_dir` | string | Relative path from workspace root to translated output |
| `meta.lang_pair_module` | string | Key used to load `references/lang-pairs/<key>.md` |
| `meta.source_version` | string | Git commit/tag of source; ensures reproducible baseline |
| `phases.*` | enum | `TODO \| IN_PROGRESS \| DONE` |
| `current_task.status` | enum | `TODO \| IN_PROGRESS \| DONE \| BLOCKED` |
| `current_task.block_reason` | string | Machine-readable summary of why task is blocked |
| `current_task.human_input_required` | string | Human-readable question to resolve block |
| `decisions_log` | list | Audit trail; append every human decision here |

---

## asset-inventory.yaml

### `type` values

| Value | Meaning |
|-------|---------|
| `source_code` | Compilable/interpretable source file |
| `test_code` | Test file (unit, integration, e2e) |
| `test_fixture` | Data file consumed by tests |
| `build_config` | Makefile, CMakeLists, build.gradle, pyproject.toml, etc. |
| `ci_config` | GitHub Actions, GitLab CI, Jenkinsfile, etc. |
| `documentation` | README, docs/, wiki, algorithm notes |
| `asset_binary` | Binary files (images, compiled artifacts, .npy, etc.) |
| `asset_text` | Non-code text assets (templates, SQL schemas, proto files) |
| `dependency_manifest` | requirements.txt, Cargo.toml, go.mod, package.json |
| `environment_config` | .env, .env.example, docker-compose.yml, Dockerfile |
| `script` | Shell scripts, utility scripts |
| `other` | Anything not covered above — always explain in `notes` |

### `migration_strategy` values

| Value | Action |
|-------|--------|
| `translate` | Rewrite in target language; creates new file at `target_path` |
| `adapt` | Keep general structure, rewrite language-specific parts (CI, build) |
| `direct_use` | Copy byte-for-byte; target code reads it as-is |
| `preserve` | Include in target project unchanged; role may be clarified later |
| `reference_only` | Not migrated; must be read during P3 (docs, algorithm notes) |
| `generated` | Target toolchain generates this automatically (lock files, etc.) |

---

## ecosystem-map.yaml

### `category` values

| Value | Examples |
|-------|---------|
| `type` | int, float64, numpy.float32, uint8 |
| `stdlib` | os.path, collections.OrderedDict, io.BytesIO |
| `third_party` | numpy.ndarray, requests.Session, sqlalchemy.Column |
| `idiom` | list comprehension, generator expression, decorator pattern |
| `runtime_behavior` | GIL, GC timing, dict iteration order, integer overflow |

### `precision_delta` values

- `none` — identical precision
- `narrower` — target type has less precision (document max acceptable error)
- `wider` — target type has more precision (generally safe, document anyway)
- `different_representation` — same bit width but different semantics (e.g., IEEE vs fixed-point)

---

## ipo-registry.yaml

### `magic_numbers.origin` values

| Value | Meaning |
|-------|---------|
| `documented` | Explained in comments, docstring, or referenced document |
| `inferred_from_context` | AI derived meaning from usage pattern; not stated explicitly |
| `unknown` | Cannot determine purpose; flag for human review |

### `side_effects` format

List strings describing each side effect:
```yaml
side_effects:
  - "writes to file: {path_param}/output.csv"
  - "mutates: self.cache (dict)"
  - "reads env var: DATABASE_URL"
  - "network: GET https://api.example.com/data"
```

### `inferred_invariants` format

Assumptions the code makes but does not assert:
```yaml
inferred_invariants:
  - "caller guarantees sum(data) ≈ 1.0 (not checked)"
  - "input list is non-empty (would divide by zero otherwise)"
  - "file at path is UTF-8 encoded (no encoding specified)"
```

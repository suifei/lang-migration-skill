#!/usr/bin/env python3
"""
scan_assets.py — Phase 1 asset scanner for lang-migration skill.

Usage:
    python scan_assets.py --source <source_dir> --output <path/to/asset-inventory.yaml>
    python scan_assets.py --source <source_dir> --output <path/to/asset-inventory.yaml> --dirload-report

Generates a starter asset-inventory.yaml by walking the source directory.
The AI agent then fills in `purpose`, `migration_strategy`, and other fields.

With --dirload-report: also detects directory-load patterns in source code and
annotates files under those directories with runtime_dependency: true. Files
that would otherwise be classified as reference_only are upgraded to direct_use
if they live under a directory that code scans at runtime.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml --break-system-packages")
    sys.exit(1)

# Maps file extension to likely asset type
EXTENSION_TYPE_MAP = {
    # Source code
    ".py": "source_code", ".go": "source_code", ".rs": "source_code",
    ".c": "source_code", ".cpp": "source_code", ".cc": "source_code",
    ".h": "source_code", ".hpp": "source_code",
    ".ts": "source_code", ".js": "source_code", ".jsx": "source_code", ".tsx": "source_code",
    ".zig": "source_code", ".rb": "source_code", ".java": "source_code",
    ".cs": "source_code", ".swift": "source_code", ".kt": "source_code",

    # Test fixtures / data
    ".npy": "test_fixture", ".npz": "test_fixture",
    ".csv": "test_fixture", ".tsv": "test_fixture",
    ".json": "asset_text",  # may be test fixture or config — AI to determine
    ".jsonl": "test_fixture",
    ".pkl": "test_fixture", ".pickle": "test_fixture",
    ".parquet": "test_fixture", ".arrow": "test_fixture",
    ".bin": "asset_binary", ".dat": "asset_binary",

    # Documentation
    ".md": "documentation", ".rst": "documentation",
    ".txt": "documentation", ".tex": "documentation",
    ".pdf": "documentation",

    # Build config
    "Makefile": "build_config", "CMakeLists.txt": "build_config",
    ".toml": "build_config",  # Cargo.toml, pyproject.toml — AI to refine
    ".gradle": "build_config", "build.gradle": "build_config",
    ".gradle.kts": "build_config",

    # Dependency manifests
    "requirements.txt": "dependency_manifest",
    "requirements-dev.txt": "dependency_manifest",
    "Pipfile": "dependency_manifest", "Pipfile.lock": "dependency_manifest",
    "poetry.lock": "dependency_manifest",
    "go.mod": "dependency_manifest", "go.sum": "dependency_manifest",
    "Cargo.lock": "dependency_manifest",
    "package.json": "dependency_manifest", "package-lock.json": "dependency_manifest",
    "yarn.lock": "dependency_manifest", "bun.lockb": "dependency_manifest",

    # Environment / config
    # Both .yml and .yaml default to environment_config (strategy: preserve).
    # The classify_file() refine block promotes .github/workflows/*.yml|yaml → ci_config.
    ".env": "environment_config", ".env.example": "environment_config",
    ".yml": "environment_config",
    ".yaml": "environment_config",
    "Dockerfile": "environment_config",
    "docker-compose.yml": "environment_config",
    "docker-compose.yaml": "environment_config",

    # Scripts
    ".sh": "script", ".bash": "script", ".zsh": "script",
    ".ps1": "script", ".bat": "script", ".cmd": "script",

    # Images / media
    ".png": "asset_binary", ".jpg": "asset_binary", ".jpeg": "asset_binary",
    ".gif": "asset_binary", ".svg": "asset_text",
    ".mp4": "asset_binary", ".avi": "asset_binary",
}

# Files/dirs to always skip
SKIP_PATTERNS = {
    ".git", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", ".venv", "venv", "env", ".env",
    "dist", "build", "target", "_build", ".build",
    ".DS_Store", "Thumbs.db",
    "migration_workspace",  # skip our own workspace
}

# Files where migration_strategy can be pre-assigned with high confidence
STRATEGY_HINTS = {
    "requirements.txt": "adapt",
    "requirements-dev.txt": "adapt",
    "Pipfile": "adapt",
    "Cargo.toml": "adapt",
    "go.mod": "adapt",
    "package.json": "adapt",
    "pyproject.toml": "adapt",
    "Makefile": "adapt",
    "CMakeLists.txt": "adapt",
    "Dockerfile": "adapt",
    "docker-compose.yml": "adapt",
    "docker-compose.yaml": "adapt",
    ".gitignore": "preserve",
    ".gitattributes": "preserve",
    "LICENSE": "preserve",
    "CHANGELOG.md": "preserve",
    "CONTRIBUTING.md": "preserve",
}

# Test-related name patterns
TEST_PATTERNS = ["test_", "_test.", "spec.", "_spec.", "tests/", "test/", "spec/"]

# Source code extensions that may contain directory-load patterns
SOURCE_CODE_EXTS = {
    ".py", ".go", ".js", ".ts", ".jsx", ".tsx",
    ".rb", ".java", ".cs", ".rs", ".c", ".cpp", ".cc",
}

# Directory-load patterns grouped by language.
# Each tuple: (regex_pattern, call_name). Capture group 1 must match the
# first string argument — i.e., a literal directory or glob path.
DIRLOAD_PATTERNS = [
    # Python — os module
    (r'os\.listdir\(\s*["\']([^"\']+)["\']', "os.listdir"),
    (r'os\.scandir\(\s*["\']([^"\']+)["\']', "os.scandir"),
    (r'os\.walk\(\s*["\']([^"\']+)["\']', "os.walk"),
    # Python — glob module
    (r'glob\.glob\(\s*["\']([^"\']+)["\']', "glob.glob"),
    (r'glob\.iglob\(\s*["\']([^"\']+)["\']', "glob.iglob"),
    # Python — pathlib
    (r'Path\(\s*["\']([^"\']+)["\']\s*\)\.(rglob|glob|iterdir)\(', "pathlib.glob"),
    (r'["\']([^"\']+)["\'].*?\.rglob\(', "Path.rglob"),
    # Python — importlib.resources / pkgutil
    (r'importlib\.resources\.files\(\s*["\']([^"\']+)["\']', "importlib.resources.files"),
    (r'pkgutil\.iter_modules\(\s*\[?["\']([^"\']+)["\']', "pkgutil.iter_modules"),
    # Go
    (r'os\.ReadDir\(\s*["\']([^"\']+)["\']', "os.ReadDir"),
    (r'filepath\.WalkDir\(\s*["\']([^"\']+)["\']', "filepath.WalkDir"),
    (r'filepath\.Walk\(\s*["\']([^"\']+)["\']', "filepath.Walk"),
    (r'filepath\.Glob\(\s*["\']([^"\']+)["\']', "filepath.Glob"),
    (r'ioutil\.ReadDir\(\s*["\']([^"\']+)["\']', "ioutil.ReadDir"),
    # JavaScript / TypeScript / Node.js
    (r'fs\.readdirSync\(\s*["\']([^"\']+)["\']', "fs.readdirSync"),
    (r'fs\.readdir\(\s*["\']([^"\']+)["\']', "fs.readdir"),
    (r'glob\.sync\(\s*["\']([^"\']+)["\']', "glob.sync"),
    (r'fastGlob\.sync\(\s*["\']([^"\']+)["\']', "fast-glob.sync"),
    (r'globSync\(\s*["\']([^"\']+)["\']', "globSync"),
    # Ruby
    (r'Dir\.glob\(\s*["\']([^"\']+)["\']', "Dir.glob"),
    (r'Dir\[\s*["\']([^"\']+)["\']', "Dir[]"),
    # Rust
    (r'fs::read_dir\(\s*["\']([^"\']+)["\']', "fs::read_dir"),
    (r'glob\(\s*["\']([^"\']+)["\']', "glob"),
]


def glob_base_dir(pattern: str) -> str:
    """Extract the base directory from a glob pattern.

    Examples:
        "references/*.md"     → "references"
        "skills/**/*.yaml"    → "skills"
        "data/fixtures/"      → "data/fixtures"
        "./scripts/"          → "scripts"
    """
    # Strip leading ./ or /
    norm = pattern.replace("\\", "/")
    while norm.startswith("./") or norm.startswith("/"):
        norm = norm.lstrip("/")
        if norm.startswith("./"):
            norm = norm[2:]
    # Strip trailing slash (bare directory references)
    norm = norm.rstrip("/")
    # Split on first wildcard-containing component
    parts = norm.split("/")
    base_parts = []
    for part in parts:
        if any(c in part for c in ("*", "?", "[")):
            break
        base_parts.append(part)
    return "/".join(base_parts) if base_parts else ""


def scan_dirloads(source_dir: str) -> dict:
    """Scan source code files for directory-load patterns.

    Returns a dict mapping normalized base-dir (relative to source_dir) →
    list of {src_file, line, call_name, raw_arg} dicts.
    Only source code files are scanned (see SOURCE_CODE_EXTS).
    """
    source = Path(source_dir).resolve()
    findings: dict = {}  # base_dir → [evidence list]

    for root, dirs, files in os.walk(source):
        # Prune skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_PATTERNS]

        for fname in files:
            if Path(fname).suffix.lower() not in SOURCE_CODE_EXTS:
                continue
            abs_path = Path(root) / fname
            rel_src = str(abs_path.relative_to(source))
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                for pattern, call_name in DIRLOAD_PATTERNS:
                    m = re.search(pattern, line)
                    if not m:
                        continue
                    raw_arg = m.group(1)
                    base = glob_base_dir(raw_arg)
                    if not base:
                        continue
                    # Normalise: strip trailing slash
                    base = base.rstrip("/")
                    if base not in findings:
                        findings[base] = []
                    findings[base].append({
                        "src_file": rel_src,
                        "line": line_no,
                        "call_name": call_name,
                        "raw_arg": raw_arg,
                    })

    return findings


def classify_file(rel_path: str, runtime_dirs=None) -> dict:  # runtime_dirs: set[str] | None
    """Classify a single file and return a starter inventory entry.

    runtime_dirs: set of normalised relative directory paths detected by scan_dirloads().
    Files whose path starts with any of these directories are flagged as runtime_dependency:
    true and have their strategy upgraded from reference_only/preserve → direct_use.
    """
    path = Path(rel_path)
    name = path.name
    suffix = path.suffix.lower()

    # Determine type
    file_type = EXTENSION_TYPE_MAP.get(name) or EXTENSION_TYPE_MAP.get(suffix, "other")

    # Refine: is this a test file?
    is_test = any(p in rel_path for p in TEST_PATTERNS)
    if is_test and file_type == "source_code":
        file_type = "test_code"

    # Refine: .github/workflows/*.yml is CI
    if ".github/workflows" in rel_path and suffix in (".yml", ".yaml"):
        file_type = "ci_config"

    # Determine migration strategy hint
    strategy = STRATEGY_HINTS.get(name, "")
    if not strategy:
        if file_type == "source_code":
            strategy = "translate"
        elif file_type == "test_code":
            strategy = "translate"
        elif file_type == "test_fixture":
            strategy = "direct_use"
        elif file_type == "documentation":
            strategy = "reference_only"
        elif file_type == "asset_binary":
            strategy = "direct_use"
        elif file_type == "ci_config":
            strategy = "adapt"
        elif file_type == "build_config":
            strategy = "adapt"
        elif file_type == "dependency_manifest":
            strategy = "adapt"
        elif file_type == "environment_config":
            strategy = "preserve"
        elif file_type == "script":
            strategy = "adapt"
        else:
            strategy = "preserve"

    # Docs that mention algorithms should be marked p3_required
    p3 = file_type in ("documentation",) and any(
        kw in name.lower() for kw in ["algo", "math", "design", "spec", "note", "theory"]
    )

    # Check if this file lives under a directory loaded at runtime by code.
    # If so, upgrade strategy (reference_only/preserve → direct_use) and flag it.
    norm = rel_path.replace("\\", "/")
    matched_dir = None
    if runtime_dirs:
        for rd in runtime_dirs:
            if norm == rd or norm.startswith(rd + "/"):
                matched_dir = rd
                break

    runtime_dependency = matched_dir is not None
    if runtime_dependency and strategy in ("reference_only", "preserve"):
        strategy = "direct_use"

    notes = f"[AUTO-CLASSIFIED: review and confirm type={file_type}, strategy={strategy}]"
    if runtime_dependency:
        notes += (
            f" [RUNTIME-DEPENDENCY: directory '{matched_dir}' is scanned by source code"
            " at runtime — strategy upgraded to direct_use; AI must verify]"
        )

    entry = {
        "path": rel_path,
        "type": file_type,
        "purpose": "",   # AI must fill this in
        "migration_strategy": strategy,
        "depends_on_ecosystem": [],
        "status": "TODO",
        "target_path": "",
        "notes": notes,
        "p3_required": p3,
    }
    if runtime_dependency:
        entry["runtime_dependency"] = True
        entry["runtime_dependency_dir"] = matched_dir
    return entry


def scan(source_dir: str, output_path: str, dirload_report: bool = False):
    source = Path(source_dir).resolve()
    assets = []

    # Phase 1a: detect directory-load patterns in source code
    dirload_findings: dict = {}
    if dirload_report:
        print("Scanning source code for directory-load patterns...")
        dirload_findings = scan_dirloads(source_dir)
        if dirload_findings:
            print(f"  Found {len(dirload_findings)} runtime-loaded director(y/ies):")
            for d, refs in sorted(dirload_findings.items()):
                print(f"    {d!r:40s} ← loaded by {len(refs)} code site(s)")
        else:
            print("  No directory-load patterns detected.")

    runtime_dirs = set(dirload_findings.keys()) if dirload_findings else None

    # Phase 1b: walk all files
    for root, dirs, files in os.walk(source):
        # Prune skip dirs in-place
        dirs[:] = [d for d in dirs if d not in SKIP_PATTERNS]

        for fname in sorted(files):
            if fname in SKIP_PATTERNS:
                continue
            abs_path = Path(root) / fname
            rel_path = str(abs_path.relative_to(source))
            entry = classify_file(rel_path, runtime_dirs=runtime_dirs)
            assets.append(entry)

    # Count by strategy
    by_strategy: dict = {}
    for a in assets:
        s = a["migration_strategy"]
        by_strategy[s] = by_strategy.get(s, 0) + 1

    runtime_dep_count = sum(1 for a in assets if a.get("runtime_dependency"))

    # Build dirload_summary block (only included when dirload_report=True and findings exist)
    dirload_summary = None
    if dirload_report and dirload_findings:
        dirload_summary = {
            "note": (
                "Directories scanned at runtime by source code. "
                "Files inside are tagged runtime_dependency: true and strategy upgraded to direct_use. "
                "AI must verify each tagged file and confirm strategy."
            ),
            "detected_dirs": {
                d: [
                    {"src_file": r["src_file"], "line": r["line"], "call": r["call_name"], "arg": r["raw_arg"]}
                    for r in refs
                ]
                for d, refs in sorted(dirload_findings.items())
            },
        }

    meta: dict = {
        "scanned_at": datetime.now().isoformat(),
        "total_files": len(assets),
        "by_strategy": by_strategy,
        "note": (
            "Auto-generated by scan_assets.py. "
            "AI agent must review every entry: fill in 'purpose', "
            "confirm 'migration_strategy', populate 'depends_on_ecosystem'."
        ),
    }
    if runtime_dep_count:
        meta["runtime_dependency_count"] = runtime_dep_count
        meta["runtime_dependency_note"] = (
            f"{runtime_dep_count} file(s) tagged as runtime_dependency: true because source code "
            "loads their containing directory at runtime (see dirload_summary). "
            "Strategy has been pre-upgraded to direct_use — AI must verify."
        )

    inventory: dict = {"meta": meta}
    if dirload_summary:
        inventory["dirload_summary"] = dirload_summary
    inventory["assets"] = assets

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(inventory, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\nScanned {len(assets)} files → {output_path}")
    print("By strategy:")
    for strategy, count in sorted(by_strategy.items()):
        print(f"  {strategy:20s} {count}")
    if runtime_dep_count:
        print(f"\n  ⚠  {runtime_dep_count} file(s) tagged runtime_dependency: true (strategy upgraded to direct_use)")
        print("     AI must verify each tagged entry in asset-inventory.yaml")
    print("\nNext: AI agent reviews each entry, fills 'purpose' and confirms strategy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Lang-migration asset scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scan (no dirload detection)
  python scan_assets.py --source ./myproject --output migration_workspace/asset-inventory.yaml

  # Full scan with directory-load pattern detection (recommended for agent/tool projects)
  python scan_assets.py --source ./myproject --output migration_workspace/asset-inventory.yaml --dirload-report

  # Just report dirload patterns without writing inventory
  python scan_assets.py --source ./myproject --output /dev/null --dirload-report
""",
    )
    parser.add_argument("--source", required=True, help="Path to source project root")
    parser.add_argument("--output", required=True, help="Path to write asset-inventory.yaml")
    parser.add_argument(
        "--dirload-report",
        action="store_true",
        default=False,
        help=(
            "Detect directory-load patterns in source code (os.listdir, glob.glob, "
            "os.ReadDir, fs.readdirSync, etc.) and tag files under those directories "
            "as runtime_dependency: true with strategy upgraded to direct_use. "
            "Recommended for projects that are agents, CLIs, or data pipelines."
        ),
    )
    args = parser.parse_args()

    if not os.path.isdir(args.source):
        print(f"Error: source dir not found: {args.source}")
        raise SystemExit(1)

    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    scan(args.source, args.output, dirload_report=args.dirload_report)

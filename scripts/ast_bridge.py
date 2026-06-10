#!/usr/bin/env python3
"""ast_bridge.py — AST Bridge toolchain for the lang-migration skill.

Machine-truth extraction and skeleton generation via tree-sitter.
Protocol documentation: references/ast-bridge.md

Subcommands:
  doctor    Check/install tree-sitter dependencies for a language pair
  index     Extract ast-index.yaml from source project (Stage 1)
  verify    Mechanical PGR-3 checks: ipo-registry.yaml vs ast-index.yaml
  skeleton  Generate draft target files with TODO(migrate) markers (Stage 2)
  todos     Count remaining TODO(migrate) markers (PGR-4-F gate)

Design contract for LLM callers:
  - No interactive prompts, ever
  - Deterministic YAML output (sorted, stable)
  - Exit code 0 = success/clean, 1 = findings/work remaining, 2 = usage or environment error
  - Every error message states the exact next action
"""

import argparse
import importlib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

TOOL_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Language registry
# --------------------------------------------------------------------------

# lang -> (pip package, python module)
LANG_PKGS = {
    "python":     ("tree-sitter-python",     "tree_sitter_python"),
    "go":         ("tree-sitter-go",         "tree_sitter_go"),
    "rust":       ("tree-sitter-rust",       "tree_sitter_rust"),
    "javascript": ("tree-sitter-javascript", "tree_sitter_javascript"),
    "typescript": ("tree-sitter-typescript", "tree_sitter_typescript"),
    "c":          ("tree-sitter-c",          "tree_sitter_c"),
    "cpp":        ("tree-sitter-cpp",        "tree_sitter_cpp"),
    "zig":        ("tree-sitter-zig",        "tree_sitter_zig"),
}

EXT_TO_LANG = {
    ".py": "python", ".go": "go", ".rs": "rust",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".zig": "zig",
}

# Extraction config per language. Node type names follow each grammar's node-types.json.
# Support tiers: "full" = index + skeleton source; "index" = index only.
CONFIGS = {
    "python": {
        "tier": "full",
        "function_types": ["function_definition"],
        "class_types": ["class_definition"],
        "branch_types": ["if_statement", "elif_clause", "else_clause",
                         "for_statement", "while_statement",
                         "try_statement", "except_clause",
                         "match_statement", "case_clause"],
        "call_types": ["call"],
        "literal_types": ["integer", "float", "string"],
        "comment_types": ["comment"],
        "decorator_types": ["decorator"],
        "name_field": "name",
    },
    "go": {
        "tier": "full",
        "function_types": ["function_declaration", "method_declaration"],
        "class_types": [],
        "branch_types": ["if_statement", "for_statement",
                         "expression_switch_statement", "type_switch_statement",
                         "select_statement", "expression_case", "type_case",
                         "communication_case", "default_case"],
        "call_types": ["call_expression"],
        "literal_types": ["int_literal", "float_literal", "imaginary_literal",
                          "rune_literal", "interpreted_string_literal",
                          "raw_string_literal"],
        "comment_types": ["comment"],
        "decorator_types": [],
        "name_field": "name",
    },
    "rust": {
        "tier": "index",
        "function_types": ["function_item"],
        "class_types": ["impl_item"],
        "branch_types": ["if_expression", "else_clause", "match_expression",
                         "match_arm", "for_expression", "while_expression",
                         "loop_expression"],
        "call_types": ["call_expression", "macro_invocation"],
        "literal_types": ["integer_literal", "float_literal", "string_literal",
                          "raw_string_literal", "char_literal"],
        "comment_types": ["line_comment", "block_comment"],
        "decorator_types": ["attribute_item"],
        "name_field": "name",
    },
    "javascript": {
        "tier": "index",
        "function_types": ["function_declaration", "method_definition",
                           "generator_function_declaration"],
        "class_types": ["class_declaration"],
        "branch_types": ["if_statement", "else_clause", "for_statement",
                         "for_in_statement", "while_statement", "do_statement",
                         "switch_statement", "switch_case", "switch_default",
                         "try_statement", "catch_clause", "finally_clause"],
        "call_types": ["call_expression"],
        "literal_types": ["number", "string", "template_string"],
        "comment_types": ["comment"],
        "decorator_types": ["decorator"],
        "name_field": "name",
    },
    "c": {
        "tier": "index",
        "function_types": ["function_definition"],
        "class_types": [],
        "branch_types": ["if_statement", "else_clause", "for_statement",
                         "while_statement", "do_statement", "switch_statement",
                         "case_statement"],
        "call_types": ["call_expression"],
        "literal_types": ["number_literal", "string_literal", "char_literal"],
        "comment_types": ["comment"],
        "decorator_types": [],
        "name_field": None,  # name lives inside declarator subtree
    },
    "cpp": {
        "tier": "index",
        "function_types": ["function_definition"],
        "class_types": ["class_specifier", "struct_specifier"],
        "branch_types": ["if_statement", "else_clause", "for_statement",
                         "while_statement", "do_statement", "switch_statement",
                         "case_statement", "try_statement", "catch_clause"],
        "call_types": ["call_expression"],
        "literal_types": ["number_literal", "string_literal", "char_literal"],
        "comment_types": ["comment"],
        "decorator_types": [],
        "name_field": None,
    },
}
CONFIGS["typescript"] = dict(CONFIGS["javascript"])  # same node families


def fail(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def need_yaml():
    try:
        import yaml  # noqa: F401
        return importlib.import_module("yaml")
    except ImportError:
        fail("PyYAML missing. Run: pip install pyyaml")


def load_language(lang):
    """Return a tree_sitter.Language for `lang`, or None with reason string."""
    if lang not in LANG_PKGS:
        return None, f"language '{lang}' not in registry (supported: {', '.join(LANG_PKGS)})"
    pkg, mod_name = LANG_PKGS[lang]
    try:
        from tree_sitter import Language
    except ImportError:
        return None, "tree-sitter missing. Run: pip install tree-sitter"
    try:
        mod = importlib.import_module(mod_name)
    except ImportError:
        return None, f"grammar missing. Run: pip install {pkg}"
    if lang == "typescript":
        return Language(mod.language_typescript()), None
    return Language(mod.language()), None


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------

def cmd_doctor(args):
    langs = [s.strip() for s in args.langs.split(",") if s.strip()]
    missing_pkgs = []
    print(f"ast_bridge doctor v{TOOL_VERSION}  (python {sys.version.split()[0]})")
    try:
        importlib.import_module("tree_sitter")
        print("  [OK] tree-sitter core")
    except ImportError:
        print("  [MISSING] tree-sitter core")
        missing_pkgs.append("tree-sitter")
    try:
        importlib.import_module("yaml")
        print("  [OK] pyyaml")
    except ImportError:
        print("  [MISSING] pyyaml")
        missing_pkgs.append("pyyaml")
    for lang in langs:
        if lang not in LANG_PKGS:
            print(f"  [UNSUPPORTED] {lang} — no grammar in registry; "
                  f"index this language manually per references/ast-bridge.md fallback")
            continue
        pkg, mod_name = LANG_PKGS[lang]
        try:
            importlib.import_module(mod_name)
            tier = CONFIGS.get(lang, {}).get("tier", "index")
            print(f"  [OK] grammar {lang} ({pkg}) — tier: {tier}")
        except ImportError:
            print(f"  [MISSING] grammar {lang} — pip install {pkg}")
            missing_pkgs.append(pkg)
    if missing_pkgs:
        cmd = [sys.executable, "-m", "pip", "install"] + missing_pkgs
        if args.install:
            print(f"\nInstalling: {' '.join(missing_pkgs)}")
            r = subprocess.run(cmd)
            if r.returncode != 0:
                fail("pip install failed — check network policy; "
                     "fall back to manual protocols per references/ast-bridge.md")
            print("Install complete. Re-run doctor to confirm.")
        else:
            print(f"\nTo install: {' '.join(cmd)}")
            print("Or re-run with --install")
            sys.exit(1)
    else:
        print("\nAll dependencies satisfied.")


# --------------------------------------------------------------------------
# AST helpers
# --------------------------------------------------------------------------

def text(node, src):
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def line(node):
    return node.start_point[0] + 1


def end_line(node):
    return node.end_point[0] + 1


def find_functions(root, cfg):
    """Yield every function node, including nested ones."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in cfg["function_types"]:
            yield n
        stack.extend(reversed(n.children))


def fn_name(node, cfg, src):
    if cfg["name_field"]:
        nf = node.child_by_field_name(cfg["name_field"])
        if nf is not None:
            return text(nf, src)
    # C/C++: identifier inside declarator subtree
    decl = node.child_by_field_name("declarator")
    cur = decl
    while cur is not None:
        if cur.type in ("identifier", "field_identifier", "qualified_identifier"):
            return text(cur, src)
        nxt = cur.child_by_field_name("declarator")
        if nxt is None:
            for c in cur.children:
                if c.type in ("identifier", "field_identifier"):
                    return text(c, src)
            break
        cur = nxt
    return f"<anon@{line(node)}>"


def parent_class(node, cfg, src):
    cur = node.parent
    while cur is not None:
        if cur.type in cfg["class_types"]:
            nf = cur.child_by_field_name("name") or cur.child_by_field_name("type")
            if nf is not None:
                return text(nf, src)
        cur = cur.parent
    # Go: receiver type as "class"
    if node.type == "method_declaration":
        recv = node.child_by_field_name("receiver")
        if recv is not None:
            m = re.search(r"[A-Za-z_]\w*\s*\)?$", text(recv, src).strip("()* "))
            if m:
                return m.group(0).strip()
    return ""


def walk_body(node, cfg, on_node):
    """Walk a function body, NOT descending into nested function definitions."""
    stack = list(node.children)
    while stack:
        n = stack.pop()
        if n.type in cfg["function_types"]:
            continue  # nested function owns its own counts
        on_node(n)
        stack.extend(reversed(n.children))


def signature_of(node, cfg, src):
    body = node.child_by_field_name("body")
    if body is not None:
        sig = src[node.start_byte:body.start_byte].decode("utf-8", errors="replace")
    else:
        sig = text(node, src).split("\n", 1)[0]
    # drop comment lines that sit between the signature and the body
    lines = [l for l in sig.splitlines() if not l.strip().startswith(("#", "//"))]
    return " ".join(" ".join(lines).split())


def python_docstring(body_node, src):
    if body_node is None or not body_node.children:
        return None
    first = body_node.children[0]
    if first.type == "expression_statement" and first.children \
            and first.children[0].type == "string":
        return first.children[0]
    return None


def extract_function(node, cfg, src, rel_path, lang):
    body = node.child_by_field_name("body")
    doc_node = python_docstring(body, src) if lang == "python" else None
    branches, calls, literals, comments, decorators = 0, [], [], [], []

    def visit(n):
        nonlocal branches
        if n.type in cfg["branch_types"]:
            branches += 1
        elif n.type in cfg["call_types"]:
            callee = n.child_by_field_name("function") or (n.children[0] if n.children else None)
            if callee is not None:
                calls.append({"name": text(callee, src), "line": line(n)})
        elif n.type in cfg["literal_types"]:
            if doc_node is not None and n.start_byte == doc_node.start_byte:
                return
            val = text(n, src)
            if len(val) > 80:
                val = val[:77] + "..."
            literals.append({"value": val, "type": n.type, "line": line(n)})
        elif n.type in cfg["comment_types"]:
            comments.append({"text": text(n, src), "line": line(n)})

    scan_root = body if body is not None else node
    walk_body(scan_root, cfg, visit)

    if doc_node is not None:
        comments.insert(0, {"text": text(doc_node, src), "line": line(doc_node), "docstring": True})

    if node.parent is not None and node.parent.type == "decorated_definition":
        for c in node.parent.children:
            if c.type in cfg["decorator_types"]:
                decorators.append(text(c, src))

    name = fn_name(node, cfg, src)
    cls = parent_class(node, cfg, src)
    stem = os.path.splitext(os.path.basename(rel_path))[0]
    fid = f"{stem}::{cls}.{name}" if cls else f"{stem}::{name}"

    seen, dedup_calls = set(), []
    for c in sorted(calls, key=lambda x: x["line"]):
        if c["name"] not in seen:
            seen.add(c["name"])
            dedup_calls.append(c)

    return {
        "id": fid,
        "file": rel_path,
        "start_line": line(node.parent if node.parent is not None
                           and node.parent.type == "decorated_definition" else node),
        "end_line": end_line(node),
        "signature": signature_of(node, cfg, src),
        "parent_class": cls,
        "branch_count": branches,
        "call_sites": dedup_calls,
        "literals": sorted(literals, key=lambda x: x["line"]),
        "comments": sorted(comments, key=lambda x: x["line"]),
        "decorators": decorators,
    }


# --------------------------------------------------------------------------
# index
# --------------------------------------------------------------------------

def collect_files(args):
    files = []
    if args.files_from:
        yaml = need_yaml()
        with open(args.files_from, encoding="utf-8") as f:
            inv = yaml.safe_load(f) or {}
        entries = inv.get("assets", inv.get("entries", []))
        for e in entries or []:
            if isinstance(e, dict) and e.get("migration_strategy") == "translate":
                files.append(e["path"])
    else:
        for root, dirs, names in os.walk(args.source):
            dirs[:] = [d for d in dirs if d not in
                       (".git", "node_modules", "__pycache__", "migration_workspace",
                        "venv", ".venv", "target", "dist", "build")]
            for n in names:
                if os.path.splitext(n)[1] in EXT_TO_LANG:
                    files.append(os.path.relpath(os.path.join(root, n), args.source))
    return sorted(files)


def cmd_index(args):
    yaml = need_yaml()
    from tree_sitter import Parser
    lang = args.lang
    if lang not in CONFIGS:
        fail(f"no extraction config for '{lang}'. Supported: {', '.join(sorted(CONFIGS))}. "
             f"For other languages, follow the manual fallback in references/ast-bridge.md")
    ts_lang, err = load_language(lang)
    if err:
        fail(err)
    cfg = CONFIGS[lang]
    parser = Parser(ts_lang)

    files = collect_files(args)
    files = [f for f in files if EXT_TO_LANG.get(os.path.splitext(f)[1]) == lang]
    if not files:
        fail(f"no {lang} files found under {args.source} "
             f"(or none with strategy=translate in {args.files_from})")

    functions, parse_failures = [], []
    for rel in files:
        path = os.path.join(args.source, rel)
        try:
            with open(path, "rb") as f:
                src = f.read()
            tree = parser.parse(src)
            if tree.root_node.has_error:
                parse_failures.append({"file": rel, "reason": "syntax errors in parse tree"})
            for fn_node in find_functions(tree.root_node, cfg):
                functions.append(extract_function(fn_node, cfg, src, rel, lang))
        except OSError as e:
            parse_failures.append({"file": rel, "reason": str(e)})

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": f"ast_bridge.py v{TOOL_VERSION}",
            "grammar": f"{LANG_PKGS[lang][0]}",
            "source_lang": lang,
            "source_dir": args.source,
            "files_scanned": len(files),
            "functions_found": len(functions),
            "parse_failures": parse_failures,
        },
        "functions": sorted(functions, key=lambda f: (f["file"], f["start_line"])),
    }
    with open(args.output, "w", encoding="utf-8") as f:
        yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, width=100)
    print(f"ast-index written: {args.output}")
    print(f"  files: {len(files)}  functions: {len(functions)}  parse_failures: {len(parse_failures)}")
    if parse_failures:
        print("  NOTE: analyze parse-failed files manually (listed in meta.parse_failures)")


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

EXEMPT_LITERALS = {"0", "1", "-1", '""', "''", "0.0", "1.0"}


def cmd_verify(args):
    yaml = need_yaml()
    with open(args.index, encoding="utf-8") as f:
        idx = yaml.safe_load(f)
    with open(args.registry, encoding="utf-8") as f:
        reg = yaml.safe_load(f) or {}
    reg_entries = reg.get("functions", reg.get("entries", [])) or []
    reg_by_id = {e.get("id"): e for e in reg_entries if isinstance(e, dict)}

    findings = []
    for fn in idx.get("functions", []):
        fid = fn["id"]
        entry = reg_by_id.get(fid)
        if entry is None:
            findings.append(f"PGR-3-A: function {fn['file']}::{fid.split('::',1)[-1]} "
                            f"not in ipo-registry.yaml (not marked SKIP)")
            continue
        if entry.get("translation_status") == "SKIP":
            continue
        steps = (entry.get("process") or {}).get("steps") or entry.get("steps") or []
        if fn["branch_count"] > 0 and len(steps) < fn["branch_count"]:
            findings.append(f"PGR-3-G: entry id={fid} — steps_count={len(steps)} < "
                            f"branch_count={fn['branch_count']}; branches collapsed")
        if args.strict_literals:
            magic = []
            for s in steps:
                magic += [str(m.get("value")) for m in (s.get("magic_numbers") or [])]
            magic += [str(m.get("value")) for m in (entry.get("magic_numbers") or [])]
            for lit in fn.get("literals", []):
                v = lit["value"]
                if v in EXEMPT_LITERALS or lit["type"] in ("string",
                        "interpreted_string_literal", "raw_string_literal",
                        "template_string", "string_literal"):
                    continue
                if v not in magic and v.strip("()") not in magic:
                    findings.append(f"PGR-3-C*: entry id={fid} — literal {v} "
                                    f"at line {lit['line']} not in magic_numbers (strict mode)")

    print(f"AST VERIFY REPORT  (index: {len(idx.get('functions', []))} functions, "
          f"registry: {len(reg_by_id)} entries)")
    if findings:
        for i, f_ in enumerate(findings, 1):
            print(f"  FINDING [{i}]: {f_}")
        print(f"\nfindings_count: {len(findings)}")
        sys.exit(1)
    print("findings_count: 0")


# --------------------------------------------------------------------------
# skeleton (Stage 2)
# --------------------------------------------------------------------------

PY_TO_GO_TYPES = {
    "int": "int64", "float": "float64", "str": "string", "bool": "bool",
    "bytes": "[]byte", "None": "", "Any": "any", "object": "any",
}


def map_py_type_to_go(t):
    t = t.strip()
    if not t:
        return ""
    if t in PY_TO_GO_TYPES:
        return PY_TO_GO_TYPES[t]
    m = re.match(r"(?:typing\.)?Optional\[(.+)\]$", t)
    if m:
        inner = map_py_type_to_go(m.group(1))
        return f"*{inner}" if inner and not inner.startswith(("[]", "map[")) else inner
    m = re.match(r"list\[(.+)\]$", t)
    if m:
        return f"[]{map_py_type_to_go(m.group(1)) or 'any'}"
    m = re.match(r"dict\[([^,]+),\s*(.+)\]$", t)
    if m:
        return (f"map[{map_py_type_to_go(m.group(1)) or 'any'}]"
                f"{map_py_type_to_go(m.group(2)) or 'any'}")
    m = re.match(r"set\[(.+)\]$", t)
    if m:
        return f"map[{map_py_type_to_go(m.group(1)) or 'any'}]struct{{}}"
    return f"any /* TODO(migrate-type): {t} */"


def go_name(py_name):
    return "".join(w.capitalize() or "_" for w in py_name.split("_"))


def build_shell_tree(node, cfg, src, lang):
    """Language-neutral shell tree from a function body. Nodes:
    {'kind': 'branch'|'stmt'|'comment', ...}"""
    shells = []
    body = node.child_by_field_name("body")
    if body is None:
        return shells
    for child in body.children:
        shells.extend(shell_of(child, cfg, src, lang))
    return shells


def shell_of(n, cfg, src, lang):
    one_line = " ".join(text(n, src).split())
    if len(one_line) > 90:
        one_line = one_line[:87] + "..."
    if n.type in cfg["comment_types"]:
        return [{"kind": "comment", "text": text(n, src), "line": line(n)}]
    if lang == "python" and n.type == "if_statement":
        parts = []
        cond = n.child_by_field_name("condition")
        cons = n.child_by_field_name("consequence")
        parts.append({"ctor": "if",
                      "cond": " ".join(text(cond, src).split()) if cond is not None else "?",
                      "line": line(n),
                      "body": [s for c in (cons.children if cons is not None else [])
                               for s in shell_of(c, cfg, src, lang)]})
        for alt in n.children_by_field_name("alternative"):
            if alt.type == "elif_clause":
                acond = alt.child_by_field_name("condition")
                acons = alt.child_by_field_name("consequence")
                parts.append({"ctor": "elif",
                              "cond": " ".join(text(acond, src).split()) if acond is not None else "?",
                              "line": line(alt),
                              "body": [s for c in (acons.children if acons is not None else [])
                                       for s in shell_of(c, cfg, src, lang)]})
            elif alt.type == "else_clause":
                ab = alt.child_by_field_name("body")
                parts.append({"ctor": "else", "cond": "", "line": line(alt),
                              "body": [s for c in (ab.children if ab is not None else [])
                                       for s in shell_of(c, cfg, src, lang)]})
        return [{"kind": "chain", "parts": parts}]
    if lang == "python" and n.type in ("for_statement", "while_statement"):
        hdr = text(n, src).split(":", 1)[0]
        body = n.child_by_field_name("body")
        return [{"kind": "loop", "cond": " ".join(hdr.split()), "line": line(n),
                 "body": [s for c in (body.children if body is not None else [])
                          for s in shell_of(c, cfg, src, lang)]}]
    if lang == "python" and n.type == "try_statement":
        # Guardrail: no error-model conversion — emit whole construct as TODO block
        return [{"kind": "stmt", "text": f"TRY-BLOCK (error model conversion is LLM work): {one_line}",
                 "line": line(n)}]
    if n.type in cfg["function_types"]:
        return [{"kind": "stmt", "text": f"NESTED-FUNCTION: {one_line}", "line": line(n)}]
    return [{"kind": "stmt", "text": one_line, "line": line(n)}]


def emit_go(shells, src_file, indent=1):
    pad = "\t" * indent
    out = []
    for s in shells:
        if s["kind"] == "comment":
            for ln in s["text"].splitlines():
                ln = ln.strip().lstrip("#").strip().strip('"""').strip("'''")
                if ln:
                    out.append(f"{pad}// {ln}")
        elif s["kind"] == "stmt":
            out.append(f"{pad}// TODO(migrate): {s['text']} [source: {src_file}:{s['line']}]")
        elif s["kind"] == "loop":
            out.append(f"{pad}for false {{ // TODO(migrate): {s['cond']} "
                       f"[source: {src_file}:{s['line']}]")
            out.extend(emit_go(s["body"], src_file, indent + 1))
            out.append(f"{pad}}}")
        elif s["kind"] == "chain":
            for k, part in enumerate(s["parts"]):
                tag = (f"// TODO(migrate): {part['ctor']} {part['cond']} "
                       f"[source: {src_file}:{part['line']}]").rstrip()
                if part["ctor"] == "if":
                    out.append(f"{pad}if false {{ {tag}")
                elif part["ctor"] == "elif":
                    out.append(f"{pad}}} else if false {{ {tag}")
                else:
                    out.append(f"{pad}}} else {{ {tag}")
                out.extend(emit_go(part["body"], src_file, indent + 1))
            out.append(f"{pad}}}")
    return out


def cmd_skeleton(args):
    yaml = need_yaml()
    from tree_sitter import Parser
    if (args.source_lang, args.target_lang) != ("python", "go"):
        fail(f"skeleton currently ships python→go only (validated pair). "
             f"For {args.source_lang}→{args.target_lang}: write a target config per "
             f"references/ast-bridge.md Stage 2 fallback, or translate manually per phase-4.")
    ts_lang, err = load_language("python")
    if err:
        fail(err)
    cfg = CONFIGS["python"]
    parser = Parser(ts_lang)
    with open(args.index, encoding="utf-8") as f:
        idx = yaml.safe_load(f)

    by_file = {}
    for fn in idx.get("functions", []):
        by_file.setdefault(fn["file"], []).append(fn)

    os.makedirs(args.target_dir, exist_ok=True)
    mapping, stamp = [], datetime.now(timezone.utc).isoformat(timespec="seconds")
    for rel, fns in sorted(by_file.items()):
        src_path = os.path.join(idx["meta"]["source_dir"], rel)
        with open(src_path, "rb") as f:
            src = f.read()
        tree = parser.parse(src)
        node_by_line = {}
        for n in find_functions(tree.root_node, cfg):
            node_by_line[line(n)] = n

        out_rel = os.path.splitext(rel)[0] + ".go"
        out_path = os.path.join(args.target_dir, out_rel)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        pkg = os.path.basename(os.path.dirname(out_rel)) or "main"
        lines = [
            "// AST-GENERATED DRAFT — DO NOT SHIP.",
            "// Every function below must be completed per its ipo-registry.yaml entry.",
            f"// Generated from {rel} by ast_bridge.py v{TOOL_VERSION} at {stamp}.",
            f"package {re.sub(r'[^a-z0-9_]', '', pkg.lower()) or 'main'}",
            "",
        ]
        for fn in sorted(fns, key=lambda x: x["start_line"]):
            node = node_by_line.get(fn["start_line"]) or node_by_line.get(fn["start_line"] + len(fn.get("decorators", [])))
            fn_start = len(lines) + 1
            lines.append(f"// TODO(migrate-signature): {fn['signature']} [source: {rel}:{fn['start_line']}]")
            for d in fn.get("decorators", []):
                lines.append(f"// TODO(migrate-decorator): {d} — no Go equivalent; see lang-pair module")
            ret = ""
            m = re.search(r"->\s*(.+?)\s*:?\s*$", fn["signature"])
            if m:
                mapped = map_py_type_to_go(m.group(1).strip().strip('"'))
                if mapped:
                    ret = " " + mapped
            py_name = fn["id"].split("::")[-1].split(".")[-1]
            recv = ""
            if fn["parent_class"]:
                recv = f"(self *{go_name(fn['parent_class'])}) "
            if py_name == "__init__" and fn["parent_class"]:
                # Class→Struct pattern: constructor becomes NewX (see lang-pair module)
                cls = go_name(fn["parent_class"])
                lines.append(f"// TODO(migrate-constructor): __init__ maps to New{cls} "
                             f"per the lang-pair Class→Struct pattern")
                lines.append(f"func New{cls}( /* TODO(migrate-signature) */ ) *{cls} {{")
            else:
                lines.append(f"func {recv}{go_name(py_name)}"
                             f"( /* TODO(migrate-signature) */ ){ret} {{")
            shells = build_shell_tree(node, cfg, src, "python") if node is not None else []
            if shells:
                lines.extend(emit_go(shells, rel))
            else:
                lines.append(f"\t// TODO(migrate): body [source: {rel}:{fn['start_line']}-{fn['end_line']}]")
            lines.append("}")
            lines.append("")
            todo_n = sum(1 for l in lines[fn_start - 1:] if "TODO(migrate" in l)
            mapping.append({
                "id": fn["id"],
                "source_file": rel,
                "source_lines": f"{fn['start_line']}-{fn['end_line']}",
                "skeleton_file": out_rel,
                "skeleton_lines": f"{fn_start}-{len(lines) - 1}",
                "todo_count_initial": todo_n,
                "todo_count_remaining": todo_n,
            })
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    map_path = args.map_output
    with open(map_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"meta": {"generated_at": stamp, "tool": f"ast_bridge.py v{TOOL_VERSION}",
                                 "pair": f"{args.source_lang}->{args.target_lang}"},
                        "skeletons": mapping}, f, sort_keys=False, allow_unicode=True)
    total_todos = sum(m["todo_count_initial"] for m in mapping)
    print(f"skeletons written under: {args.target_dir}")
    print(f"  functions: {len(mapping)}  TODO(migrate) markers: {total_todos}")
    print(f"  mapping: {map_path}  ← merge each entry into its ipo-registry ast_bridge block")


# --------------------------------------------------------------------------
# todos (PGR-4-F)
# --------------------------------------------------------------------------

def cmd_todos(args):
    hits = []
    for root, dirs, names in os.walk(args.target_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "vendor")]
        for n in names:
            p = os.path.join(root, n)
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    for i, ln in enumerate(f, 1):
                        if "TODO(migrate" in ln:
                            hits.append((os.path.relpath(p, args.target_dir), i, ln.strip()[:120]))
            except OSError:
                continue
    print(f"PGR-4-F TODO(migrate) scan: {args.target_dir}")
    by_file = {}
    for f_, i, ln in hits:
        by_file.setdefault(f_, []).append((i, ln))
    for f_ in sorted(by_file):
        print(f"  {f_}: {len(by_file[f_])} markers")
        if args.verbose:
            for i, ln in by_file[f_]:
                print(f"    {i}: {ln}")
    print(f"total_remaining: {len(hits)}")
    sys.exit(1 if hits else 0)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="ast_bridge.py",
                                 description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=TOOL_VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="check/install tree-sitter dependencies")
    d.add_argument("--langs", required=True, help="comma-separated, e.g. python,go")
    d.add_argument("--install", action="store_true", help="auto-run pip install for missing packages")
    d.set_defaults(fn=cmd_doctor)

    i = sub.add_parser("index", help="Stage 1: extract ast-index.yaml")
    i.add_argument("--source", required=True, help="source project root")
    i.add_argument("--lang", required=True, help="source language key (e.g. python)")
    i.add_argument("--files-from", help="asset-inventory.yaml — only strategy:translate files")
    i.add_argument("--output", default="migration_workspace/ast-index.yaml")
    i.set_defaults(fn=cmd_index)

    v = sub.add_parser("verify", help="mechanical PGR-3 checks against the index")
    v.add_argument("--index", default="migration_workspace/ast-index.yaml")
    v.add_argument("--registry", default="migration_workspace/ipo-registry.yaml")
    v.add_argument("--strict-literals", action="store_true",
                   help="also flag numeric literals missing from magic_numbers")
    v.set_defaults(fn=cmd_verify)

    s = sub.add_parser("skeleton", help="Stage 2: generate draft target files (python→go)")
    s.add_argument("--index", default="migration_workspace/ast-index.yaml")
    s.add_argument("--source-lang", default="python")
    s.add_argument("--target-lang", default="go")
    s.add_argument("--target-dir", required=True)
    s.add_argument("--map-output", default="migration_workspace/skeleton-map.yaml")
    s.set_defaults(fn=cmd_skeleton)

    t = sub.add_parser("todos", help="PGR-4-F: count remaining TODO(migrate) markers")
    t.add_argument("--target-dir", required=True)
    t.add_argument("--verbose", action="store_true")
    t.set_defaults(fn=cmd_todos)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

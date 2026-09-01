#!/usr/bin/env python3
"""Validate YAML frontmatter of a SKILL.md file.

Usage: python validate.py <path-to-SKILL.md>
Output: JSON to stdout.  Exit 0 = clean, 1 = has errors.
"""

import json, re, sys
from pathlib import Path
import yaml

_NEEDS_QUOTING = re.compile(r""": | \#|[{}\[\]&*!|>'%@`]""")


def validate(text: str) -> dict:
    lines = text.split("\n")
    issues = []

    # --- delimiters ---
    if not lines or lines[0].strip() != "---":
        return {"valid": False, "issues": [_err("missing_open_delimiter")]}
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return {"valid": False, "issues": [_err("missing_close_delimiter")]}

    fm_text = "\n".join(lines[1:close])

    # --- parse ---
    try:
        parsed = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        return {"valid": False, "issues": [_err("yaml_parse_error", str(e))]}
    if not isinstance(parsed, dict):
        return {"valid": False, "issues": [_err("not_a_mapping")]}

    # --- required fields ---
    for f in ("name", "description"):
        v = parsed.get(f)
        if v is None:
            issues.append(_err(f"missing_{f}"))
        elif not isinstance(v, str) or not v.strip():
            issues.append(_err(f"empty_{f}"))

    # --- quoting safety ---
    for line in lines[1:close]:
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.+)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw in ("|", ">", "|+", "|-", ">+", ">-"):
            continue
        is_quoted = (raw[0] in "\"'" and raw[-1] == raw[0] and len(raw) > 1)
        if not is_quoted and _NEEDS_QUOTING.search(raw):
            issues.append(_warn("should_quote", f"'{key}' has unquoted YAML special chars"))
        if raw.startswith('"') and raw.endswith('"') and re.search(r'(?<!\\)"', raw[1:-1]):
            issues.append(_err("broken_double_quote", f"'{key}' has unescaped '\"' inside double-quoted string"))

    # --- description length ---
    desc = parsed.get("description")
    if isinstance(desc, str) and len(desc) > 1024:
        issues.append(_warn("description_too_long", f"{len(desc)} chars"))

    # --- dependencies (optional) ---
    deps = parsed.get("dependencies")
    if deps is not None:
        if not isinstance(deps, list):
            issues.append(_warn("bad_dependencies", "dependencies must be a list"))
        elif not all(isinstance(d, str) and d.strip() for d in deps):
            issues.append(_warn("bad_dependencies", "each dependency must be a non-empty string"))

    has_err = any(i["severity"] == "error" for i in issues)
    return {"valid": not has_err, "issues": issues, "parsed": parsed}


def _err(code, msg=""):
    return {"severity": "error", "code": code, "message": msg}

def _warn(code, msg=""):
    return {"severity": "warn", "code": code, "message": msg}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate.py <SKILL.md>", file=sys.stderr)
        sys.exit(2)
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    result = validate(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["valid"] else 1)

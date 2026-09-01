
import json, re
import yaml
from pathlib import Path
from typing import Optional, Dict

def load_manifest_from_workdir(workdir: str) -> Dict:
    # 优先级列表
    candidates = [
        "skill-manifest.yaml",
        "skill-manifest.yml",
        "manifest.yaml",
        "manifest.yml",
        "skill.yaml",
        "skill.yml",
        "skill-checker-export.json",
        "package.json",
        "skill.md",
        "README.md",
        "readme.md",
    ]
    wd = Path(workdir)
    for name in candidates:
        p = wd / name
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        if p.suffix in (".yaml", ".yml"):
            return yaml.safe_load(text)
        if p.suffix == ".json":
            return json.loads(text)
        if name.lower().endswith(".md") or name.lower().startswith("readme"):
            # 尝试提取 YAML frontmatter: ---\n ... \n---
            m = re.search(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
            if m:
                try:
                    return yaml.safe_load(m.group(1))
                except Exception:
                    pass
            # 否则按 markdown 内容做简单解析（比如查找 entrypoint URL 的行）
            # 这里保持简单：返回 minimal manifest if possible
            # 可根据你的 skill.md 规范做自定义解析
    raise FileNotFoundError("no manifest-like file found in workdir")

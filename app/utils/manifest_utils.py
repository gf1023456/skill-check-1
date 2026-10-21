
import json, re
import yaml
from pathlib import Path
from typing import Optional, Dict

def _try_load_file(path: Path) -> Optional[Dict]:
    """尝试从单个文件加载 manifest。"""
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    if path.suffix == ".json":
        return json.loads(text)
    if path.suffix == ".md":
        m = re.search(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
        if m:
            try:
                return yaml.safe_load(m.group(1))
            except Exception:
                pass
        return {
            "name": path.stem,
            "version": "0.1.0",
            "entrypoint": {"type": "http", "url": "", "method": "POST"},
            "description": (text.strip()[:200] if text.strip() else "No description"),
        }
    return None


def load_manifest_from_workdir(workdir: str) -> Dict:
    # 优先级列表: 结构化 manifest 优先，SKILL.md 优先于 skill.md
    candidates = [
        "skill-manifest.yaml",
        "skill-manifest.yml",
        "manifest.yaml",
        "manifest.yml",
        "skill.yaml",
        "skill.yml",
        "skill-checker-export.json",
        "package.json",
        "SKILL.md",
        "skill.md",
        "README.md",
        "readme.md",
    ]
    wd = Path(workdir)

    # 第一轮: 在 workdir 顶层查找
    for name in candidates:
        p = wd / name
        result = _try_load_file(p)
        if result is not None:
            return result

    # 第二轮: 递归搜索子目录（处理 ZIP 带顶层文件夹的情况）
    for name in candidates:
        for p in sorted(wd.rglob(name)):
            result = _try_load_file(p)
            if result is not None:
                return result

    raise FileNotFoundError("no manifest-like file found in workdir")

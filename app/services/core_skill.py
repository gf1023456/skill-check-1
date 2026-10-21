"""Adapters for the bundled ``skill-checker`` agent skill.

Every uploaded-skill validation goes through this adapter.  The adapter invokes
that skill's canonical frontmatter validator and TRACE scoring utility instead
of maintaining a second, divergent interpretation of the skill contract.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CoreSkillChecker:
    """Run the repository's bundled skill-checker assets for one validation."""

    def __init__(self, skill_root: Optional[Path] = None) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        self.skill_root = skill_root or repository_root / "skill" / "skill-checker"
        self.validator_script = self.skill_root / "scripts" / "validate.py"
        self.scoring_script = self.skill_root / "scripts" / "scoring.py"
        if not self.validator_script.is_file() or not self.scoring_script.is_file():
            raise RuntimeError("bundled skill-checker assets are missing")

    @staticmethod
    def find_skill_markdown(workdir: Path) -> Optional[Path]:
        """Locate the target skill's SKILL.md without following paths outside it."""
        candidates = sorted(workdir.rglob("SKILL.md"))
        return candidates[0] if candidates else None

    def validate_frontmatter(self, workdir: Path) -> dict[str, Any]:
        """Run the core skill's frontmatter validation step for an upload."""
        skill_markdown = self.find_skill_markdown(workdir)
        if skill_markdown is None:
            logger.error("SKILL.md not found in workdir")
            return {
                "valid": False,
                "issues": [{"severity": "error", "code": "missing_skill_md", "message": "SKILL.md not found"}],
            }
        logger.info(f"运行frontmatter验证: {skill_markdown}")
        completed = subprocess.run(
            [sys.executable, str(self.validator_script), str(skill_markdown)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode != 0:
            logger.warning(f"frontmatter验证脚本返回非零状态: {completed.returncode}, stderr={completed.stderr[:500]}")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            logger.error(f"frontmatter验证脚本输出非JSON: {completed.stdout[:500]}")
            raise RuntimeError(f"skill-checker validator returned invalid JSON: {error}") from error
        if not isinstance(result, dict):
            logger.error("frontmatter验证脚本返回非对象")
            raise RuntimeError("skill-checker validator returned a non-object report")
        result["path"] = str(skill_markdown.relative_to(workdir))
        logger.info(f"frontmatter验证完成: valid={result.get('valid')}, issues={len(result.get('issues', []))}")
        return result

    def summarize_environment(self, dependencies: list[dict[str, Any]]) -> dict[str, Any]:
        """Run the core skill's environment-summary scoring step."""
        completed = subprocess.run(
            [sys.executable, str(self.scoring_script), "env-summary"],
            input=json.dumps({"dependencies": dependencies}),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "skill-checker environment scoring failed")
        result = json.loads(completed.stdout)
        if not isinstance(result, dict):
            raise RuntimeError("skill-checker environment scoring returned a non-object report")
        return result

    def evaluate_triggers(self, agent: Any, workdir: Path, frontmatter: dict[str, Any]) -> tuple[list[dict], dict[str, Any]]:
        """Run the core skill's real 20-query trigger evaluation through the agent."""
        parsed = frontmatter.get("parsed", {})
        if not isinstance(parsed, dict) or not frontmatter.get("valid"):
            logger.error("frontmatter无效，跳过触发器评估")
            raise ValueError("a valid SKILL.md frontmatter is required for trigger evaluation")
        skill_markdown = workdir / frontmatter["path"]
        template = (self.skill_root / "references" / "prompts" / "trigger_eval_prompt.md").read_text(encoding="utf-8")
        logger.info(f"开始生成trigger evals: skill_name={parsed['name']}")
        evals = agent.generate_trigger_evals(parsed["name"], parsed["description"], skill_markdown.read_text(encoding="utf-8"))
        logger.info(f"trigger evals生成完成: {len(evals)}个")
        logger.info(f"开始评估trigger queries")
        evaluated = agent.evaluate_trigger_queries(template, parsed["name"], parsed["description"], evals)
        logger.info(f"trigger queries评估完成")
        logger.info(f"运行trigger评分脚本")
        completed = subprocess.run(
            [sys.executable, str(self.scoring_script), "eval-summary", "--skill-name", parsed["name"], "--description", parsed["description"]],
            input=json.dumps(evaluated, ensure_ascii=False), check=False, capture_output=True, text=True, timeout=30,
        )
        if completed.returncode:
            logger.error(f"trigger评分脚本失败: returncode={completed.returncode}, stderr={completed.stderr[:500]}")
            raise RuntimeError(completed.stderr.strip() or "skill-checker trigger scoring failed")
        result = json.loads(completed.stdout)
        if not isinstance(result, dict):
            raise RuntimeError("skill-checker trigger scoring returned a non-object report")
        logger.info(f"trigger评估全部完成")
        return evals, result

    def merge_trace(
        self,
        *,
        skill_name: str,
        evals: list[dict[str, Any]],
        trigger: Optional[dict[str, Any]],
        environment: dict[str, Any],
        frontmatter_valid: bool,
        frontmatter_warnings: int,
    ) -> dict[str, Any]:
        """Produce the core skill's canonical TRACE report."""
        payload = {
            "skill_name": skill_name,
            "evals": evals,
            "environment": environment,
        }
        if trigger is not None:
            payload["trigger"] = trigger
        completed = subprocess.run(
            [
                sys.executable,
                str(self.scoring_script),
                "merge",
                "--frontmatter-valid",
                str(frontmatter_valid).lower(),
                "--frontmatter-warnings",
                str(frontmatter_warnings),
            ],
            input=json.dumps(payload, ensure_ascii=False),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "skill-checker TRACE merge failed")
        result = json.loads(completed.stdout)
        if not isinstance(result, dict):
            raise RuntimeError("skill-checker TRACE merge returned a non-object report")
        return result

"""Orchestrates validation and test execution for uploaded skills."""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import yaml

from ..agent.executor import Executor
from ..agent.llm_agent import LlmAgent
from ..agent.validator import Validator
from .core_skill import CoreSkillChecker
from ..utils.manifest_utils import load_manifest_from_workdir


class SkillManager:
    def __init__(self, storage_root: Path = Path("/tmp/skill_checker_storage")):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._status_dir = self.storage_root / "status"
        self._report_dir = self.storage_root / "reports"
        self._work_dir = self.storage_root / "work"
        for directory in (self._status_dir, self._report_dir, self._work_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def _id_dirs(self, skill_id: str):
        return self._work_dir / skill_id, self._report_dir / f"{skill_id}.json", self._status_dir / f"{skill_id}.json"

    @staticmethod
    def _extract_zip(zip_path: Path, destination: Path) -> None:
        """Extract an upload without allowing entries to escape its work directory."""
        destination = destination.resolve()
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                # ZIP files created on Windows may use backslashes.  Normalize
                # them before validating and writing paths on this POSIX host.
                relative = Path(member.filename.replace("\\", "/"))
                if relative.is_absolute():
                    raise ValueError("zip contains an unsafe path")
                target = (destination / relative).resolve()
                if target != destination and destination not in target.parents:
                    raise ValueError("zip contains an unsafe path")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def get_status(self, skill_id: str) -> Optional[dict]:
        return self._read_json(self._id_dirs(skill_id)[2])

    def get_report(self, skill_id: str) -> Optional[dict]:
        return self._read_json(self._id_dirs(skill_id)[1])

    def run_check_for_skill(self, skill_id: str, baseline_skill_id: Optional[str] = None) -> None:
        workdir, report_path, status_path = self._id_dirs(skill_id)
        executor: Optional[Executor] = None
        manifest_dir: Optional[Path] = None
        try:
            status_path.write_text(json.dumps({"status": "running"}), encoding="utf-8")
            zip_path = self.storage_root / skill_id / "skill.zip"
            if not zip_path.is_file():
                status_path.write_text(json.dumps({"status": "error", "reason": "zip not found"}), encoding="utf-8")
                return

            if workdir.exists():
                shutil.rmtree(workdir)
            workdir.mkdir(parents=True)
            self._extract_zip(zip_path, workdir)
            core_checker = CoreSkillChecker()
            frontmatter = core_checker.validate_frontmatter(workdir)
            target_manifest = load_manifest_from_workdir(workdir)
            if not isinstance(target_manifest, dict):
                raise ValueError("manifest must be an object")

            baseline_manifest = self._load_baseline(baseline_skill_id)
            manifest_dir = Path(tempfile.mkdtemp(prefix="skill-manifest-"))
            manifest_path = manifest_dir / "skill-manifest.yaml"
            manifest_path.write_text(yaml.safe_dump(target_manifest, allow_unicode=True), encoding="utf-8")
            validator = Validator(str(manifest_path))
            static = validator.run_static_checks()

            executor = Executor(str(workdir), target_manifest)
            executor.prepare_and_start()
            deterministic_tests = executor.run_manifest_tests()

            try:
                plan, raw = LlmAgent().request_test_plan(
                    target_manifest, triggers=target_manifest.get("triggers") or [], baseline=baseline_manifest
                )
            except Exception as error:
                plan, raw = None, f"llm error: {error}"

            plan_results = executor.execute_plan(plan or {})
            dependencies = self._environment_dependencies(frontmatter)
            environment = core_checker.summarize_environment(dependencies)
            # This is a real agent evaluation of whether target-skill queries
            # trigger the target skill; it is not a proxy based on HTTP tests.
            # It is mandatory: no TRACE report is emitted if it cannot run.
            evals, trigger = core_checker.evaluate_triggers(LlmAgent(), workdir, frontmatter)
            warnings = sum(1 for issue in frontmatter.get("issues", []) if issue.get("severity") == "warn")
            core_report = core_checker.merge_trace(
                skill_name=target_manifest.get("name") or skill_id,
                evals=evals,
                trigger=trigger,
                environment=environment,
                frontmatter_valid=bool(frontmatter.get("valid")),
                frontmatter_warnings=warnings,
            )
            report = {
                "skill": target_manifest.get("name") or skill_id,
                "skill_checker": {
                    "version": "bundled",
                    "frontmatter": frontmatter,
                    "environment": environment,
                    "trigger": trigger,
                    "trace_report": core_report,
                },
                "static": static,
                "deterministic_tests": deterministic_tests,
                "llm_plan_raw": raw,
                "plan_results": plan_results,
                "legacy_trace": validator.compute_trace(static, deterministic_tests, plan_results),
                "trace": core_report["trace"],
            }
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            status_path.write_text(json.dumps({"status": "done"}), encoding="utf-8")
        except Exception as error:
            status_path.write_text(json.dumps({"status": "error", "reason": str(error)}), encoding="utf-8")
        finally:
            if manifest_dir:
                shutil.rmtree(manifest_dir, ignore_errors=True)
            if executor:
                executor.teardown()

    @staticmethod
    def _environment_dependencies(frontmatter: dict) -> list[dict]:
        """Translate declared dependencies into core skill environment findings."""
        parsed = frontmatter.get("parsed") if isinstance(frontmatter, dict) else None
        declared = parsed.get("dependencies", []) if isinstance(parsed, dict) else []
        supported = {"bash", "file_system", "network", "python", "subprocess"}
        dependencies = []
        for name in declared if isinstance(declared, list) else []:
            if not isinstance(name, str) or not name.strip():
                continue
            normalized = name.strip()
            compatibility = "compatible" if normalized in supported else "unknown"
            dependencies.append({
                "category": "tool",
                "name": normalized,
                "description": f"Declared by the target skill: {normalized}",
                "evidence": "frontmatter dependencies",
                "compatibility": compatibility,
                "reason": (
                    "Available to the skill-checker service."
                    if compatibility == "compatible"
                    else "The service cannot verify this declared dependency."
                ),
            })
        return dependencies

    def _load_baseline(self, baseline_skill_id: Optional[str]) -> Optional[dict]:
        if not baseline_skill_id:
            return None
        zip_path = self.storage_root / baseline_skill_id / "skill.zip"
        if not zip_path.is_file():
            return None
        with tempfile.TemporaryDirectory(prefix="baseline-") as directory:
            destination = Path(directory)
            self._extract_zip(zip_path, destination)
            try:
                manifest = load_manifest_from_workdir(destination)
            except (FileNotFoundError, OSError, ValueError, yaml.YAMLError):
                return None
            return manifest if isinstance(manifest, dict) else None

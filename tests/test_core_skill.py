import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.core_skill import CoreSkillChecker


class CoreSkillCheckerTests(unittest.TestCase):
    def test_validates_target_skill_using_bundled_validator(self):
        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory)
            (workdir / "SKILL.md").write_text("---\nname: example\ndescription: example\n---\n", encoding="utf-8")
            expected = {"valid": True, "issues": [], "parsed": {"name": "example"}}
            with patch("app.services.core_skill.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, json.dumps(expected), "")
                result = CoreSkillChecker().validate_frontmatter(workdir)

        self.assertTrue(result["valid"])
        self.assertEqual(result["path"], "SKILL.md")
        command = run.call_args.args[0]
        self.assertTrue(command[1].endswith("skill/skill-checker/scripts/validate.py"))

    def test_trace_merge_delegates_to_bundled_scoring_script(self):
        expected = {"trace": {"overall": 1.0}}
        with patch("app.services.core_skill.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, json.dumps(expected), "")
            result = CoreSkillChecker().merge_trace(
                skill_name="example",
                evals=[],
                trigger={"summary": {}},
                environment={"summary": {}},
                frontmatter_valid=True,
                frontmatter_warnings=0,
            )

        self.assertEqual(result, expected)
        command = run.call_args.args[0]
        self.assertTrue(command[1].endswith("skill/skill-checker/scripts/scoring.py"))
        self.assertEqual(command[2], "merge")

    def test_runs_real_trigger_workflow_through_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory)
            (workdir / "SKILL.md").write_text("---\nname: example\ndescription: example\n---\n", encoding="utf-8")
            agent = Mock()
            evals = [{"query": "check this skill", "should_trigger": True}]
            agent.generate_trigger_evals.return_value = evals
            agent.evaluate_trigger_queries.return_value = [{**evals[0], "triggered": True}]
            with patch("app.services.core_skill.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, json.dumps({"summary": {"pass_rate": 1.0}}), "")
                returned_evals, trigger = CoreSkillChecker().evaluate_triggers(
                    agent, workdir, {"valid": True, "path": "SKILL.md", "parsed": {"name": "example", "description": "example"}},
                )

        self.assertEqual(returned_evals, evals)
        self.assertEqual(trigger["summary"]["pass_rate"], 1.0)
        agent.generate_trigger_evals.assert_called_once()
        agent.evaluate_trigger_queries.assert_called_once()
        self.assertEqual(run.call_args.args[0][2], "eval-summary")


if __name__ == "__main__":
    unittest.main()

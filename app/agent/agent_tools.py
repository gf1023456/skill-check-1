"""Agent tools - callable tools that the agent can use."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import logging

logger = logging.getLogger(__name__)

# Paths to bundled scripts
SKILL_CHECKER_DIR = Path(__file__).parent.parent.parent / "skill" / "skill-checker"
VALIDATE_SCRIPT = SKILL_CHECKER_DIR / "scripts" / "validate.py"
SCORING_SCRIPT = SKILL_CHECKER_DIR / "scripts" / "scoring.py"
PROMPTS_DIR = SKILL_CHECKER_DIR / "references" / "prompts"


class AgentTool:
    """Base class for agent tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def run(self, **kwargs) -> dict:
        raise NotImplementedError
    
    def to_schema(self) -> dict:
        """Convert to JSON schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
        }


class ValidateFrontmatterTool(AgentTool):
    """Validate SKILL.md frontmatter using bundled validate.py."""
    
    def __init__(self):
        super().__init__(
            name="validate_frontmatter",
            description="Validate YAML frontmatter of a SKILL.md file. Returns JSON with valid, issues, and parsed fields."
        )
    
    def run(self, skill_md_path: str) -> dict:
        """Run validate.py on a SKILL.md file."""
        logger.info(f"Tool validate_frontmatter: validating {skill_md_path}")
        
        try:
            result = subprocess.run(
                [sys.executable, str(VALIDATE_SCRIPT), skill_md_path],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8"
            )
            
            if result.returncode == 0 or result.returncode == 1:
                # Both 0 (valid) and 1 (has errors) are valid outputs
                output = json.loads(result.stdout)
                logger.info(f"Tool validate_frontmatter: valid={output.get('valid')}, issues={len(output.get('issues', []))}")
                return {"success": True, "data": output}
            else:
                logger.error(f"Tool validate_frontmatter failed: {result.stderr}")
                return {"success": False, "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Validation timed out after 30s"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse validation output: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ScoringTool(AgentTool):
    """Run scoring.py commands (eval-summary, env-summary, merge, trace, split)."""
    
    def __init__(self):
        super().__init__(
            name="run_scoring",
            description="Run scoring.py command. Commands: eval-summary (count pass/fail), env-summary (count compatibility), merge (combine into check.json), trace (recompute TRACE), split (train/test split)"
        )
    
    def run(self, command: str, input_data: Any = None, **kwargs) -> dict:
        """Run a scoring.py command."""
        logger.info(f"Tool run_scoring: command={command}, kwargs={kwargs}")
        
        try:
            # Build command
            cmd = [sys.executable, str(SCORING_SCRIPT), command]
            
            # Add arguments
            for key, value in kwargs.items():
                if value is not None:
                    cmd.append(f"--{key.replace('_', '-')}")
                    cmd.append(str(value))
            
            # Prepare input
            input_json = json.dumps(input_data) if input_data else None
            
            result = subprocess.run(
                cmd,
                input=input_json,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8"
            )
            
            if result.returncode == 0:
                output = json.loads(result.stdout)
                logger.info(f"Tool run_scoring: success")
                return {"success": True, "data": output}
            else:
                logger.error(f"Tool run_scoring failed: {result.stderr}")
                return {"success": False, "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Scoring timed out after 30s"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse scoring output: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ReadFileTool(AgentTool):
    """Read a file's content."""
    
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Read the content of a file. Use this to read SKILL.md, manifest files, or other files in the skill directory."
        )
    
    def run(self, file_path: str) -> dict:
        """Read a file."""
        logger.info(f"Tool read_file: {file_path}")
        
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}
            
            content = path.read_text(encoding="utf-8")
            logger.info(f"Tool read_file: read {len(content)} characters")
            return {"success": True, "data": {"content": content, "path": str(path)}}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class ListDirectoryTool(AgentTool):
    """List files in a directory."""
    
    def __init__(self):
        super().__init__(
            name="list_directory",
            description="List files and subdirectories in a directory."
        )
    
    def run(self, dir_path: str) -> dict:
        """List directory contents."""
        logger.info(f"Tool list_directory: {dir_path}")
        
        try:
            path = Path(dir_path)
            if not path.exists():
                return {"success": False, "error": f"Directory not found: {dir_path}"}
            
            entries = []
            for entry in path.iterdir():
                entries.append({
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0
                })
            
            logger.info(f"Tool list_directory: found {len(entries)} entries")
            return {"success": True, "data": {"entries": entries, "path": str(path)}}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class GenerateTriggerEvalsTool(AgentTool):
    """Generate trigger evaluation test queries using LLM."""
    
    def __init__(self, llm_agent):
        super().__init__(
            name="generate_trigger_evals",
            description="Generate ~20 test queries (10 should-trigger + 10 should-not-trigger) for evaluating skill trigger accuracy."
        )
        self.llm_agent = llm_agent
    
    def run(self, skill_name: str = "", skill_description: str = "", skill_content: str = "") -> dict:
        """Generate trigger eval queries."""
        logger.info(f"Tool generate_trigger_evals: skill_name={skill_name}")
        
        try:
            evals = self.llm_agent.generate_trigger_evals(
                skill_name=skill_name,
                description=skill_description,
                skill_body=skill_content
            )
            
            if evals:
                logger.info(f"Tool generate_trigger_evals: generated {len(evals)} queries")
                return {"success": True, "data": evals}
            else:
                return {"success": False, "error": "Failed to generate trigger evals"}
                
        except Exception as e:
            logger.error(f"Tool generate_trigger_evals failed: {e}")
            return {"success": False, "error": str(e)}


class EvaluateTriggerQueryTool(AgentTool):
    """Evaluate a single query against a skill's trigger."""
    
    def __init__(self, llm_agent):
        super().__init__(
            name="evaluate_trigger_query",
            description="Evaluate if a user query would trigger a specific skill. Returns {triggered: true/false}."
        )
        self.llm_agent = llm_agent
    
    def run(self, query: str = "", skill_name: str = "", skill_description: str = "") -> dict:
        """Evaluate a single query."""
        logger.info(f"Tool evaluate_trigger_query: query={query[:50]}...")
        
        try:
            # Read the prompt template
            prompt_template = (PROMPTS_DIR / "trigger_eval_prompt.md").read_text(encoding="utf-8")
            
            # Fill in the template
            prompt = prompt_template.format(
                skill_name=skill_name,
                skill_description=skill_description,
                query=query
            )
            
            # Call LLM
            messages = [{"role": "user", "content": prompt}]
            result = self.llm_agent._call_model(messages)
            
            if result:
                # Parse JSON response
                if isinstance(result, str):
                    result = json.loads(result)
                
                logger.info(f"Tool evaluate_trigger_query: triggered={result.get('triggered')}")
                return {"success": True, "data": result}
            else:
                return {"success": False, "error": "LLM returned empty response"}
                
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse LLM response as JSON: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class AnalyzeEnvironmentTool(AgentTool):
    """Analyze skill's environment dependencies."""
    
    def __init__(self):
        super().__init__(
            name="analyze_environment",
            description="Analyze SKILL.md content to identify environment dependencies (tools, capabilities, external services, implicit assumptions)."
        )
    
    def run(self, skill_content: str, environment_context: str = "") -> dict:
        """Analyze environment dependencies."""
        logger.info(f"Tool analyze_environment: analyzing skill content")
        
        try:
            dependencies = []
            
            # Simple pattern matching for common dependencies
            skill_lower = skill_content.lower()
            
            # Tool dependencies
            tool_patterns = {
                "bash": ["bash", "shell", "command line", "terminal"],
                "file_system": ["read", "write", "file", "directory", "path"],
                "http": ["http", "curl", "fetch", "api", "request"],
                "git": ["git", "commit", "push", "pull", "repository"],
                "python": ["python", "pip", "pytest", "unittest"],
                "node": ["node", "npm", "yarn", "package.json"],
            }
            
            for tool_name, patterns in tool_patterns.items():
                for pattern in patterns:
                    if pattern in skill_lower:
                        dependencies.append({
                            "category": "tool",
                            "name": tool_name,
                            "description": f"Requires {tool_name} capability",
                            "evidence": f"Found pattern '{pattern}' in skill content",
                            "compatibility": "compatible",  # Assume compatible by default
                            "reason": f"Pattern '{pattern}' detected"
                        })
                        break  # Only add once per tool
            
            # Capability dependencies
            if "user" in skill_lower and ("choice" in skill_lower or "select" in skill_lower):
                dependencies.append({
                    "category": "capability",
                    "name": "user_choices",
                    "description": "Requires presenting options to user",
                    "evidence": "Found user choice/selection patterns",
                    "compatibility": "adaptable",
                    "reason": "Has structured clarification capability"
                })
            
            # External service dependencies
            if "api" in skill_lower or "endpoint" in skill_lower:
                dependencies.append({
                    "category": "external_service",
                    "name": "api_access",
                    "description": "Requires external API access",
                    "evidence": "Found API/endpoint references",
                    "compatibility": "unknown",
                    "reason": "Cannot determine API availability without more context"
                })
            
            # Remove duplicates
            seen = set()
            unique_deps = []
            for dep in dependencies:
                key = (dep["category"], dep["name"])
                if key not in seen:
                    seen.add(key)
                    unique_deps.append(dep)
            
            logger.info(f"Tool analyze_environment: found {len(unique_deps)} dependencies")
            return {"success": True, "data": {"dependencies": unique_deps}}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class WriteFileTool(AgentTool):
    """Write content to a file."""
    
    def __init__(self):
        super().__init__(
            name="write_file",
            description="Write content to a file. Use this to save the final check.json report."
        )
    
    def run(self, file_path: str, content: str) -> dict:
        """Write content to a file."""
        logger.info(f"Tool write_file: {file_path}")
        
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            
            logger.info(f"Tool write_file: wrote {len(content)} characters")
            return {"success": True, "data": {"path": str(path), "size": len(content)}}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


def create_default_tools(llm_agent) -> list[AgentTool]:
    """Create the default set of tools for the agent."""
    return [
        ValidateFrontmatterTool(),
        ScoringTool(),
        ReadFileTool(),
        ListDirectoryTool(),
        GenerateTriggerEvalsTool(llm_agent),
        EvaluateTriggerQueryTool(llm_agent),
        AnalyzeEnvironmentTool(),
        WriteFileTool(),
    ]

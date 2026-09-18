"""Skill Checker Agent - 真正的智能体，按照 SKILL.md 指令自主决策."""

import json
import logging
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

import yaml

from ..core.config import settings
from .agent_state import AgentState, StepStatus
from .llm_agent import LlmAgent

logger = logging.getLogger(__name__)

# 加载 skill-checker SKILL.md 作为 Agent 指令
SKILL_CHECKER_DIR = Path(__file__).parent.parent.parent / "skill" / "skill-checker"
SKILL_MD_CONTENT = (SKILL_CHECKER_DIR / "SKILL.md").read_text(encoding="utf-8")
VALIDATE_SCRIPT = SKILL_CHECKER_DIR / "scripts" / "validate.py"
SCORING_SCRIPT = SKILL_CHECKER_DIR / "scripts" / "scoring.py"
TRIGGER_EVAL_PROMPT = (SKILL_CHECKER_DIR / "references" / "prompts" / "trigger_eval_prompt.md").read_text(encoding="utf-8")


class SkillCheckerAgent:
    """
    真正的智能体。
    
    - 有工具可以调用
    - 读 SKILL.md 作为自己的指令
    - LLM 自己决定下一步做什么
    - 根据结果动态调整
    """
    
    def __init__(self, llm_agent: Optional[LlmAgent] = None):
        self.llm_agent = llm_agent or LlmAgent()
        self.max_iterations = 30
        logger.info("SkillCheckerAgent initialized")
    
    async def run(self, skill_id: str, skill_zip_path: str) -> dict:
        """主入口."""
        logger.info(f"[{skill_id}] ========== Agent 启动 ==========")
        
        state = AgentState(skill_id=skill_id, skill_zip_path=skill_zip_path)
        
        try:
            # 先解压，这是固定步骤
            await self._extract_skill(state)
            
            # 进入决策循环，让 LLM 自己决定做什么
            await self._decision_loop(state)
            
            if state.trace_report:
                logger.info(f"[{skill_id}] ========== Agent 完成 ==========")
                return state.trace_report
            else:
                logger.error(f"[{skill_id}] Agent 完成但无报告")
                return {"error": "No report", "state": state.to_dict()}
                
        except Exception as e:
            logger.error(f"[{skill_id}] Agent 失败: {e}", exc_info=True)
            return {"error": str(e), "state": state.to_dict()}
    
    async def _extract_skill(self, state: AgentState):
        """解压 ZIP."""
        logger.info(f"[{state.skill_id}] 解压 skill ZIP")
        
        work_dir = Path(settings.storage_dir) / state.skill_id / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(state.skill_zip_path, 'r') as zip_ref:
            for info in zip_ref.infolist():
                if '..' in info.filename or info.filename.startswith('/'):
                    raise ValueError(f"ZIP contains unsafe path: {info.filename}")
            zip_ref.extractall(work_dir)
        
        # 找 SKILL.md
        skill_md = None
        for path in work_dir.rglob("SKILL.md"):
            skill_md = path
            break
        
        if not skill_md:
            raise ValueError("No SKILL.md found in uploaded ZIP")
        
        state.skill_md_path = str(skill_md)
        state.skill_content = skill_md.read_text(encoding="utf-8")
        
        # 提取 frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---', state.skill_content, re.DOTALL)
        if fm_match:
            fm = yaml.safe_load(fm_match.group(1))
            if isinstance(fm, dict):
                state.skill_name = fm.get("name")
                state.skill_description = fm.get("description")
        
        if not state.skill_name:
            state.skill_name = skill_md.parent.name or "unknown"
        
        logger.info(f"[{state.skill_id}] 解压完成: name={state.skill_name}")
        state.record_step("extract", StepStatus.COMPLETED)
    
    async def _decision_loop(self, state: AgentState):
        """决策循环：LLM 自己决定下一步."""
        logger.info(f"[{state.skill_id}] 进入决策循环")
        
        for iteration in range(self.max_iterations):
            logger.info(f"[{state.skill_id}] === 迭代 {iteration + 1} ===")
            
            # 构建上下文
            context = self._build_context(state)
            
            # 让 LLM 决定
            decision = self._get_llm_decision(context, state)
            
            action = decision.get("action", "error")
            tool_name = decision.get("tool", "")
            args = decision.get("args", {})
            reasoning = decision.get("reasoning", "")
            
            logger.info(f"[{state.skill_id}] LLM 决定: tool={tool_name}, reasoning={reasoning[:100]}")
            
            if action == "complete":
                # 防护：没评测完不允许 complete
                if state.evals and len(state.trigger_results) < len(state.evals):
                    logger.warning(f"[{state.skill_id}] 评测未完成 ({len(state.trigger_results)}/{len(state.evals)})，不允许 complete")
                    state.add_conversation("system", f"评测未完成，还需评测 {len(state.evals) - len(state.trigger_results)} 条。请调用 evaluate_trigger。")
                    continue
                logger.info(f"[{state.skill_id}] LLM 决定完成")
                break
            
            if action == "error":
                logger.warning(f"[{state.skill_id}] LLM 报错: {decision.get('error')}")
                state.add_conversation("system", f"Error: {decision.get('error')}")
                continue
            
            # 防护：有 evals 但没评测完时，不允许调 scoring/complete（但允许 analyze_environment）
            if state.evals and len(state.trigger_results) < len(state.evals) and tool_name in ("scoring", "complete"):
                logger.warning(f"[{state.skill_id}] 评测未完成，强制调用 evaluate_trigger 而不是 {tool_name}")
                tool_name = "evaluate_trigger"
                args = {}
            
            # 防护：没有 evals 时不能调 evaluate_trigger
            if not state.evals and tool_name == "evaluate_trigger":
                logger.warning(f"[{state.skill_id}] 没有测试集，强制调用 generate_trigger_evals")
                tool_name = "generate_trigger_evals"
                args = {}
            
            # 执行工具
            result = self._execute_tool(tool_name, args, state)
            
            # 更新状态
            self._update_state(state, tool_name, result, args)
            
            # 记录到对话历史
            if result.get("success"):
                state.add_conversation("tool", f"{tool_name} 成功: {json.dumps(result.get('data', {}), ensure_ascii=False)[:300]}")
            else:
                state.add_conversation("tool", f"{tool_name} 失败: {result.get('error')}")
        
        logger.info(f"[{state.skill_id}] 决策循环结束")
    
    def _build_context(self, state: AgentState) -> str:
        """构建 LLM 决策上下文."""
        # 构建对话历史
        history = ""
        if state.conversation:
            recent = state.conversation[-10:]  # 最近 10 条
            history = "\n\n最近操作记录:\n"
            for msg in recent:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "tool":
                    # 截取重要信息
                    if len(content) > 500:
                        content = content[:500] + "..."
                    history += f"工具结果: {content}\n"
        
        return f"""你是 skill 验证智能体。根据当前状态决定下一步。

当前状态:
- Skill Name: {state.skill_name}
- Skill 目录: {Path(state.skill_md_path).parent}
- 已完成步骤: {state.get_completed_steps()}
- Frontmatter 已校验: {state.frontmatter_valid}
- 测试集数量: {len(state.evals)}
- 已评测数量: {len(state.trigger_results)}
- 环境依赖数量: {len(state.env_dependencies)}
- 报告已生成: {state.trace_report is not None}
{history}

## 核心工具（必须掌握）
1. bash(command="...") - 执行 shell 命令
   - 用法: bash(command="ls -la") 或 bash(command="python scripts/validate.py SKILL.md")
2. read_file(file_path="...") - 读取文件内容
   - 用法: read_file(file_path="SKILL.md") 或 read_file(file_path="scripts/validate.py")
3. list_directory(dir_path="...") - 列出目录结构
   - 用法: list_directory(dir_path=".") 或 list_directory(dir_path="scripts")
4. write_file(file_path="...", content="...") - 写入文件
   - 用法: write_file(file_path="test_data.json", content='{{"key": "value"}}')

## Skill 验证工具
5. validate_frontmatter - 校验 frontmatter
6. generate_trigger_evals - 发现脚本并创建测试数据
7. evaluate_trigger(batch=true) - 执行所有测试用例并检查输出
8. analyze_environment - 分析环境依赖
9. scoring - 合并报告

## 工作流程（真实执行模式）
1. list_directory 查看 skill 目录结构
2. read_file 读取 SKILL.md 理解功能
3. read_file 读取 scripts/ 中的脚本，理解输入格式
4. generate_trigger_evals 自动发现脚本并创建测试数据
5. evaluate_trigger(batch=true) 执行所有测试，检查输出
6. analyze_environment 分析环境依赖
7. scoring 合并报告

**重要**: 必须真正执行脚本，不能只问 LLM 会不会触发！

返回 JSON: {{"action": "tool", "tool": "工具名", "args": {{}}}} 或 {{"action": "complete"}}"""
    
    def _get_llm_decision(self, context: str, state: AgentState) -> dict:
        """让 LLM 决定下一步."""
        messages = [
            {"role": "system", "content": "你是 skill 验证智能体。只返回 JSON，不要其他文字。"},
            {"role": "user", "content": context}
        ]
        
        try:
            response = self.llm_agent._call_model(messages)
            logger.info(f"[{state.skill_id}] LLM 原始响应: {response[:500] if response else 'None'}")
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"LLM 决策失败: {e}")
            return {"action": "error", "error": str(e)}
    
    def _parse_json_response(self, response: str) -> dict:
        """解析 LLM 的 JSON 响应."""
        if isinstance(response, dict):
            return response
        
        if not response:
            return {"action": "error", "error": "Empty response"}
        
        # 尝试直接解析整个响应
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                if "action" in parsed:
                    return parsed
                elif "tool" in parsed:
                    parsed["action"] = "tool"
                    return parsed
        except:
            pass
        
        # 尝试用正则提取 JSON 块（支持嵌套）
        for match in re.finditer(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL):
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict) and ("action" in parsed or "tool" in parsed):
                    return parsed
            except:
                continue
        
        # 尝试从文本中提取 tool 名称（容错模式）
        tool_match = re.search(r'"tool"\s*:\s*"(\w+)"', response)
        action_match = re.search(r'"action"\s*:\s*"(\w+)"', response)
        
        if tool_match or action_match:
            tool = tool_match.group(1) if tool_match else ""
            action = action_match.group(1) if action_match else "tool"
            args_match = re.search(r'"args"\s*:\s*(\{[^}]*\})', response)
            reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', response)
            
            return {
                "action": action if action in ("tool", "complete", "error") else "tool",
                "tool": tool,
                "args": json.loads(args_match.group(1)) if args_match else {},
                "reasoning": reasoning_match.group(1) if reasoning_match else ""
            }
        
        # 最后尝试：直接匹配自然语言中的工具名
        natural_tools = {
            "validate_frontmatter": "validate_frontmatter",
            "generate_trigger_evals": "generate_trigger_evals",
            "evaluate_trigger": "evaluate_trigger",
            "analyze_environment": "analyze_environment",
            "scoring": "scoring",
        }
        for keyword, tool_name in natural_tools.items():
            if keyword in response.lower():
                return {"action": "tool", "tool": tool_name, "args": {}, "reasoning": response[:200]}
        
        return {"action": "error", "error": f"Failed to parse: {response[:200]}"}
    
    def _execute_tool(self, tool_name: str, args: dict, state: AgentState) -> dict:
        """执行工具."""
        logger.info(f"[{state.skill_id}] 执行工具: {tool_name}")
        
        try:
            # 核心 agent 工具
            if tool_name == "bash":
                return self._tool_bash(args, state)
            elif tool_name == "read_file":
                return self._tool_read_file(args, state)
            elif tool_name == "list_directory":
                return self._tool_list_directory(args, state)
            elif tool_name == "write_file":
                return self._tool_write_file(args, state)
            # skill 验证工具
            elif tool_name == "validate_frontmatter":
                return self._tool_validate_frontmatter(args, state)
            elif tool_name == "generate_trigger_evals":
                return self._tool_generate_trigger_evals(args, state)
            elif tool_name == "evaluate_trigger":
                return self._tool_evaluate_trigger(args, state)
            elif tool_name == "analyze_environment":
                return self._tool_analyze_environment(args, state)
            elif tool_name == "scoring":
                return self._tool_scoring(args, state)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _tool_bash(self, args: dict, state: AgentState) -> dict:
        """执行 shell 命令."""
        command = args.get("command", "")
        if not command:
            return {"success": False, "error": "command is required"}
        
        # 安全限制：不允许危险命令
        dangerous_commands = ["rm -rf /", "format", "del /s /q", "shutdown", "reboot"]
        for dangerous in dangerous_commands:
            if dangerous in command.lower():
                return {"success": False, "error": f"Dangerous command blocked: {dangerous}"}
        
        # 规范化路径：避免 Windows 长路径问题
        command = command.replace("\\\\", "\\").replace("//", "/")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
                cwd=str(Path(state.skill_md_path).parent)
            )
            
            return {
                "success": True,
                "data": {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out after 60 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _tool_read_file(self, args: dict, state: AgentState) -> dict:
        """读取文件内容."""
        file_path = args.get("file_path", "")
        if not file_path:
            return {"success": False, "error": "file_path is required"}
        
        # 解析相对于 skill 目录的路径
        skill_dir = Path(state.skill_md_path).parent
        full_path = skill_dir / file_path if not os.path.isabs(file_path) else Path(file_path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"success": True, "data": {"content": content, "path": str(full_path)}}
        except Exception as e:
            return {"success": False, "error": f"Cannot read file: {e}"}
    
    def _tool_list_directory(self, args: dict, state: AgentState) -> dict:
        """列出目录内容."""
        dir_path = args.get("dir_path", ".")
        skill_dir = Path(state.skill_md_path).parent
        full_path = skill_dir / dir_path if not os.path.isabs(dir_path) else Path(dir_path)
        
        try:
            items = []
            for item in sorted(full_path.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0
                })
            return {"success": True, "data": {"items": items, "path": str(full_path)}}
        except Exception as e:
            return {"success": False, "error": f"Cannot list directory: {e}"}
    
    def _tool_write_file(self, args: dict, state: AgentState) -> dict:
        """写入文件."""
        file_path = args.get("file_path", "")
        content = args.get("content", "")
        if not file_path:
            return {"success": False, "error": "file_path is required"}
        
        skill_dir = Path(state.skill_md_path).parent
        full_path = skill_dir / file_path if not os.path.isabs(file_path) else Path(file_path)
        
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "data": {"path": str(full_path), "bytes_written": len(content)}}
        except Exception as e:
            return {"success": False, "error": f"Cannot write file: {e}"}
    
    def _tool_validate_frontmatter(self, args: dict, state: AgentState) -> dict:
        """校验 frontmatter."""
        skill_md_path = args.get("skill_md_path", state.skill_md_path)
        
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), skill_md_path],
            capture_output=True, text=True, timeout=30, encoding="utf-8"
        )
        
        if result.returncode in (0, 1):
            output = json.loads(result.stdout)
            return {"success": True, "data": output}
        else:
            return {"success": False, "error": result.stderr}
    
    def _tool_generate_trigger_evals(self, args: dict, state: AgentState) -> dict:
        """发现 skill 的脚本并创建测试数据."""
        skill_dir = Path(state.skill_md_path).parent
        
        # 1. 列出完整的 skill 目录结构（递归）
        def list_dir_recursive(path: Path, prefix: str = "", max_depth: int = 3) -> list:
            items = []
            if len(items) > 50:  # 防止过深
                return items
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.'):
                        continue
                    if item.is_dir():
                        items.append(f"{prefix}{item.name}/")
                        if max_depth > 0:
                            items.extend(list_dir_recursive(item, prefix + "  ", max_depth - 1))
                    else:
                        # 标记可能是脚本的文件
                        is_script = item.suffix in ('.py', '.sh', '.js', '.ts', '.rb', '.pl', '.go', '.rs')
                        marker = " [SCRIPT]" if is_script else ""
                        items.append(f"{prefix}{item.name}{marker}")
            except:
                pass
            return items
        
        dir_structure = list_dir_recursive(skill_dir)
        dir_structure_text = "\n".join(dir_structure)
        
        # 2. 让 LLM 分析目录结构，找出可执行脚本
        skill_content = state.skill_content[:2000] if state.skill_content else ""
        
        prompt = f"""分析以下 skill 的目录结构，找出所有可执行的脚本文件。

**目录结构**:
{dir_structure_text}

**SKILL.md 内容**:
{skill_content}

**判断规则**:
1. 脚本可能是 .py, .sh, .js, .ts, .rb, .pl, .go, .rs 等文件
2. 脚本可能在任何目录下：scripts/, src/, bin/, lib/, 或直接在根目录
3. 脚本可能有依赖（如 requirements.txt, package.json）
4. 如果 SKILL.md 声明了使用方式（如 `python script.py --arg`），优先测试这些

**请返回**:
```json
{{
  "scripts": [
    {{
      "path": "相对于 skill 目录的路径",
      "type": "py/sh/js/等",
      "purpose": "脚本用途",
      "test_command": "建议的测试命令"
    }}
  ],
  "has_scripts": true/false,
  "reason": "判断依据"
}}
```"""
        
        messages = [{"role": "user", "content": prompt}]
        llm_result = self.llm_agent._call_model(messages)
        
        logger.info(f"generate_trigger_evals LLM 原始响应: {llm_result}")
        
        # 解析结果
        scripts = []
        has_scripts = False
        if isinstance(llm_result, dict):
            scripts = llm_result.get("scripts", [])
            has_scripts = llm_result.get("has_scripts", len(scripts) > 0)
        elif isinstance(llm_result, str):
            import re
            # 尝试解析 JSON
            json_match = re.search(r'\{.*\}', llm_result, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    scripts = parsed.get("scripts", [])
                    has_scripts = parsed.get("has_scripts", len(scripts) > 0)
                except:
                    pass
            if not has_scripts:
                match = re.search(r'"has_scripts"\s*:\s*(true|false)', llm_result, re.IGNORECASE)
                if match:
                    has_scripts = match.group(1).lower() == "true"
        
        logger.info(f"generate_trigger_evals 解析结果: scripts={len(scripts)}, has_scripts={has_scripts}")
        
        # 如果没有脚本，跳过触发测试
        if not has_scripts:
            state.evals = []
            return {"success": True, "data": {
                "dir_structure": dir_structure_text,
                "scripts": [],
                "test_cases": [],
                "note": "无脚本 skill，跳过触发测试",
                "trigger_status": "skipped"
            }}
        
        # 3. 读取脚本内容，生成测试用例
        script_contents = []
        for script in scripts[:5]:
            script_path = skill_dir / script.get("path", "")
            if script_path.exists():
                try:
                    content = script_path.read_text(encoding='utf-8')[:2000]
                    script_contents.append({
                        "path": script.get("path"),
                        "content": content
                    })
                except:
                    pass
        
        # 4. 让 LLM 根据脚本内容生成测试数据
        prompt = f"""分析以下脚本内容，为每个脚本创建测试数据。

**重要规则**:
1. 命令行参数必须使用**连字符**（如 --output-dir），不是下划线（--output_dir）
2. **必须从脚本源码中读取 argparse 定义**，确定每个子命令的参数格式
3. 如果脚本用的是位置参数（如 `image "prompt"`），不要改成命名参数
4. 仔细阅读 add_argument() 调用，确定参数是 positional 还是 optional
5. **测试命令必须使用完整路径**，格式: `python <skill_dir>/path/to/script.py`

**SKILL 目录**: {skill_dir}

**脚本内容**:
{json.dumps(script_contents, ensure_ascii=False, indent=2)}

**SKILL.md**:
{skill_content}

请为每个脚本创建测试数据，格式如下:
```json
{{
  "test_cases": [
    {{
      "script": "脚本路径（相对于 skill 目录）",
      "description": "测试目的",
      "command": "python E:\\\\path\\\\to\\\\skill\\\\scripts\\\\xxx.py arg1 --flag value",
      "expected_output_contains": "期望输出中的关键字"
    }}
  ]
}}
```

**注意**: command 中的路径必须是完整绝对路径，不能用相对路径！

只返回 JSON，不要其他内容。"""
        
        messages = [{"role": "user", "content": prompt}]
        llm_result = self.llm_agent._call_model(messages)
        
        # 解析测试用例
        test_cases = []
        if isinstance(llm_result, dict):
            test_cases = llm_result.get("test_cases", [])
        elif isinstance(llm_result, str):
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_result, re.DOTALL)
            if json_match:
                try:
                    test_cases = json.loads(json_match.group(1)).get("test_cases", [])
                except:
                    pass
        
        state.evals = test_cases
        return {"success": True, "data": {
            "dir_structure": dir_structure_text,
            "scripts": scripts,
            "test_cases": test_cases
        }}
    
    def _tool_evaluate_trigger(self, args: dict, state: AgentState) -> dict:
        """执行测试用例并检查输出."""
        skill_dir = Path(state.skill_md_path).parent
        batch = args.get("batch", False)
        
        # 获取待执行的测试用例
        if batch:
            test_cases = state.evals
        else:
            # 单条模式
            script_name = args.get("script", "")
            test_cases = [tc for tc in state.evals if tc.get("script") == script_name]
            if not test_cases and state.evals:
                # 取第一个未执行的
                executed = {r.get("script") for r in state.trigger_results}
                test_cases = [tc for tc in state.evals if tc.get("script") not in executed][:1]
        
        results = []
        for tc in test_cases:
            script = tc.get("script", "")
            command = tc.get("command", "")
            expected = tc.get("expected_output_contains", "")
            
            if not command:
                # 构建默认命令
                input_file = tc.get("input_file", "test_input.json")
                command = f"python scripts/{script} --input {input_file}"
            
            # 规范化命令：确保使用相对路径
            # 移除命令中可能包含的绝对路径前缀
            command = command.replace("\\\\", "\\").replace("//", "/")
            
            # 执行脚本 - 使用相对路径和 cwd
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(skill_dir),
                    encoding='utf-8',
                    errors='replace'
                )
                
                stdout = result.stdout
                stderr = result.stderr
                returncode = result.returncode
                
                # 让 LLM 判断脚本是否通过
                judgment_prompt = f"""分析以下脚本执行结果，判断是否通过测试。

脚本: {script}
命令: {command}
退出码: {returncode}
stdout: {stdout[:1000]}
stderr: {stderr[:1000]}

判断规则：
1. 退出码非0 → 失败
2. 输出包含"成功"、"✅"、"generated"等成功标志 → 通过
3. 输出包含"失败"、"❌"、"error"、"exception"等失败标志 → 失败
4. 命令参数错误（unrecognized arguments）→ 失败
5. 文件不存在（can't open file）→ 失败

只返回 JSON: {{"passed": true/false, "reason": "简短原因"}}"""
                
                messages = [{"role": "user", "content": judgment_prompt}]
                judgment = self.llm_agent._call_model(messages)
                
                # 解析判断结果
                passed = returncode == 0  # 默认按退出码
                reason = ""
                if isinstance(judgment, dict):
                    passed = judgment.get("passed", returncode == 0)
                    reason = judgment.get("reason", "")
                elif isinstance(judgment, str):
                    # 尝试从文本提取
                    match = re.search(r'"passed"\s*:\s*(true|false)', judgment, re.IGNORECASE)
                    if match:
                        passed = match.group(1).lower() == "true"
                
                results.append({
                    "script": script,
                    "command": command,
                    "success": returncode == 0,
                    "passed": passed,
                    "stdout": stdout[:500],
                    "stderr": stderr[:500],
                    "expected": expected,
                    "judgment_reason": reason
                })
                
                logger.info(f"[{state.skill_id}] 执行 {script}: {'PASS' if passed else 'FAIL'}")
                
            except subprocess.TimeoutExpired:
                results.append({
                    "script": script,
                    "command": command,
                    "success": False,
                    "passed": False,
                    "error": "Timeout after 30s"
                })
            except Exception as e:
                results.append({
                    "script": script,
                    "command": command,
                    "success": False,
                    "passed": False,
                    "error": str(e)
                })
        
        return {"success": True, "data": {"results": results, "count": len(results)}}
        
        if not query:
            return {"success": True, "data": {"triggered": False, "query": "", "note": "no more queries to evaluate"}}
        
        skill_name = args.get("skill_name", state.skill_name)
        skill_description = args.get("skill_description", state.skill_description)
        
        prompt = TRIGGER_EVAL_PROMPT.replace("{skill_name}", skill_name).replace("{skill_description}", skill_description).replace("{query}", query)
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_agent._call_model(messages)
        
        # 解析 triggered
        triggered = False
        if isinstance(response, dict):
            triggered = response.get("triggered", False)
        elif isinstance(response, str):
            # 尝试多种格式
            match = re.search(r'"triggered"\s*:\s*(true|false)', response, re.IGNORECASE)
            if match:
                triggered = match.group(1).lower() == "true"
            elif "true" in response.lower() and "false" not in response.lower():
                triggered = True
            elif "false" in response.lower() and "true" not in response.lower():
                triggered = False
        
        return {"success": True, "data": {"triggered": triggered, "query": query}}
    
    def _tool_analyze_environment(self, args: dict, state: AgentState) -> dict:
        """用 LLM 深度分析环境依赖，同时验证脚本是否存在."""
        skill_content = args.get("skill_content", state.skill_content)
        skill_name = state.skill_name or "unknown"
        skill_description = state.skill_description or ""
        
        # 先列出 skill 目录下的所有文件
        skill_dir = Path(state.skill_md_path).parent
        actual_files = []
        try:
            for item in skill_dir.rglob("*"):
                if item.is_file():
                    rel_path = str(item.relative_to(skill_dir))
                    actual_files.append(rel_path)
        except Exception as e:
            logger.warning(f"无法列出 skill 目录: {e}")
        
        files_list = "\n".join(actual_files) if actual_files else "无法获取文件列表"
        
        prompt = f"""你是一个 skill 验证专家。请完成以下两项任务：

## 任务 1: 验证脚本是否存在且已实现

Skill 名称: {skill_name}
Skill 描述: {skill_description}

SKILL.md 内容:
{skill_content[:3000]}

Skill 目录下的实际文件:
{files_list}

请对比 SKILL.md 声称的功能/脚本 vs 实际文件，找出：
- 声称但不存在的脚本
- 存在但未实现的脚本（空文件、placeholder）
- 声称但未导入的依赖（如 jinja2, requests）
- 声称但不支持的参数（如 --template）

## 任务 2: 分析环境依赖

基于 SKILL.md 内容，分析所有环境依赖：

### 依赖分类 (category)
- tool: 工具依赖 (bash, python, git, http 等)
- capability: 能力依赖 (文件读写, 用户交互等)
- external_service: 外部服务依赖 (API, 模板引擎等)

### 兼容性判断 (compatibility)
- compatible: 当前环境完全支持
- adaptable: 需要适配/修改才能使用
- incompatible: 当前环境不支持，无法使用

### 输出格式
返回 JSON 对象：
```json
{{
  "claimed_features": ["声称的功能1", "声称的功能2"],
  "actual_scripts": ["实际存在的脚本1", "实际存在的脚本2"],
  "missing_scripts": ["声称但不存在的脚本"],
  "unimplemented_features": ["声称但未实现的功能"],
  "trust_issues": ["所有发现的问题"],
  "dependencies": [
    {{
      "category": "tool|capability|external_service",
      "name": "依赖名称",
      "description": "详细描述",
      "evidence": "SKILL.md 中的证据",
      "compatibility": "compatible|adaptable|incompatible",
      "reason": "判断理由",
      "adaptation": {{
        "target_capability": "目标能力",
        "strategy": "replace|wrap|extend",
        "description": "适配方案",
        "changes": ["修改建议"]
      }}
    }}
  ]
}}
```

只返回 JSON，不要其他文字。"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_agent._call_model(messages)
        
        # 解析 JSON
        try:
            if isinstance(response, dict):
                result = response
            else:
                # 尝试提取 JSON
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                else:
                    result = {}
        except:
            result = {}
        
        # 提取依赖列表
        dependencies = result.get("dependencies", [])
        if not dependencies:
            dependencies = self._fallback_env_analysis(skill_content)
        
        # 提取脚本验证信息
        script_verification = {
            "claimed_features": result.get("claimed_features", []),
            "actual_scripts": result.get("actual_scripts", []),
            "missing_scripts": result.get("missing_scripts", []),
            "unimplemented_features": result.get("unimplemented_features", []),
            "trust_issues": result.get("trust_issues", [])
        }
        
        return {"success": True, "data": {
            "dependencies": dependencies,
            "script_verification": script_verification
        }}
    
    def _fallback_env_analysis(self, skill_content: str) -> list:
        """备用环境分析（关键词匹配）."""
        dependencies = []
        skill_lower = skill_content.lower()
        
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
                        "evidence": f"Found pattern '{pattern}'",
                        "compatibility": "compatible",
                        "reason": f"Pattern '{pattern}' detected"
                    })
                    break
        
        return dependencies
    
    def _tool_scoring(self, args: dict, state: AgentState) -> dict:
        """调用 scoring.py."""
        command = args.get("command", "merge")
        
        # 准备输入数据
        if command == "merge":
            input_data = {
                "skill_name": state.skill_name or "unknown",
                "trigger": {
                    "results": state.trigger_results,
                    "summary": state.trigger_summary or {},
                    "description": state.skill_description or ""
                } if state.trigger_results else None,
                "environment": {
                    "dependencies": state.env_dependencies,
                    "summary": state.env_summary or {}
                } if state.env_dependencies else None
            }
        elif command == "eval-summary":
            input_data = args.get("items", state.trigger_results)
        elif command == "env-summary":
            input_data = {"dependencies": state.env_dependencies}
        else:
            input_data = args.get("input_data", {})
        
        # 构建命令行
        cmd = [sys.executable, str(SCORING_SCRIPT), command]
        for key, value in args.items():
            if key not in ("command", "input_data", "items") and value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        
        result = subprocess.run(
            cmd,
            input=json.dumps(input_data),
            capture_output=True, text=True, timeout=30, encoding="utf-8"
        )
        
        if result.returncode == 0:
            output = json.loads(result.stdout)
            return {"success": True, "data": output}
        else:
            return {"success": False, "error": result.stderr}
    
    def _update_state(self, state: AgentState, tool_name: str, result: dict, args: dict):
        """根据工具结果更新状态."""
        if not result.get("success"):
            return
        
        data = result.get("data", {})
        
        if tool_name == "validate_frontmatter":
            state.frontmatter_valid = data.get("valid", False)
            state.frontmatter_warnings = sum(1 for i in data.get("issues", []) if i.get("severity") == "warn")
            state.record_step("validate", StepStatus.COMPLETED)
            
        elif tool_name == "generate_trigger_evals":
            state.evals = data.get("test_cases", [])
            state.record_step("generate_evals", StepStatus.COMPLETED)
            
        elif tool_name == "evaluate_trigger":
            # 处理脚本执行结果
            if "results" in data:
                batch_results = data["results"]
                for item in batch_results:
                    state.trigger_results.append({
                        "script": item.get("script", ""),
                        "command": item.get("command", ""),
                        "success": item.get("success", False),
                        "passed": item.get("passed", False),
                        "stdout": item.get("stdout", "")[:200],
                        "stderr": item.get("stderr", "")[:200],
                        "expected": item.get("expected", ""),
                        "error": item.get("error", "")
                    })
                logger.info(f"[{state.skill_id}] evaluate_trigger batch: {len(batch_results)} scripts executed")
            
            # 更新 summary
            if state.trigger_results:
                passed = sum(1 for r in state.trigger_results if r.get("passed", False))
                total = len(state.trigger_results)
                state.trigger_summary = {
                    "total": total,
                    "passed": passed,
                    "failed": total - passed,
                    "pass_rate": round(passed / total, 4) if total > 0 else 0
                }
            
            state.record_step("trigger_eval", StepStatus.COMPLETED)
            
        elif tool_name == "analyze_environment":
            state.env_dependencies = data.get("dependencies", [])
            
            # 保存脚本验证信息
            script_verification = data.get("script_verification", {})
            
            # 计算 env_summary
            compatible = sum(1 for d in state.env_dependencies if d.get("compatibility") == "compatible")
            adaptable = sum(1 for d in state.env_dependencies if d.get("compatibility") == "adaptable")
            incompatible = sum(1 for d in state.env_dependencies if d.get("compatibility") == "incompatible")
            total = len(state.env_dependencies)
            
            blocking_issues = [d["name"] for d in state.env_dependencies if d.get("compatibility") == "incompatible"]
            adaptations_available = [d["name"] for d in state.env_dependencies if d.get("compatibility") == "adaptable"]
            
            # 加入脚本验证的阻塞问题
            missing_scripts = script_verification.get("missing_scripts", [])
            unimplemented = script_verification.get("unimplemented_features", [])
            blocking_issues.extend(missing_scripts)
            blocking_issues.extend(unimplemented)
            
            fitness_score = round((compatible + adaptable * 0.5) / total, 4) if total > 0 else 1.0
            
            state.env_summary = {
                "total": total,
                "compatible": compatible,
                "adaptable": adaptable,
                "incompatible": incompatible,
                "blocking_issues": blocking_issues,
                "adaptations_available": adaptations_available,
                "fitness_score": fitness_score,
                "script_verification": script_verification
            }
            
            state.record_step("env_scan", StepStatus.COMPLETED)
            
        elif tool_name == "scoring":
            # scoring 默认执行 merge
            command = args.get("command", "merge")
            if command == "merge":
                state.trace_report = data
                state.record_step("merge_report", StepStatus.COMPLETED)
    
    def _extract_json_list(self, text: str) -> list:
        """从文本中提取 JSON 数组."""
        if isinstance(text, list):
            return text
        
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return []

"""Provider-agnostic LLM client used to generate skill test plans."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import httpx
from ..core.config import settings


class LlmAgent:
    """Generate JSON test plans through the configured LLM provider."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.provider = settings.llm_provider.lower()

    def _build_messages(self, manifest: dict, triggers: Optional[list]) -> List[Dict[str, str]]:
        system = (
            "你是一个测试智能体。你的目标是生成一个 JSON 测试计划（仅输出 JSON 或至少包含一个有效 JSON 对象）。"
            "生成 actions 列表：每项包含 id、type(http|command)、method、url(或 command)、json(可选)、expected(断言)、rationale。"
            "禁止访问私有网络。"
        )
        summary = {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "entrypoint": manifest.get("entrypoint"),
            "triggers": triggers or [],
        }
        user = (
            f"manifest: {json.dumps(summary, ensure_ascii=False)}\n"
            "请基于 manifest 和 triggers 生成测试计划 JSON（actions 列表）示例。"
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract the first decodable JSON object from a model response."""
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise ValueError("no JSON object found")

    def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OpenAI API key not configured")
        # Use the HTTP API directly so this works with both current and legacy SDK installs.
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0.2, "max_tokens": 800},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _response_text(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text
        if isinstance(body, dict):
            return body.get("completion") or body.get("text") or body.get("response") or response.text
        return response.text

    def _call_prompt_endpoint(self, url: str, prompt: str, headers: Optional[dict] = None, timeout: int = 30) -> str:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json={"prompt": prompt}, headers=headers)
            response.raise_for_status()
            return self._response_text(response)

    def _call_deepseek(self, prompt: str) -> str:
        url = settings.deepseek_url or os.getenv("DEEPSEEK_URL")
        api_key = settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        if not url:
            raise RuntimeError("DeepSeek URL not configured")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        return self._call_prompt_endpoint(url, prompt, headers)

    def _call_anthropic(self, prompt: str) -> str:
        url = settings.anthropic_url or os.getenv("ANTHROPIC_URL") or "https://api.anthropic.com/v1/complete"
        api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Anthropic API key not configured")
        payload = {"prompt": prompt, "model": self.model, "max_tokens_to_sample": 800}
        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload, headers={"x-api-key": api_key, "Content-Type": "application/json"})
            response.raise_for_status()
            return self._response_text(response)

    def _call_azure(self, messages: List[Dict[str, str]]) -> str:
        base = settings.azure_api_base or os.getenv("AZURE_API_BASE")
        key = settings.azure_api_key or os.getenv("AZURE_API_KEY")
        deployment = settings.azure_deployment or os.getenv("AZURE_DEPLOYMENT")
        if not (base and key and deployment):
            raise RuntimeError("Azure OpenAI config missing")
        url = f"{base.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version=2023-10-01"
        with httpx.Client(timeout=30) as client:
            response = client.post(url, json={"messages": messages, "max_tokens": 800}, headers={"api-key": key})
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    def _call_local(self, prompt: str) -> str:
        url = settings.local_llm_url or os.getenv("LOCAL_LLM_URL")
        if not url:
            raise RuntimeError("Local LLM URL not configured")
        return self._call_prompt_endpoint(url, prompt, timeout=60)

    def _call_model(self, messages: List[Dict[str, str]]) -> str:
        """Send one agent task to the configured provider."""
        prompt = messages[-1]["content"]
        if self.provider == "openai":
            return self._call_openai(messages)
        if self.provider == "deepseek":
            return self._call_deepseek(prompt)
        if self.provider == "anthropic":
            return self._call_anthropic(prompt)
        if self.provider == "azure":
            return self._call_azure(messages)
        if self.provider == "local":
            return self._call_local(prompt)
        raise RuntimeError(f"unsupported LLM provider: {self.provider}")

    def generate_trigger_evals(self, skill_name: str, description: str, skill_body: str) -> list[dict]:
        """Ask the validation agent for the core skill's balanced trigger set."""
        messages = [{
            "role": "system",
            "content": (
                "You are the Skill Checker evaluation agent. Generate exactly 20 realistic user queries "
                "for trigger evaluation: 10 with should_trigger=true and 10 with should_trigger=false. "
                "Negative examples must be close, plausible distractions. Return JSON only: "
                "{\"evals\":[{\"query\":string,\"should_trigger\":boolean}]}"
            ),
        }, {
            "role": "user",
            "content": json.dumps({
                "skill_name": skill_name, "description": description, "skill_body": skill_body[:12000],
            }, ensure_ascii=False),
        }]
        data = self._extract_json(self._call_model(messages))
        evals = data.get("evals")
        if not isinstance(evals, list) or len(evals) != 20:
            raise ValueError("trigger test set must contain exactly 20 queries")
        normalized = []
        for item in evals:
            if not isinstance(item, dict) or not isinstance(item.get("query"), str) or not isinstance(item.get("should_trigger"), bool):
                raise ValueError("invalid trigger test case")
            normalized.append({"query": item["query"], "should_trigger": item["should_trigger"]})
        if sum(item["should_trigger"] for item in normalized) != 10:
            raise ValueError("trigger test set must contain 10 positive and 10 negative queries")
        return normalized

    def evaluate_trigger_queries(self, prompt_template: str, skill_name: str, description: str, evals: list[dict]) -> list[dict]:
        """Execute all trigger decisions with the validation agent in parallel."""
        def evaluate(item: dict) -> dict:
            # The bundled template contains a literal JSON example, so use
            # explicit token replacement instead of ``str.format``.
            prompt = (prompt_template
                      .replace("{skill_name}", skill_name)
                      .replace("{skill_description}", description)
                      .replace("{query}", item["query"]))
            result = self._extract_json(self._call_model([{"role": "user", "content": prompt}]))
            triggered = result.get("triggered")
            if not isinstance(triggered, bool):
                raise ValueError("trigger evaluation must return a boolean 'triggered' field")
            return {**item, "triggered": triggered}

        with ThreadPoolExecutor(max_workers=min(5, len(evals))) as pool:
            return list(pool.map(evaluate, evals))

    def request_test_plan(
        self, manifest: dict, triggers: Optional[list] = None, baseline: Optional[dict] = None, max_retries: int = 2
    ) -> Tuple[dict, str]:
        """Return a validated ``(plan, raw_model_response)`` tuple."""
        messages = self._build_messages(manifest, triggers)
        if baseline:
            summary = {
                "name": baseline.get("name"), "version": baseline.get("version"),
                "entrypoint": baseline.get("entrypoint"), "tests_count": len(baseline.get("tests", []) or []),
            }
            messages.append({"role": "system", "content": "Baseline skill (reference): " + json.dumps(summary, ensure_ascii=False)})

        last_raw = ""
        for _ in range(max_retries + 1):
            raw = self._call_model(messages)
            last_raw = raw
            try:
                plan = self._extract_json(raw)
                if not isinstance(plan.get("actions"), list):
                    raise ValueError("plan must contain an actions list")
                return plan, raw
            except (TypeError, ValueError) as error:
                messages.extend([
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"上一条输出无法解析为合法 JSON: {error}. 请只输出纯 JSON，确保包含 actions 列表。"},
                ])
                time.sleep(0.5)
        raise RuntimeError("LLM 未能生成合法测试计划; 最后输出:\n" + last_raw)

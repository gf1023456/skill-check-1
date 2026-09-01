import os
import json
import re
import time
from typing import Optional, Tuple, Dict, Any, List
import openai
import httpx
from app.core.config import settings

class LlmAgent:
    """
    Supports multiple providers: openai (via openai SDK), deepseek (HTTP), anthropic (HTTP), azure (Azure OpenAI REST), local (custom HTTP).
    request_test_plan(manifest, triggers) -> (plan_dict, raw_text)
    """
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.provider = settings.llm_provider
        # initialize keys
        if self.provider == "openai":
            openai.api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")

    def _build_messages(self, manifest: dict, triggers: Optional[list]):
        system = (
            "你是一个测试智能体。你的目标是生成一个 JSON 测试计划（仅输出 JSON，或至少包含一个有效 JSON 对象）。"
            "生成 actions 列表：每项包含 id,type(http|command), method, url(或 command), json(可选), expected(断言), rationale。"
            "禁止访问私有网络。"
        )
        manifest_summary = {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "entrypoint": manifest.get("entrypoint"),
            "triggers": triggers or []
        }
        user = f"manifest: {json.dumps(manifest_summary, ensure_ascii=False)}\n请基于 manifest 和 triggers 生成测试计划 JSON（actions 列表）示例。"
        return [{"role":"system","content":system},{"role":"user","content":user}]

    def _extract_json(self, text: str):
        # try to locate first balanced JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no json object found")
        candidate = text[start:end+1]
        # try to progressively trim trailing chars until valid
        while candidate:
            try:
                return json.loads(candidate)
            except Exception:
                candidate = candidate[:-1]
        raise ValueError("could not parse json")

    def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        if not (settings.openai_api_key or os.getenv("OPENAI_API_KEY")):
            raise RuntimeError("OpenAI API key not configured")
        resp = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=800
        )
        return resp["choices"][0]["message"]["content"].strip()

    def _call_deepseek(self, prompt: str) -> str:
        url = settings.deepseek_url or os.getenv("DEEPSEEK_URL")
        api_key = settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        if not url:
            raise RuntimeError("Deepseek URL not configured")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json={"prompt": prompt}, headers=headers)
            resp.raise_for_status()
            return resp.text

    def _call_anthropic(self, prompt: str) -> str:
        # Anthropic API expects a prompt and model; this is a simple wrapper
        url = settings.anthropic_url or os.getenv("ANTHROPIC_URL") or "https://api.anthropic.com/v1/complete"
        api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Anthropic API key not configured")
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        payload = {"prompt": prompt, "model": self.model, "max_tokens_to_sample": 800}
        with httpx.Client(timeout=30) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            # try to return text or JSON->text
            try:
                j = r.json()
                # Anthropic returns 'completion' or 'text'
                return j.get("completion") or j.get("text") or r.text
            except Exception:
                return r.text

    def _call_azure(self, messages: List[Dict[str, str]]) -> str:
        # Azure OpenAI REST: POST {azure_base}/openai/deployments/{deployment}/chat/completions?api-version=2023-10-01
        base = settings.azure_api_base or os.getenv("AZURE_API_BASE")
        key = settings.azure_api_key or os.getenv("AZURE_API_KEY")
        dep = settings.azure_deployment or os.getenv("AZURE_DEPLOYMENT")
        if not (base and key and dep):
            raise RuntimeError("Azure OpenAI config missing")
        url = f"{base.rstrip('/')}/openai/deployments/{dep}/chat/completions?api-version=2023-10-01"
        # convert messages to azure format
        payload = {"messages": messages, "max_tokens": 800}
        headers = {"api-key": key, "Content-Type": "application/json"}
        with httpx.Client(timeout=30) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            j = r.json()
            # Azure returns choices[0].message.content
            try:
                return j["choices"][0]["message"]["content"].strip()
            except Exception:
                return r.text

    def _call_local(self, prompt: str) -> str:
        url = settings.local_llm_url or os.getenv("LOCAL_LLM_URL")
        if not url:
            raise RuntimeError("Local LLM URL not configured")
        with httpx.Client(timeout=60) as client:
            r = client.post(url, json={"prompt": prompt})
            r.raise_for_status()
            return r.text

    def request_test_plan(self, manifest: dict, triggers: Optional[list] = None, max_retries: int = 2) -> Tuple[dict, str]:
        messages = self._build_messages(manifest, triggers)
        last_raw = ""
        for attempt in range(max_retries + 1):
            if self.provider == "openai":
                raw = self._call_openai(messages)
            elif self.provider == "deepseek":
                raw = self._call_deepseek(messages[-1]["content"])
            elif self.provider == "anthropic":
                raw = self._call_anthropic(messages[-1]["content"])
            elif self.provider == "azure":
                raw = self._call_azure(messages)
            elif self.provider == "local":
                raw = self._call_local(messages[-1]["content"])
            else:
                raise RuntimeError(f"unsupported llm provider: {self.provider}")
            last_raw = raw
            try:
                plan = self._extract_json(raw)
                if not isinstance(plan, dict) or "actions" not in plan:
                    raise ValueError("plan must be a dict containing actions list")
                return plan, raw
            except Exception as e:
                messages.append({"role":"assistant","content":raw})
                messages.append({"role":"user","content":f"上一条输出无法解析为合法 JSON: {e}. 请只输出纯 JSON，确保包含 actions 列表。"})
                time.sleep(0.5)
        raise RuntimeError("LLM 未能生成合法测试计划; 最后输出:\n" + last_raw)

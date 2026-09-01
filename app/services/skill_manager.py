import os
import subprocess
import time
import socket
import ipaddress
import json
import httpx
from urllib.parse import urlparse
from pathlib import Path
from pathlib import Path
import zipfile, shutil, json
from ..agent.validator import Validator
from ..agent.agent.llm_agent import LlmAgent
from ..agent.agent.executor import Executor
from ..utils.manifest_utils import load_manifest_from_workdir  # 或把函数顶置

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16")
]

from ..core.config import settings

def is_private_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            for net in PRIVATE_NETWORKS:
                if ip in net:
                    return True
    except Exception:
        # treat unresolved hosts as unsafe by default
        return True
    return False

class Executor:
    def __init__(self, workdir: str, manifest: dict):
        self.workdir = workdir
        self.manifest = manifest
        self.proc = None

    def prepare_and_start(self) -> bool:
        run = self.manifest.get("run")
        if not run:
            return False
        cmd = run.get("command")
        if not cmd:
            return False
        # start process (production: use docker container)
        self.proc = subprocess.Popen(cmd, shell=True, cwd=self.workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        hc = run.get("healthcheck", {})
        if hc:
            url = hc.get("url")
            timeout = hc.get("timeout", 5)
            t0 = time.time()
            while time.time() - t0 < timeout:
                try:
                    with httpx.Client(timeout=2) as c:
                        r = c.get(url)
                        if r.status_code < 400:
                            return True
                except Exception:
                    time.sleep(0.5)
            return False
        return True

    def teardown(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()

    def run_manifest_tests(self):
        results = []
        entry = self.manifest.get("entrypoint", {})
        for t in self.manifest.get("tests", []):
            if entry.get("type") == "http":
                try:
                    method = entry.get("method", "POST").upper()
                    with httpx.Client(timeout=8) as c:
                        r = c.request(method, entry["url"], json=t.get("input", {}).get("json"))
                    ok = True
                    reasons = []
                    exp = t.get("expected", {})
                    if "status" in exp and r.status_code != exp["status"]:
                        ok = False; reasons.append(f"status {r.status_code} != {exp['status']}")
                    if "json_contains" in exp:
                        try:
                            body = r.json()
                            for k,v in exp["json_contains"].items():
                                if body.get(k) != v:
                                    ok = False; reasons.append(f"body[{k}] mismatch")
                        except Exception:
                            ok = False; reasons.append("not json")
                    results.append({"id": t.get("id"), "result": {"ok": ok, "status": r.status_code, "reasons": reasons}})
                except Exception as e:
                    results.append({"id": t.get("id"), "result": {"ok": False, "error": str(e)}})
            else:
                results.append({"id": t.get("id"), "result": {"ok": False, "error": "unsupported entry type for tests"}})
        return results

    def _safe_url(self, url: str):
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            raise ValueError("URL has no hostname")
        if is_private_host(host) and not settings.allow_private_network:
            raise ValueError("private or unresolved host rejected: " + host)
        # if allowed_hosts configured, ensure host in allowed set
        if settings.allowed_hosts and host not in settings.allowed_hosts:
            raise ValueError("host not in allowed_hosts")
        return True

    def execute_plan(self, plan: dict):
        if not plan or not isinstance(plan, dict) or "actions" not in plan:
            return {"actions": []}
        results = []
        for act in plan.get("actions", []):
            aid = act.get("id")
            typ = act.get("type")
            if typ == "http":
                url = act.get("url")
                try:
                    self._safe_url(url)
                except Exception as e:
                    results.append({"id": aid, "ok": False, "error": f"security: {e}"})
                    continue
                try:
                    method = act.get("method", "POST").upper()
                    with httpx.Client(timeout=8) as c:
                        r = c.request(method, url, json=act.get("json"))
                    ok = True
                    reasons = []
                    exp = act.get("expected", {})
                    if "status" in exp and r.status_code != exp["status"]:
                        ok = False; reasons.append(f"status {r.status_code} != {exp['status']}")
                    if "json_contains" in exp:
                        try:
                            body = r.json()
                            for k,v in exp["json_contains"].items():
                                if body.get(k) != v:
                                    ok = False; reasons.append(f"body[{k}] mismatch")
                        except Exception:
                            ok = False; reasons.append("response not json")
                    results.append({"id": aid, "ok": ok, "status": r.status_code, "reasons": reasons, "resp_snippet": r.text[:1000]})
                except Exception as e:
                    results.append({"id": aid, "ok": False, "error": str(e)})
            else:
                results.append({"id": aid, "ok": False, "error": "unsupported action type in PoC"})
        return {"actions": results}


class SkillManager:
    ...
    def run_check_for_skill(self, skill_id: str, baseline_skill_id: Optional[str] = None):
        workdir, report_path, status_path = self._id_dirs(skill_id)
        status_path.write_text(json.dumps({"status":"running"}))
        upload_dir = self.storage_root / skill_id
        zip_path = upload_dir / "skill.zip"
        if not zip_path.exists():
            status_path.write_text(json.dumps({"status":"error","reason":"zip not found"})); return

        # 解包
        if workdir.exists(): shutil.rmtree(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(workdir)

        # 加载 target manifest（尝试多种候选）
        try:
            target_manifest = load_manifest_from_workdir(workdir)
        except FileNotFoundError:
            status_path.write_text(json.dumps({"status":"error","reason":"manifest not found"})); return

        # 如果有 baseline_skill_id，解包并加载 baseline manifest
        baseline_manifest = None
        if baseline_skill_id:
            baseline_upload_dir = self.storage_root / baseline_skill_id
            baseline_zip = baseline_upload_dir / "skill.zip"
            if baseline_zip.exists():
                tmpb = tempfile.mkdtemp(prefix="baseline_")
                with zipfile.ZipFile(baseline_zip, 'r') as z:
                    z.extractall(tmpb)
                try:
                    baseline_manifest = load_manifest_from_workdir(tmpb)
                except Exception:
                    baseline_manifest = None
                shutil.rmtree(tmpb)
            else:
                # baseline not found -> mark but continue
                pass

        # 静态校验（基于 target manifest）
        validator = Validator(...)  # 传入 manifest path 或 manifest dict (可改 Validator 支持)
        static = validator.run_static_checks()  # 也可改为接收 manifest dict

        # 启动 skill（如果有 run 命令）
        execer = Executor(str(workdir), target_manifest)
        execer.prepare_and_start()

        # 运行 deterministic tests
        det_results = execer.run_manifest_tests()

        # 向 LLM 请求测试计划并把 baseline 传入
        llm = LlmAgent()
        triggers = target_manifest.get("triggers", [])
        try:
            plan, raw = llm.request_test_plan(target_manifest, triggers=triggers, baseline=baseline_manifest)
        except Exception as e:
            plan = None; raw = f"llm error: {e}"

        # 执行 plan
        plan_results = execer.execute_plan(plan or {})

        # 计算 trace
        trace = validator.compute_trace(static, det_results, plan_results)

        report = {...}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        status_path.write_text(json.dumps({"status":"done"}))
        execer.teardown()
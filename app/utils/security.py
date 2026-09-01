import os
import subprocess
import time
import socket
import ipaddress
import json
import httpx
from urllib.parse import urlparse
from pathlib import Path

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
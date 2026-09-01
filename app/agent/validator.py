import yaml

class Validator:
    def __init__(self, manifest_path):
        self.manifest_path = manifest_path

    def load_manifest(self):
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def run_static_checks(self):
        m = self.load_manifest()
        result = {"frontmatter_ok": True, "missing": [], "entrypoint": m.get("entrypoint")}
        required = ["name", "version", "entrypoint"]
        missing = [k for k in required if k not in m]
        if missing:
            result["frontmatter_ok"] = False
            result["missing"] = missing
        result["has_tests"] = bool(m.get("tests"))
        result["has_run_command"] = bool(m.get("run"))
        return result

    def compute_trace(self, static_report, deterministic_tests, plan_results):
        T = 100 if static_report.get("frontmatter_ok") else 50
        if not deterministic_tests:
            R = 70
        else:
            passed = sum(1 for t in deterministic_tests if t.get("result", {}).get("ok"))
            R = int(100 * passed / len(deterministic_tests))
        A = 100 if static_report.get("has_run_command") or static_report.get("entrypoint", {}).get("type") in ("http","command") else 50
        C = 100 if static_report.get("frontmatter_ok") else 40
        if not plan_results or not plan_results.get("actions"):
            E = 30
        else:
            succ = sum(1 for a in plan_results["actions"] if a.get("ok"))
            E = int(100 * succ / max(1, len(plan_results["actions"])))
        total = int(0.2*T + 0.25*R + 0.2*A + 0.15*C + 0.2*E)
        return {"T":T,"R":R,"A":A,"C":C,"E":E,"total":total}
#!/usr/bin/env python3
"""Skill-checker scoring utilities.

All commands read JSON from stdin (or an optional file arg) and write to stdout.
No intermediate files — agent pipes data through these commands.

Commands:
    eval-summary    Count pass/fail, compute pass_rate
    env-summary     Count compatibility categories, compute fitness_score
    merge           Combine all dimensions into a single check.json (with TRACE)
    trace           Compute TRACE scores from existing check.json
    split           Stratified train/test split
"""

import argparse
import json
import random
import sys
from datetime import datetime, timezone


def _read(path=None):
    if path and path != "-":
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return json.load(sys.stdin)


def _out(data):
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    print()


# ── eval-summary ─────────────────────────────────────────

def eval_summary(items, skill_name="", description=""):
    results = []
    for item in items:
        passed = item["triggered"] == item["should_trigger"]
        results.append({
            "query": item["query"],
            "should_trigger": item["should_trigger"],
            "triggered": item["triggered"],
            "pass": passed,
        })
    n_passed = sum(1 for r in results if r["pass"])
    total = len(results)
    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": n_passed,
            "failed": total - n_passed,
            "pass_rate": round(n_passed / total, 4) if total else 0,
        },
    }


# ── env-summary ──────────────────────────────────────────

def env_summary(dependencies):
    counts = {"compatible": 0, "adaptable": 0, "incompatible": 0, "unknown": 0}
    blocking, adaptations = [], []
    for dep in dependencies:
        c = dep.get("compatibility", "unknown")
        counts[c] = counts.get(c, 0) + 1
        if c == "incompatible":
            blocking.append(dep.get("name", ""))
        elif c == "adaptable":
            adaptations.append(dep.get("name", ""))
    total = len(dependencies)
    ok = counts["compatible"] + counts["adaptable"]
    return {
        "total": total,
        **counts,
        "blocking_issues": blocking,
        "adaptations_available": adaptations,
        "fitness_score": round(ok / total, 4) if total else 1.0,
    }


# ── TRACE five-dimension evaluation ──────────────────────

def _verdict(score):
    """Map score to verdict label."""
    if score >= 0.9:
        return "优秀"
    elif score >= 0.8:
        return "良好"
    elif score >= 0.6:
        return "需修复"
    else:
        return "不合格"


def _conclusion(dim_scores):
    """Determine overall conclusion from TRACE dimension scores."""
    if not dim_scores:
        return "无法评估", "缺少评分数据"
    scores = list(dim_scores.values())
    if all(s >= 0.8 for s in scores):
        return "可直接使用", "所有维度均达到良好以上，可直接在当前环境使用"
    if any(s < 0.6 for s in scores):
        return "不可用，需修复", "存在不合格维度，必须先修复阻塞问题后才能使用"
    return "可用，但需修复", "部分维度需修复后即可正常使用，修复成本可控"


def compute_trace(trigger_summary, env_summary_data, frontmatter_valid=True,
                  frontmatter_warnings=0):
    """
    Compute TRACE five-dimension scores from existing evaluation data.

    T - Trust (可信任度): Does the skill deliver what description promises?
    R - Reliability (可靠性): How robust is the implementation?
    A - Adaptability (适用性): How well does it fit the current environment?
    C - Convention (规范性): Does it follow skill conventions?
    E - Effectiveness (有效性): Does it trigger correctly?

    Returns dict with trace scores, verdicts, issues, and overall conclusion.
    """
    total_deps = env_summary_data.get("total", 0) if env_summary_data else 0
    incompatible = env_summary_data.get("incompatible", 0) if env_summary_data else 0
    adaptable = env_summary_data.get("adaptable", 0) if env_summary_data else 0
    unknown = env_summary_data.get("unknown", 0) if env_summary_data else 0
    compatible = env_summary_data.get("compatible", 0) if env_summary_data else 0
    blocking = env_summary_data.get("blocking_issues", []) if env_summary_data else []

    # ── Trust: description claims vs actual implementation ──
    # Subtract for each incompatible dep (promised but not delivered)
    denom = compatible + adaptable + incompatible
    if denom > 0:
        trust_score = round(1.0 - (incompatible / denom), 4)
    else:
        trust_score = 1.0
    trust_issues = []
    if incompatible > 0:
        trust_issues.append(
            f"description 声称的功能有 {incompatible} 项无对应实现: {', '.join(blocking)}"
        )
    if unknown > 0:
        trust_issues.append(f"有 {unknown} 项依赖状态不明，无法确认是否兑现")

    # ── Reliability: dependency quality ──
    # Unknown deps are risky, adaptable deps need workarounds
    if total_deps > 0:
        reliability_score = round(max(0, 1.0 - (unknown * 0.3 + adaptable * 0.05)), 4)
    else:
        reliability_score = 1.0
    reliability_issues = []
    if unknown > 0:
        reliability_issues.append(f"有 {unknown} 项依赖状态未知，存在运行时风险")
    if adaptable > 0:
        reliability_issues.append(f"有 {adaptable} 项依赖需适配，增加不确定性")

    # ── Adaptability: fitness to current environment ──
    adaptability_score = env_summary_data.get("fitness_score", 1.0) if env_summary_data else 1.0
    adaptability_issues = []
    if incompatible > 0:
        adaptability_issues.append(f"有 {incompatible} 项不兼容当前环境: {', '.join(blocking)}")
    if adaptable > 0:
        adapt_names = env_summary_data.get("adaptations_available", []) if env_summary_data else []
        adaptability_issues.append(f"有 {adaptable} 项需适配: {', '.join(adapt_names)}")

    # ── Convention: frontmatter validity ──
    if frontmatter_valid and frontmatter_warnings == 0:
        convention_score = 1.0
    elif frontmatter_valid:
        convention_score = 0.9
    else:
        convention_score = 0.7
    convention_issues = []
    if not frontmatter_valid:
        convention_issues.append("frontmatter 校验失败，存在错误")
    elif frontmatter_warnings > 0:
        convention_issues.append(f"frontmatter 有 {frontmatter_warnings} 个警告")

    # ── Effectiveness: trigger accuracy ──
    effectiveness_score = trigger_summary.get("pass_rate", 0) if trigger_summary else 0
    effectiveness_issues = []
    if trigger_summary:
        failed = trigger_summary.get("failed", 0)
        if failed > 0:
            effectiveness_issues.append(f"触发评测有 {failed} 条失败，存在误触发或漏触发")

    dim_scores = {
        "trust": trust_score,
        "reliability": reliability_score,
        "adaptability": adaptability_score,
        "convention": convention_score,
        "effectiveness": effectiveness_score,
    }

    trace = {
        "trust": {
            "score": trust_score,
            "label": "可信任度",
            "verdict": _verdict(trust_score),
            "issues": trust_issues,
        },
        "reliability": {
            "score": reliability_score,
            "label": "可靠性",
            "verdict": _verdict(reliability_score),
            "issues": reliability_issues,
        },
        "adaptability": {
            "score": adaptability_score,
            "label": "适用性",
            "verdict": _verdict(adaptability_score),
            "issues": adaptability_issues,
        },
        "convention": {
            "score": convention_score,
            "label": "规范性",
            "verdict": _verdict(convention_score),
            "issues": convention_issues,
        },
        "effectiveness": {
            "score": effectiveness_score,
            "label": "有效性",
            "verdict": _verdict(effectiveness_score),
            "issues": effectiveness_issues,
        },
        "overall": round(sum(dim_scores.values()) / 5, 4),
    }

    conclusion_label, conclusion_detail = _conclusion(dim_scores)
    trace["conclusion"] = conclusion_label
    trace["conclusion_detail"] = conclusion_detail

    return trace


# ── merge ────────────────────────────────────────────────

def merge(skill_name, trigger=None, environment=None, evals=None,
          optimization=None, frontmatter_valid=True, frontmatter_warnings=0):
    """Combine all dimensions into a single check.json report with TRACE evaluation."""
    dims = {}

    if trigger is not None:
        s = trigger.get("summary", {})
        dims["trigger"] = {
            "status": "checked",
            "score": s.get("pass_rate", 0),
            "results": trigger.get("results", []),
            "summary": s,
            "description_used": trigger.get("description", ""),
        }
    else:
        dims["trigger"] = {"status": "skipped"}

    if environment is not None:
        s = environment.get("summary", {})
        dims["environment"] = {
            "status": "checked",
            "score": s.get("fitness_score", 0),
            "dependencies": environment.get("dependencies", []),
            "summary": s,
        }
    else:
        dims["environment"] = {"status": "skipped"}

    # ── Compute TRACE scores ──
    trigger_s = trigger.get("summary", {}) if trigger else {}
    env_s = environment.get("summary", {}) if environment else {}
    trace = compute_trace(trigger_s, env_s, frontmatter_valid, frontmatter_warnings)

    checked = [d for d in dims.values() if d["status"] == "checked"]
    overall = (round(sum(d["score"] for d in checked) / len(checked), 4)
               if checked else 0)

    report = {
        "skill_name": skill_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall,
        "trace": trace,
        "dimensions": dims,
    }
    if evals is not None:
        report["evals"] = evals
    if optimization is not None:
        report["optimization"] = optimization
    return report


# ── split ────────────────────────────────────────────────

def split_eval_set(eval_set, holdout=0.4, seed=42):
    random.seed(seed)
    pos = [e for e in eval_set if e["should_trigger"]]
    neg = [e for e in eval_set if not e["should_trigger"]]
    random.shuffle(pos)
    random.shuffle(neg)
    np = max(1, int(len(pos) * holdout))
    nn = max(1, int(len(neg) * holdout))
    return {
        "train": pos[np:] + neg[nn:],
        "test": pos[:np] + neg[:nn],
    }


# ── CLI ──────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Skill-checker scoring")
    sub = p.add_subparsers(dest="cmd")

    s1 = sub.add_parser("eval-summary")
    s1.add_argument("input", nargs="?", help="JSON file (default: stdin)")
    s1.add_argument("--skill-name", default="")
    s1.add_argument("--description", default="")

    s2 = sub.add_parser("env-summary")
    s2.add_argument("input", nargs="?")

    s3 = sub.add_parser("merge")
    s3.add_argument("input", nargs="?", help="JSON: {skill_name, trigger, environment, evals, ...}")
    s3.add_argument("--skill-name", default="")
    s3.add_argument("--frontmatter-valid", type=lambda x: x.lower() == "true", default=True)
    s3.add_argument("--frontmatter-warnings", type=int, default=0)

    s4 = sub.add_parser("split")
    s4.add_argument("input", nargs="?")
    s4.add_argument("--holdout", type=float, default=0.4)
    s4.add_argument("--seed", type=int, default=42)

    s5 = sub.add_parser("trace")
    s5.add_argument("input", nargs="?", help="Existing check.json to recompute TRACE from")
    s5.add_argument("--frontmatter-valid", type=lambda x: x.lower() == "true", default=True)
    s5.add_argument("--frontmatter-warnings", type=int, default=0)

    args = p.parse_args()

    if args.cmd == "eval-summary":
        _out(eval_summary(_read(args.input), args.skill_name, args.description))

    elif args.cmd == "env-summary":
        data = _read(args.input)
        deps = data.get("dependencies", data) if isinstance(data, dict) else data
        summary = env_summary(deps)
        if isinstance(data, dict) and "dependencies" in data:
            data["summary"] = summary
            _out(data)
        else:
            _out(summary)

    elif args.cmd == "merge":
        data = _read(args.input)
        _out(merge(
            skill_name=args.skill_name or data.get("skill_name", ""),
            trigger=data.get("trigger"),
            environment=data.get("environment"),
            evals=data.get("evals"),
            optimization=data.get("optimization"),
            frontmatter_valid=args.frontmatter_valid,
            frontmatter_warnings=args.frontmatter_warnings,
        ))

    elif args.cmd == "split":
        _out(split_eval_set(_read(args.input), args.holdout, args.seed))

    elif args.cmd == "trace":
        data = _read(args.input)
        trigger_s = data.get("dimensions", {}).get("trigger", {}).get("summary", {})
        env_s = data.get("dimensions", {}).get("environment", {}).get("summary", {})
        _out(compute_trace(
            trigger_s, env_s,
            args.frontmatter_valid, args.frontmatter_warnings,
        ))

    else:
        p.print_help()


if __name__ == "__main__":
    main()
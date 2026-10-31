"""Metrics harness (B1 + T1 measurement).

- run_task_comparison(tasks, agent_fn, baseline_fn): runs both agents
  on copies of each task repo and returns per-task and aggregate
  metrics: tokens/task, cost/task (when usage reports cost -- otherwise
  None, never invented), turns/task, pass@1, and token savings %.
- evaluate_detector(labeled_claims, provider): runs the detector over
  the frozen labeled claim set and returns precision, recall,
  mean latency/claim and credits/claim (credits only tracked by
  TavilyProvider; None for stub).

Task repos are copied to temp dirs before each run so the agent's
patches never contaminate the frozen repos.
"""

import copy
import shutil
import tempfile
import time

from .freshness.verdict import check_claim


def _copy_task(task):
    tmp = tempfile.mkdtemp(prefix="freshcode-task-")
    dest = tmp + "/repo"
    shutil.copytree(task["repo"], dest)
    t = dict(task)
    t["repo"] = dest
    t["_tmp"] = tmp
    return t


def run_task_comparison(tasks, agent_fn, baseline_fn):
    rows = []
    for task in tasks:
        a_task = _copy_task(task)
        b_task = _copy_task(task)
        try:
            a = agent_fn(a_task)
            b = baseline_fn(b_task)
        finally:
            # Temp copies are removed even if an agent raises, so a
            # crashed run never leaks task repos into /tmp.
            shutil.rmtree(a_task["_tmp"], ignore_errors=True)
            shutil.rmtree(b_task["_tmp"], ignore_errors=True)
        rows.append({
            "task_id": task["id"],
            "agent_passed": a["passed"],
            "baseline_passed": b["passed"],
            "agent_tokens": a["tokens_total"],
            "baseline_tokens": b["tokens_total"],
            "agent_turns": a["turns"],
            "baseline_turns": b["turns"],
            "tokens_saved_by_masking": a.get("tokens_saved_by_masking", 0),
        })
    n = max(1, len(rows))
    agent_tokens = sum(r["agent_tokens"] for r in rows)
    baseline_tokens = sum(r["baseline_tokens"] for r in rows)
    savings = None
    if baseline_tokens:
        savings = round(100.0 * (baseline_tokens - agent_tokens)
                        / baseline_tokens, 1)
    return {
        "tasks": rows,
        "n_tasks": len(rows),
        "agent_pass_at_1": round(
            sum(r["agent_passed"] for r in rows) / n, 3),
        "baseline_pass_at_1": round(
            sum(r["baseline_passed"] for r in rows) / n, 3),
        "agent_tokens_per_task": round(agent_tokens / n, 1),
        "baseline_tokens_per_task": round(baseline_tokens / n, 1),
        "token_savings_pct": savings,
        "agent_turns_per_task": round(
            sum(r["agent_turns"] for r in rows) / n, 1),
        "baseline_turns_per_task": round(
            sum(r["baseline_turns"] for r in rows) / n, 1),
    }


def evaluate_detector(labeled_claims, provider, max_results=3):
    """labeled_claims: [{text, label}] with label 'stale' or 'fresh'.

    Detector verdict 'uncertain' counts as a miss for both classes
    (honest: abstention is not a correct answer).
    """
    tp = fp = fn = tn = 0
    latencies = []
    credits_before = getattr(provider, "credits_used", 0)
    calls_before = getattr(provider, "calls", 0)
    for item in labeled_claims:
        label = item["label"]
        if label not in ("fresh", "stale"):
            raise ValueError(
                "claim label must be 'fresh' or 'stale', got %r "
                "for claim %r" % (label, item.get("text", "")[:80]))
        start = time.monotonic()
        results = provider.search(item["text"], max_results=max_results)
        verdict, _score, _src = check_claim(item["text"], results)
        latencies.append(time.monotonic() - start)
        if verdict == "stale" and label == "stale":
            tp += 1
        elif verdict == "stale" and label == "fresh":
            fp += 1
        elif verdict == "fresh" and label == "fresh":
            tn += 1
        else:  # fresh/uncertain on a stale claim
            fn += 1
    precision = round(tp / (tp + fp), 3) if (tp + fp) else None
    recall = round(tp / (tp + fn), 3) if (tp + fn) else None
    calls = getattr(provider, "calls", 0) - calls_before
    credits = getattr(provider, "credits_used", None)
    credits_per_claim = None
    if credits is not None:
        credits_per_claim = round((credits - credits_before)
                                  / max(1, len(labeled_claims)), 2)
    return {
        "n_claims": len(labeled_claims),
        "precision_stale": precision,
        "recall_stale": recall,
        "true_positives": tp, "false_positives": fp,
        "false_negatives": fn, "true_negatives": tn,
        "mean_latency_s_per_claim": round(
            sum(latencies) / max(1, len(latencies)), 3),
        "search_calls": calls,
        "credits_per_claim": credits_per_claim,
    }

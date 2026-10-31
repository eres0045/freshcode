"""FreshCode demo runner (STUB MODE -- pipeline demonstration only).

Runs the agent vs the baseline on 2 sample tasks and the freshness
detector on a 10-claim sample, using StubModel / StubProvider.
Numbers printed here are NOT measurements of a real model: the stub
returns canned gold patches, so pass rates reflect the stub, not the
agent. Real measurements require:
  - a real model via FRESHCODE_MODEL_BASE_URL / FRESHCODE_MODEL_NAME /
    FRESHCODE_MODEL_API_KEY, and
  - a real Tavily key via TAVILY_API_KEY.

Usage: python3 run_demo.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freshcode.agent import run_agent
from freshcode.baseline import run_baseline
from freshcode.freshness import StubProvider
from freshcode.metrics import evaluate_detector, run_task_comparison
from freshcode.model import StubModel

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(ROOT, "data", "tasks.json")) as fh:
        tasks = json.load(fh)
    for t in tasks:
        t["repo"] = os.path.join(ROOT, t["repo"])
    sample = [t for t in tasks if t["id"] in ("t01", "t09")]
    gold = {t["id"]: t["gold_patch"] for t in tasks}
    print("=== FreshCode demo (STUB MODE -- not a measurement) ===")
    result = run_task_comparison(
        sample,
        lambda task: run_agent(task, StubModel(gold)),
        lambda task: run_baseline(task, StubModel(gold)))
    print(json.dumps(result, indent=2))
    with open(os.path.join(ROOT, "data", "claims.json")) as fh:
        claims = json.load(fh)
    sample_claims = claims[:5] + claims[50:55]

    class LabelProvider(StubProvider):
        def __init__(self, label_map):
            super().__init__({})
            self.label_map = label_map

        def search(self, query, max_results=5):
            self.calls += 1
            label = self.label_map.get(query)
            if label:
                return [{"title": "stub", "snippet": query,
                         "url": "", "verdict": label}]
            return [{"title": "stub", "snippet": "",
                     "url": "", "verdict": None}]

    det = evaluate_detector(
        sample_claims,
        LabelProvider({c["text"]: c["label"] for c in sample_claims}))
    print("=== Detector sample (STUB MODE -- not a measurement) ===")
    print(json.dumps(det, indent=2))


if __name__ == "__main__":
    main()

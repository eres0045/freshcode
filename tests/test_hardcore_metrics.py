"""Hardcore metrics-harness tests for FreshCode.

Covers: frozen-data non-contamination, stub determinism, loud failure
on malformed tasks/claims, temp-dir cleanup when an agent raises, and
the full 20-task stub comparison (pipeline numbers only).
"""
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from freshcode.agent import run_agent
from freshcode.baseline import run_baseline
from freshcode.freshness import StubProvider
from freshcode.metrics import evaluate_detector, run_task_comparison
from freshcode.model import StubModel

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_tasks():
    with open(os.path.join(ROOT, "data", "tasks.json")) as fh:
        tasks = json.load(fh)
    for t in tasks:
        t["repo"] = os.path.join(ROOT, t["repo"])
    return tasks


def hash_py_files(repo_dir):
    out = {}
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "rb") as fh:
                    out[os.path.relpath(path, repo_dir)] = \
                        hashlib.sha256(fh.read()).hexdigest()
    return out


class TestMetricsHardcore(unittest.TestCase):
    def test_frozen_repos_not_contaminated(self):
        task = next(t for t in load_tasks() if t["id"] == "t03")
        before = hash_py_files(task["repo"])
        gold = {task["id"]: task["gold_patch"]}
        run_task_comparison(
            [task],
            lambda t: run_agent(t, StubModel(gold)),
            lambda t: run_baseline(t, StubModel(gold)))
        after = hash_py_files(task["repo"])
        self.assertEqual(before, after)

    def test_stub_runs_are_deterministic(self):
        tasks = [t for t in load_tasks() if t["id"] in ("t01", "t02")]
        gold = {t["id"]: t["gold_patch"] for t in tasks}

        def run_once():
            return run_task_comparison(
                tasks,
                lambda t: run_agent(t, StubModel(gold)),
                lambda t: run_baseline(t, StubModel(gold)))

        first = run_once()
        second = run_once()
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))

    def test_malformed_task_fails_loudly(self):
        task = {"id": "bad1", "repo": "/tmp", "target_file": "x.py",
                "description": "missing test_command"}
        with self.assertRaises(KeyError):
            run_agent(task, StubModel({}))
        ghost = {"id": "ghost", "repo": "/tmp/does-not-exist-freshcode",
                 "target_file": "x.py", "description": "ghost repo",
                 "test_command": "true"}
        with self.assertRaises((FileNotFoundError, OSError)):
            run_task_comparison(
                [ghost],
                lambda t: run_agent(t, StubModel({})),
                lambda t: run_baseline(t, StubModel({})))

    def test_malformed_claim_label_fails_loudly(self):
        with self.assertRaises(ValueError):
            evaluate_detector(
                [{"text": "Python 3.13 was released in 2024.",
                  "label": "bogus"}],
                StubProvider({}))
        with self.assertRaises(KeyError):
            evaluate_detector([{"text": "Python 3.13 was released in 2024."}],
                              StubProvider({}))

    def test_temp_dirs_cleaned_when_agent_raises(self):
        task = next(t for t in load_tasks() if t["id"] == "t01")

        def boom(_task):
            raise RuntimeError("simulated agent crash")

        before = set(glob.glob(os.path.join(tempfile.gettempdir(),
                                            "freshcode-task-*")))
        with self.assertRaises(RuntimeError):
            run_task_comparison(
                [task], boom,
                lambda t: run_baseline(t, StubModel({})))
        after = set(glob.glob(os.path.join(tempfile.gettempdir(),
                                           "freshcode-task-*")))
        self.assertEqual(before, after)

    def test_full_20_task_stub_comparison(self):
        """Full frozen set, stub model: pipeline numbers ONLY.
        (Stub returns canned gold patches, so pass rates here say
        nothing about a real model. This test pins the harness shape
        and determinism inputs for the real-model run.)"""
        tasks = load_tasks()
        gold = {t["id"]: t["gold_patch"] for t in tasks}
        result = run_task_comparison(
            tasks,
            lambda t: run_agent(t, StubModel(gold)),
            lambda t: run_baseline(t, StubModel(gold)))
        self.assertEqual(result["n_tasks"], 20)
        self.assertEqual(len(result["tasks"]), 20)
        for key in ("agent_pass_at_1", "baseline_pass_at_1",
                    "agent_tokens_per_task", "baseline_tokens_per_task",
                    "token_savings_pct", "agent_turns_per_task",
                    "baseline_turns_per_task"):
            self.assertIn(key, result)
            self.assertIsNotNone(result[key])


if __name__ == "__main__":
    unittest.main()

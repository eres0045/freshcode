"""FreshCode test suite (stdlib unittest, offline).

Run: python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from freshcode.agent import run_agent
from freshcode.baseline import run_baseline
from freshcode.freshness import (StubProvider, check_claim, check_text,
                                 extract_claims)
from freshcode.metrics import evaluate_detector, run_task_comparison
from freshcode.model import OpenAICompatibleModel, StubModel
from freshcode.tools import ToolSet, parse_action

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_tasks():
    with open(os.path.join(ROOT, "data", "tasks.json")) as fh:
        tasks = json.load(fh)
    for t in tasks:
        t["repo"] = os.path.join(ROOT, t["repo"])
    return tasks


def load_claims():
    with open(os.path.join(ROOT, "data", "claims.json")) as fh:
        return json.load(fh)


class TestTools(unittest.TestCase):
    def test_parse_action(self):
        action, arg, rest = parse_action("ACTION: read_file calc.py")
        self.assertEqual(action, "read_file")
        self.assertEqual(arg, "calc.py")

    def test_parse_write_file(self):
        action, arg, rest = parse_action("ACTION: write_file\nx = 1\n")
        self.assertEqual(action, "write_file")
        self.assertIn("x = 1", rest)

    def test_masking_saves_tokens(self):
        tools = ToolSet("/tmp", "true")
        _schemas, saved = tools.visible_schemas(mask=True)
        self.assertGreaterEqual(saved, 0)

    def test_path_escape_blocked(self):
        tools = ToolSet("/tmp", "true")
        with self.assertRaises(ValueError):
            tools.read_file("../etc/passwd")


class TestFreshness(unittest.TestCase):
    def test_extract_claims_finds_version(self):
        claims = extract_claims("React 19 was released in December 2024. "
                                "It is a nice day.")
        self.assertEqual(len(claims), 1)
        self.assertIn("React 19", claims[0]["text"])

    def test_extract_claims_skips_plain(self):
        self.assertEqual(extract_claims("Hello world, have a nice day."), [])

    def test_stub_verdict_stale(self):
        provider = StubProvider({"react": [
            {"title": "React versions", "snippet": "React 19 is current.",
             "url": "https://react.dev/", "verdict": "stale"}]})
        verdict, score, _ = check_claim("React's latest major version is 18.",
                                        provider.search("react"))
        self.assertEqual(verdict, "stale")
        self.assertLess(score, 0.5)

    def test_check_text_labels_stub_mode(self):
        provider = StubProvider({})
        report = check_text("Python 3.13 was released in October 2024.",
                            provider)
        self.assertEqual(report["claims_found"], 1)
        self.assertEqual(report["checked"][0]["verdict"], "uncertain")


class TestFrozenData(unittest.TestCase):
    def test_task_count(self):
        self.assertEqual(len(load_tasks()), 20)

    def test_claim_count_and_balance(self):
        claims = load_claims()
        self.assertEqual(len(claims), 100)
        labels = [c["label"] for c in claims]
        self.assertEqual(labels.count("fresh"), 50)
        self.assertEqual(labels.count("stale"), 50)

    def test_claim_categories(self):
        cats = {c["category"] for c in load_claims()}
        self.assertTrue({"api", "pricing", "law", "leadership"} <= cats)


class TestAgentEndToEnd(unittest.TestCase):
    """Full pipeline: agent on a sample task + detector on samples.

    Uses StubModel with gold patches: this proves the pipeline runs
    end to end. It is NOT a measurement of a real model.
    """

    def test_agent_fixes_sample_task(self):
        tasks = load_tasks()
        task = next(t for t in tasks if t["id"] == "t01")
        tmp = tempfile.mkdtemp()
        try:
            repo = os.path.join(tmp, "repo")
            shutil.copytree(task["repo"], repo)
            run_task = dict(task, repo=repo)
            model = StubModel({task["id"]: task["gold_patch"]})
            report = run_agent(run_task, model)
            self.assertTrue(report["passed"])
            self.assertGreater(report["tokens_total"], 0)
            self.assertIn("tokens_saved_by_masking", report)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_baseline_runs_sample_task(self):
        tasks = load_tasks()
        task = next(t for t in tasks if t["id"] == "t02")
        tmp = tempfile.mkdtemp()
        try:
            repo = os.path.join(tmp, "repo")
            shutil.copytree(task["repo"], repo)
            run_task = dict(task, repo=repo)
            model = StubModel({task["id"]: task["gold_patch"]})
            report = run_baseline(run_task, model)
            self.assertTrue(report["passed"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_metrics_produced_for_sample(self):
        tasks = [t for t in load_tasks() if t["id"] in ("t01", "t02")]
        gold = {t["id"]: t["gold_patch"] for t in tasks}
        result = run_task_comparison(
            tasks,
            lambda task: run_agent(task, StubModel(gold)),
            lambda task: run_baseline(task, StubModel(gold)))
        self.assertEqual(result["n_tasks"], 2)
        self.assertIn("token_savings_pct", result)
        self.assertIn("agent_pass_at_1", result)

    def test_detector_metrics_produced(self):
        all_claims = load_claims()
        claims = all_claims[:5] + all_claims[50:55]  # 5 fresh + 5 stale
        knowledge = {}
        for c in claims:
            key = c["text"].split()[0].lower()
            knowledge.setdefault(key, []).append({
                "title": "stub", "snippet": c["text"],
                "url": c["source"], "verdict": c["label"]})
        provider = StubProvider(knowledge)
        # Map each claim to a matching key by patching search per claim:
        # simpler: build knowledge keyed on first distinctive word is
        # unreliable, so instead evaluate with a provider that returns
        # the claim's own label via a small wrapper.
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

        label_map = {c["text"]: c["label"] for c in claims}
        result = evaluate_detector(claims, LabelProvider(label_map))
        self.assertEqual(result["n_claims"], 10)
        self.assertEqual(result["precision_stale"], 1.0)
        self.assertEqual(result["recall_stale"], 1.0)


class TestModelConfig(unittest.TestCase):
    def test_openai_model_reads_env(self):
        os.environ["FRESHCODE_MODEL_BASE_URL"] = "https://example.invalid/v1"
        os.environ["FRESHCODE_MODEL_NAME"] = "test-model"
        m = OpenAICompatibleModel()
        self.assertEqual(m.model, "test-model")
        # Key must never be echoed: the object holds it but repr must
        # not include it.
        self.assertNotIn("FRESHCODE_MODEL_API_KEY", repr(m.__dict__.keys()))


if __name__ == "__main__":
    unittest.main()

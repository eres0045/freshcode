"""Hardcore agent tests for FreshCode.

Covers: multi-file edits, visible-tests-only limitation (documented,
not hidden), empty/garbage input, missing files, failure-loop cutoff
(same action AND alternating actions), masking actually saving tokens,
summarization keeping the task goal, path traversal, secret hygiene.

All models here are scripted/deterministic: these tests measure the
agent LOOP, not model intelligence. Stub-model numbers are pipeline
checks, never agent measurements.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from freshcode.agent import run_agent
from freshcode.model import ModelResponse, StubModel, estimate_tokens
from freshcode.tools import ToolSet

ROOT = os.path.join(os.path.dirname(__file__), "..")


class ScriptedModel:
    """Returns a fixed script of ACTION replies, in order.

    Records every prompt it receives so tests can inspect what the
    agent actually sent (schemas, history, task goal).
    """

    def __init__(self, script):
        self.script = list(script)
        self.prompts = []
        self.n = 0

    def complete(self, messages):
        self.prompts.append("\n".join(m.get("content", "") for m in messages))
        if not self.script:
            text = "ACTION: finish"
        else:
            text = self.script[min(self.n, len(self.script) - 1)]
        self.n += 1
        return ModelResponse(text, {"total_tokens": estimate_tokens(text)})


def make_repo(files):
    """Create a temp repo dir from {relpath: content}. Returns dir."""
    tmp = tempfile.mkdtemp(prefix="freshcode-hard-")
    for rel, content in files.items():
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path) or tmp, exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
    return tmp


class TestMultiFileAndRegression(unittest.TestCase):
    def test_multifile_edit(self):
        """A fix spanning two files must persist and pass."""
        repo = make_repo({
            "config.py": "BASE_PRICE = 90\n",
            "cart.py": ("from config import BASE_PRICE\n\n\n"
                        "def total():\n    return BASE_PRICE\n"),
            "test_cart.py": ("import unittest\nfrom cart import total\n\n\n"
                             "class T(unittest.TestCase):\n"
                             "    def test_total(self):\n"
                             "        self.assertAlmostEqual(total(), 110)\n"),
        })
        try:
            task = {"id": "mf1", "repo": repo, "target_file": "cart.py",
                    "description": "Fix pricing: BASE_PRICE should be 100 "
                    "in config.py and total() should apply 10% tax.",
                    "test_command": "python3 -m unittest test_cart -v"}
            script = [
                "ACTION: read_file config.py",
                "ACTION: read_file cart.py",
                "ACTION: write_file config.py\nBASE_PRICE = 100\n",
                ("ACTION: write_file cart.py\n"
                 "from config import BASE_PRICE\n\n\n"
                 "def total():\n    return BASE_PRICE * 1.1\n"),
                "ACTION: run_tests",
                "ACTION: finish",
            ]
            report = run_agent(task, ScriptedModel(script))
            self.assertTrue(report["passed"])
            with open(os.path.join(repo, "config.py")) as fh:
                self.assertIn("100", fh.read())
            with open(os.path.join(repo, "cart.py")) as fh:
                self.assertIn("1.1", fh.read())
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    def test_visible_tests_pass_but_hidden_behavior_breaks(self):
        """DOCUMENTED LIMITATION: the agent's pass verdict is the
        repo's own tests only. A patch that hardcodes the visible
        answer passes visibly while breaking hidden behavior, and
        the agent cannot see that. This test pins the behavior so
        the limitation stays visible; it is NOT a claim of correctness.
        """
        repo = make_repo({
            "ops.py": "def add(a, b):\n    return a - b\n",
            "test_ops.py": ("import unittest\nfrom ops import add\n\n\n"
                            "class T(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"),
        })
        try:
            task = {"id": "trap1", "repo": repo, "target_file": "ops.py",
                    "description": "Fix add() so it returns the sum.",
                    "test_command": "python3 -m unittest test_ops -v"}
            script = [
                "ACTION: write_file ops.py\ndef add(a, b):\n    return 5\n",
                "ACTION: run_tests",
                "ACTION: finish",
            ]
            report = run_agent(task, ScriptedModel(script))
            self.assertTrue(report["passed"])  # visible tests pass
            sys.path.insert(0, repo)
            try:
                import ops  # noqa: PLC0415
                self.assertNotEqual(ops.add(2, 4), 6)  # hidden breaks
            finally:
                sys.path.remove(repo)
                sys.modules.pop("ops", None)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


class TestRobustInputs(unittest.TestCase):
    def _t01_copy(self):
        import json
        with open(os.path.join(ROOT, "data", "tasks.json")) as fh:
            tasks = json.load(fh)
        task = next(t for t in tasks if t["id"] == "t01")
        tmp = tempfile.mkdtemp()
        repo = os.path.join(tmp, "repo")
        shutil.copytree(os.path.join(ROOT, task["repo"]), repo)
        return tmp, dict(task, repo=repo)

    def test_empty_and_garbage_task_do_not_crash(self):
        for desc in ("", "asdf qwer !!!", "???"):
            tmp, task = self._t01_copy()
            try:
                task["description"] = desc
                report = run_agent(task, StubModel({}))
                self.assertFalse(report["passed"])
                self.assertLessEqual(report["turns"], 25)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_file_task_fails_cleanly(self):
        repo = make_repo({
            "test_missing.py": ("import unittest\nimport missing_mod\n"),
        })
        try:
            task = {"id": "miss1", "repo": repo, "target_file": "missing.py",
                    "description": "Fix the missing module.",
                    "test_command": "python3 -m unittest test_missing -v"}
            script = ["ACTION: read_file missing.py", "ACTION: finish"]
            report = run_agent(task, ScriptedModel(script))
            self.assertFalse(report["passed"])
            self.assertLessEqual(report["turns"], 25)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


class TestFailureLoopCutoff(unittest.TestCase):
    def _failing_task(self):
        import json
        with open(os.path.join(ROOT, "data", "tasks.json")) as fh:
            tasks = json.load(fh)
        task = next(t for t in tasks if t["id"] == "t01")
        tmp = tempfile.mkdtemp()
        repo = os.path.join(tmp, "repo")
        shutil.copytree(os.path.join(ROOT, task["repo"]), repo)
        return tmp, dict(task, repo=repo)

    def test_same_action_loop_is_cut_off(self):
        tmp, task = self._failing_task()
        try:
            report = run_agent(task, ScriptedModel(["ACTION: run_tests"]))
            self.assertEqual(report["stopped_reason"], "failure_loop_cutoff")
            self.assertLessEqual(report["turns"], 10)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_alternating_action_loop_is_cut_off(self):
        """Old code gave one redirect per distinct action, so an agent
        alternating two failing actions looped until max_turns. The
        global redirect budget must stop it early."""
        tmp, task = self._failing_task()
        try:
            script = ["ACTION: run_tests",
                      "ACTION: read_file missing.py"] * 20
            report = run_agent(task, ScriptedModel(script))
            self.assertEqual(report["stopped_reason"], "failure_loop_cutoff")
            self.assertLessEqual(report["turns"], 12)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMechanismsMeasured(unittest.TestCase):
    def _t01_copy_with_gold(self):
        import json
        with open(os.path.join(ROOT, "data", "tasks.json")) as fh:
            tasks = json.load(fh)
        task = next(t for t in tasks if t["id"] == "t01")
        tmp = tempfile.mkdtemp()
        repo = os.path.join(tmp, "repo")
        shutil.copytree(os.path.join(ROOT, task["repo"]), repo)
        return tmp, dict(task, repo=repo), task["gold_patch"]

    def test_masking_reduces_tokens_on_same_run(self):
        tmp, task, gold = self._t01_copy_with_gold()
        try:
            script = ["ACTION: write_file calc.py\n" + gold,
                      "ACTION: run_tests", "ACTION: finish"]
            masked = run_agent(dict(task), ScriptedModel(script))
            unmasked = run_agent(dict(task), ScriptedModel(script),
                                 mask=False)
            self.assertGreater(masked["tokens_saved_by_masking"], 0)
            self.assertLess(masked["tokens_total"], unmasked["tokens_total"])
            self.assertTrue(masked["passed"])
            self.assertTrue(unmasked["passed"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_summarization_keeps_task_goal(self):
        tmp, task, _gold = self._t01_copy_with_gold()
        try:
            script = ["ACTION: read_file calc.py"] * 10 + ["ACTION: finish"]
            model = ScriptedModel(script)
            run_agent(task, model)
            for prompt in model.prompts:
                self.assertIn(task["description"], prompt)
            self.assertTrue(any("[SUMMARY:" in p for p in model.prompts),
                            "history was never summarized over 10+ turns")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSecurityHygiene(unittest.TestCase):
    def test_path_traversal_blocked(self):
        base = tempfile.mkdtemp(prefix="freshcode-sec-")
        try:
            repo = os.path.join(base, "repo")
            os.makedirs(repo)
            with open(os.path.join(repo, "calc.py"), "w") as fh:
                fh.write("x = 1\n")
            tools = ToolSet(repo, "true")
            for bad in ("../evil.py", "sub/../../evil.py",
                        "/etc/passwd", "../repo_evil/pwn.py"):
                with self.assertRaises(ValueError, msg=bad):
                    tools.write_file(bad, "pwned")
                with self.assertRaises(ValueError, msg=bad):
                    tools.read_file(bad)
            # Legitimate paths still work.
            self.assertEqual(tools.read_file("calc.py"), "x = 1\n")
            self.assertFalse(os.path.exists(os.path.join(base, "evil.py")))
            self.assertFalse(os.path.exists(
                os.path.join(base, "repo_evil", "pwn.py")))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_no_secret_literals_in_repo(self):
        """No API keys, tokens, or key-like literals anywhere in the
        tracked repo (env-var names and "..." placeholders allowed)."""
        secret_res = [
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"ghp_[A-Za-z0-9]{20,}"),
            re.compile(r"gho_[A-Za-z0-9]{20,}"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"Bearer [A-Za-z0-9_\-]{20,}"),
            re.compile(r"(?i)api_key\s*=\s*['\"][^'\"]{4,}['\"]"),
        ]
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            for f in files:
                path = os.path.join(root, f)
                try:
                    with open(path, errors="ignore") as fh:
                        content = fh.read()
                except OSError:
                    continue
                for rx in secret_res:
                    for hit in rx.findall(content):
                        # "..." placeholders and the literal word "key"
                        # are not secrets.
                        if hit.strip("'\"") in ("...", "key"):
                            continue
                        self.fail("possible secret %r in %s" % (hit, path))


if __name__ == "__main__":
    unittest.main()

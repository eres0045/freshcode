"""Tool layer for the FreshCode agent.

Tools are plain functions over a repo directory. The agent's action
language is line-based so any chat model can use it without function
calling:

    ACTION: list_files
    ACTION: read_file <relative path>
    ACTION: write_file <relative path>
    <file content follows on the remaining lines>
    ACTION: run_tests
    ACTION: search <query>
    ACTION: finish

Tool-schema masking (a B1 token-saving mechanism): the prompt only
includes schemas for tools the agent used recently plus the always-on
core tools (list_files, read_file). Schemas for masked-out tools are
NOT sent, and the estimated tokens saved are recorded. The baseline
agent (freshcode/baseline.py) never masks.
"""

import os
import subprocess

SCHEMAS = {
    "list_files": "list_files - list files in the repo",
    "read_file": "read_file <path> - read a file",
    "write_file": "write_file <path> + content - replace a file",
    "run_tests": "run_tests - run the repo test command",
    "search": "search <query> - live web search (short results only)",
    "finish": "finish - stop, work is done",
}

CORE_TOOLS = ("list_files", "read_file", "finish")


class ToolSet:
    def __init__(self, repo_path, test_command, search_provider=None):
        self.repo_path = repo_path
        self.test_command = test_command
        self.search_provider = search_provider
        self.used_recently = []
        self.masked_out_tokens = 0

    def visible_schemas(self, mask=True):
        """Return (schema_text, tokens_saved_by_masking)."""
        schemas = dict(SCHEMAS)
        if self.search_provider is None:
            schemas.pop("search", None)
        if not mask:
            return "\n".join(schemas.values()), 0
        visible = set(CORE_TOOLS) | set(self.used_recently[-2:])
        hidden = [k for k in schemas if k not in visible]
        saved = sum(len(schemas[k]) // 4 for k in hidden)
        self.masked_out_tokens += saved
        return "\n".join(schemas[k] for k in schemas if k in visible), saved

    def _safe(self, rel):
        path = os.path.normpath(os.path.join(self.repo_path, rel))
        if not path.startswith(os.path.normpath(self.repo_path)):
            raise ValueError("path escapes repo: " + rel)
        return path

    def list_files(self):
        out = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in files:
                out.append(os.path.relpath(os.path.join(root, f),
                                           self.repo_path))
        return "\n".join(sorted(out))

    def read_file(self, rel):
        with open(self._safe(rel)) as fh:
            return fh.read()

    def write_file(self, rel, content):
        path = self._safe(rel)
        os.makedirs(os.path.dirname(path) or self.repo_path, exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
        return "wrote " + rel

    def run_tests(self):
        proc = subprocess.run(self.test_command, shell=True,
                              cwd=self.repo_path, capture_output=True,
                              text=True, timeout=120)
        tail = (proc.stdout + proc.stderr)[-2000:]
        return ("PASS" if proc.returncode == 0 else "FAIL") + "\n" + tail

    def search(self, query):
        if self.search_provider is None:
            return "search unavailable (no provider configured)"
        results = self.search_provider.search(query, max_results=3)
        lines = []
        for r in results:
            lines.append("- %s | %s" % (r.get("title", ""),
                                        r.get("snippet", "")[:300]))
        return "\n".join(lines) if lines else "no results"


def parse_action(text):
    """Parse one ACTION block from model output.

    Returns (action, argument, rest). `rest` is the body for write_file.
    """
    lines = text.strip().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().split()[0]
            arg = line.split(":", 1)[1].strip()
            arg = arg[len(action):].strip()
            rest = "\n".join(lines[i + 1:])
            return action, arg, rest
    return "finish", "", ""

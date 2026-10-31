"""Model interface for FreshCode.

Two implementations:
- StubModel: deterministic, offline. Used by tests and demos. It returns
  canned patches keyed by task id for the sample tasks, and "no fix"
  otherwise. Numbers produced with StubModel demonstrate the pipeline
  only and are NEVER real agent measurements.
- OpenAICompatibleModel: talks to any OpenAI-compatible chat-completions
  endpoint (Groq, OpenAI, local servers) via urllib. Credentials come
  from environment variables only -- never hardcoded, never logged.
"""

import json
import os
import urllib.request


def estimate_tokens(text):
    """Rough token estimate (chars / 4). Used when the model does not
    report usage. Reported usage is always preferred when present."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class ModelResponse:
    def __init__(self, text, usage=None):
        self.text = text
        self.usage = usage or {}

    def tokens_used(self):
        if "total_tokens" in self.usage:
            return int(self.usage["total_tokens"])
        return estimate_tokens(self.text)


class ModelClient:
    """Interface every model must satisfy."""

    def complete(self, messages):
        raise NotImplementedError


class StubModel(ModelClient):
    """Deterministic offline model for tests and demos.

    `patches` maps task_id -> patch text (the full replacement content
    for the task's target file). For unknown tasks it returns a
    FINISH with no patch. Its outputs are canned, so any metric
    computed with StubModel is a pipeline smoke signal, not a result.
    """

    def __init__(self, patches=None):
        self.patches = patches or {}
        self.calls = {}

    def complete(self, messages):
        task_id = None
        for m in messages:
            if m.get("role") == "system" and "TASK_ID:" in m.get("content", ""):
                for line in m["content"].splitlines():
                    if line.startswith("TASK_ID:"):
                        task_id = line.split(":", 1)[1].strip()
        n = self.calls.get(task_id, 0)
        self.calls[task_id] = n + 1
        patch = self.patches.get(task_id)
        if patch is None:
            text = "ACTION: finish\nI cannot fix this task."
        elif n == 0:
            text = "ACTION: write_file\n" + patch
        elif n == 1:
            text = "ACTION: run_tests"
        else:
            text = "ACTION: finish\nDone."
        return ModelResponse(text, {"total_tokens": estimate_tokens(text)})


class OpenAICompatibleModel(ModelClient):
    """OpenAI-compatible chat client (Groq / OpenAI / local endpoints).

    Config via env: FRESHCODE_MODEL_BASE_URL, FRESHCODE_MODEL_NAME,
    FRESHCODE_MODEL_API_KEY. The key is never printed or logged.
    """

    def __init__(self, base_url=None, model=None, api_key=None, timeout=120):
        self.base_url = (base_url or os.environ.get(
            "FRESHCODE_MODEL_BASE_URL",
            "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get(
            "FRESHCODE_MODEL_NAME", "gpt-4o-mini")
        self.api_key = api_key or os.environ.get("FRESHCODE_MODEL_API_KEY", "")
        self.timeout = timeout

    def complete(self, messages):
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.api_key},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.load(resp)
        choice = data["choices"][0]["message"]
        return ModelResponse(choice.get("content", ""),
                             data.get("usage", {}))

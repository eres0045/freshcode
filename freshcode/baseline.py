"""Baseline agent: plain ReAct, no token-saving mechanisms.

Same task interface and same model as the FreshCode agent, but:
- no tool-schema masking (all schemas every turn),
- no context summarization (full history every turn),
- no failure-loop cutoff,
- no search tool (docs would have to be pasted in; the baseline gets
  no retrieval).

This makes token/pass-rate comparisons apples-to-apples: same tasks,
same model, same turn cap; only the mechanisms differ.
"""

from .agent import run_agent


def run_baseline(task, model, max_turns=25):
    report = run_agent(task, model, search_provider=None,
                       max_turns=max_turns, mask=False,
                       summarize=False, failure_cutoff=False)
    report["agent"] = "baseline"
    return report

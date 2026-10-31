"""FreshCode agent (B1): token-frugal coding agent.

Token-saving mechanisms, all four, each measurable:
1. Tool-schema masking: only recently used + core tool schemas are sent
   (see freshcode/tools.py). Tokens saved are recorded.
2. Context summarization: when the transcript exceeds
   `summarize_after_tokens`, older turns are replaced by a short
   summary line instead of being re-sent every turn.
3. Failure-loop cutoff: after MAX_IDENTICAL_FAILS identical failed
   actions, the agent gets ONE redirect hint; if the same action
   fails again, the run stops instead of burning more tokens.
4. Live retrieval instead of pasted docs: the `search` tool returns
   short snippets (max 3 results, truncated) so the agent never needs
   long documentation pasted into context.

The agent works on a task dict: {id, repo, target_file, description,
test_command}. It returns a run report with token/turn/pass data.
"""

from .model import estimate_tokens
from .tools import ToolSet, parse_action

MAX_TURNS = 25
MAX_IDENTICAL_FAILS = 3
SUMMARIZE_AFTER_TOKENS = 3000


def _summarize_turns(turns):
    """Collapse older turns into one summary line."""
    if len(turns) <= 4:
        return turns
    kept = turns[-4:]
    summary = ("[SUMMARY: %d earlier turns collapsed: actions=%s]" %
               (len(turns) - 4,
                ",".join(t["action"] for t in turns[:-4])))
    return [{"action": "summary", "text": summary}] + kept


def run_agent(task, model, search_provider=None, max_turns=MAX_TURNS,
              mask=True, summarize=True, failure_cutoff=True):
    """Run the agent on one task. Returns a report dict."""
    tools = ToolSet(task["repo"], task["test_command"],
                    search_provider=search_provider)
    history = []  # turns: {action, text}
    tokens_in = 0
    tokens_out = 0
    turns = 0
    passed = False
    stopped_reason = "finished"
    fail_streak = {}  # action signature -> consecutive failures
    last_failed_sig = None

    system = ("You are FreshCode, a coding agent. Fix the task with as "
              "few tokens as possible. Use ACTION lines only.\n"
              "TASK_ID: %s\nTask: %s\nTarget file: %s" %
              (task["id"], task["description"], task["target_file"]))

    for turn in range(max_turns):
        turns = turn + 1
        schemas, saved = tools.visible_schemas(mask=mask)
        ctx_turns = _summarize_turns(history) if summarize else history
        ctx = "\n".join("%s: %s" % (t["action"], t["text"][:800])
                        for t in ctx_turns)
        prompt = ("%s\n\nTOOLS:\n%s\n\nREPO FILES:\n%s\n\nHISTORY:\n%s\n"
                  "Reply with one ACTION line." %
                  (system, schemas, tools.list_files(), ctx))
        tokens_in += estimate_tokens(prompt)
        resp = model.complete([{"role": "system", "content": system},
                               {"role": "user", "content": prompt}])
        tokens_out += resp.tokens_used()
        action, arg, rest = parse_action(resp.text)
        tools.used_recently.append(action)
        sig = action + ":" + arg
        try:
            if action == "list_files":
                out = tools.list_files()
            elif action == "read_file":
                out = tools.read_file(arg)
            elif action == "write_file":
                out = tools.write_file(arg or task["target_file"], rest)
            elif action == "run_tests":
                out = tools.run_tests()
                if out.startswith("PASS"):
                    passed = True
            elif action == "search":
                out = tools.search(arg)
            elif action == "finish":
                stopped_reason = "finished"
                break
            else:
                out = "unknown action: " + action
        except Exception as exc:  # noqa: BLE001 - agent must survive tool errors
            out = "ERROR: " + str(exc)
        history.append({"action": action, "text": out[:800]})
        if out.startswith("ERROR") or out.startswith("FAIL"):
            fail_streak[sig] = fail_streak.get(sig, 0) + 1
            if failure_cutoff and fail_streak[sig] >= MAX_IDENTICAL_FAILS:
                if last_failed_sig != sig:
                    # One redirect, then stop on repeat.
                    history.append({"action": "redirect",
                                    "text": "Same action failed repeatedly; "
                                            "try a different approach."})
                    last_failed_sig = sig
                    fail_streak[sig] = 0
                else:
                    stopped_reason = "failure_loop_cutoff"
                    break
        else:
            fail_streak[sig] = 0
    else:
        stopped_reason = "max_turns"

    # Final verification: run tests once at the end if not already passing.
    if not passed:
        final = tools.run_tests()
        passed = final.startswith("PASS")

    return {
        "task_id": task["id"],
        "passed": passed,
        "turns": turns,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "tokens_saved_by_masking": tools.masked_out_tokens,
        "stopped_reason": stopped_reason,
    }

# FreshCode — Token-frugal coding agent with live freshness verification

**Geek Room Global AI Hackathon entry (HackCulture) — Bifrost B1 + Tavily T1, one integrated project.**

## What it is

FreshCode is a CLI coding agent that completes real coding tasks while
using as few tokens as possible (Bifrost B1), and runs every factual
claim in its own output through a freshness checker that re-verifies
claims against live sources and attaches a per-claim freshness score
with sources (Tavily T1).

The two halves are genuinely integrated, not glued together: the
agent's context retrieval uses live search instead of stale parametric
knowledge — retrieved evidence replaces long pasted docs, which is
itself a token-saving move.

## Token-saving mechanisms (all four, each measured)

1. **Tool-schema masking** — only recently used + core tool schemas are
   sent to the model; tokens saved are recorded per run.
2. **Context summarization** — older turns collapse into a summary line
   once the transcript passes a threshold, instead of being re-sent.
3. **Failure-loop cutoff** — after 3 identical failed actions the agent
   gets one redirect; a repeat after that stops the run.
4. **Live retrieval instead of pasted docs** — the `search` tool returns
   short snippets (max 3 results, truncated).

A plain ReAct baseline (no mechanisms, same tasks, same model) ships
alongside so every comparison is apples-to-apples.

## Run it

```bash
# Tests (offline, stdlib only)
python3 -m unittest discover -s tests -v

# Pipeline demo (STUB MODE -- see honesty section)
python3 run_demo.py
```

Real runs need a model and (for live freshness) a Tavily key, all via
environment variables — never hardcoded:

```bash
export FRESHCODE_MODEL_BASE_URL="https://api.groq.com/openai/v1"
export FRESHCODE_MODEL_NAME="llama-3.3-70b-versatile"
export FRESHCODE_MODEL_API_KEY="..."   # never print or commit this
export TAVILY_API_KEY="..."            # same rule
```

## Frozen evaluation sets (frozen 2026-10-31, before any tuning)

- **20 coding tasks** (`data/tasks.json` + `data/repos_task/<id>/`):
  one isolated bug per task across three tiny repos (calc, strings,
  config), each with its own pass/fail tests. Verified: 19 tasks fail
  pre-fix and pass with the gold patch; t18 (`flatten_dict`) is a
  behavior-preservation task that passes either way. Do not tune the
  agent against these after freezing except to fix crashes — tuning
  on the eval set invalidates the numbers.
- **100 labeled claims** (`data/claims.json`): 50 fresh / 50 stale
  across pricing, API versions, laws, and leadership, with ground
  truth labels and source URLs, as of October 2026.

Hashes (sha256):
- `data/tasks.json`: `0bf506b3cba0d0fec7c1703f9fed4ed761f6d7f55997fce6c46c56fd89fc3f46`
- `data/claims.json`: `80d6267599ac155313cc59fd1890cf6a8e4b05a1713ec26e31112f101972f74d`

## Honesty section (read before quoting any number)

- **Stub mode is not measurement.** `StubModel` returns canned gold
  patches and `StubProvider` returns canned verdicts. Any number
  produced in stub mode demonstrates that the pipeline runs; it is
  NOT an agent result. Real targets from research: 30–45% fewer tokens
  than baseline at equal or better pass rate (20–30 tasks), detector
  precision ≥ 0.85 / recall ≥ 0.80 on the 100-claim set. Those targets
  are **not yet measured** — no real-model run has happened yet.
- **No live Tavily key yet.** Tavily key issuance for this event is
  unverified; check the Geek Room Discord announcements before
  relying on live Tavily. Until then the freshness checker runs in
  clearly labelled stub mode.
- **Verdict scoring is a first-version heuristic** (keyword overlap +
  recency cues), documented in `freshcode/freshness/verdict.py`. The
  labeled-set metrics measure it honestly rather than claiming
  perfection.

## Judging-criteria mapping (Geek Room, 6 criteria, no weights published)

- **Innovation:** two hard problems fused — token frugality and
  temporal freshness — in one agent loop.
- **Technical execution:** two measured tables (tokens/pass rate,
  precision/recall) on frozen sets, re-runnable by judges.
- **Problem and potential impact:** LLM answers go stale constantly
  (prices, API versions, laws, leadership); coding agents burn tokens
  on every turn. Both problems are real and daily.
- **Use of AI:** an agent loop plus a verification pipeline, both
  visible in the code and the demo.
- **User experience:** a CLI agent with a run report (tokens, turns,
  pass/fail, freshness scores with sources) per task.
- **Scalability:** works on any repo and any OpenAI-compatible model
  via environment configuration.

## Honest limits

- The freshness verdict heuristic will misjudge edge cases; the
  labeled set exists to measure that, not hide it.
- Token counts are estimates (chars/4) unless the model reports usage.
- The agent's action language is line-based (`ACTION:` lines) so any
  chat model can use it without function calling — simpler, but less
  robust than structured tool calls for some models.
- No submission has been made to HackCulture. A pre-submit checkpoint
  with Ronit is required before any submission.

## License

MIT

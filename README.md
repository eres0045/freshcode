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
# Tests (offline, stdlib only) — 41 tests, all green
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
  NOT an agent result. Measured stub numbers (2026-10-31): full
  20-task comparison, agent 589.7 tokens/task vs baseline 620.0
  (4.9% savings, both pass@1 1.0, 3.0 turns/task) — this is a
  masking-only floor, because the stub writes gold on turn 1 and the
  loop barely exercises summarization or retrieval. It is NOT the
  30–45% token-saving claim. Full-100 detector numbers with stub
  verdicts (precision/recall 1.0) are tautological by construction
  and are likewise NOT measurements.
- **Live-heuristic calibration probe (real measurement, 20 claims,
  hand-written current-fact evidence, October 2026):** precision
  1.0, recall 0.4 (4/10 stale caught); fresh scores mean 0.993,
  range [0.929, 1.000]; stale scores mean 0.620, range
  [0.250, 0.929]. The ranges touch at 0.929 and 5 of the 6 missed
  stale claims score ≥ 0.75 — so the freshness score alone is NOT
  a reliable separator, and the heuristic catches dotted-version,
  year, and price mismatches but NOT bare-number versions
  ("latest is 17" vs "21") or entity replacements ("Biden" vs
  "Trump"). A full-100 live-heuristic calibration cannot be
  measured without evidence snippets for all 100 claims; it is not
  claimed here.
- **Hardening pass (2026-10-31, 25 new tests):** fixed a real
  path-traversal hole (plain `startswith` was fooled by sibling
  directories like `/tmp/repo_evil`); closed the alternating-action
  failure loop with a global redirect budget (max 2 per run); made
  temp-dir cleanup exception-safe; made malformed claim labels fail
  loudly instead of silently counting as misses; fixed version
  comparison so 3.13 vs 3.13.0 is the same line, not a mismatch;
  fixed tokenization so sentence-final punctuation no longer
  depresses keyword overlap. No frozen evaluation data was changed
  in this pass (all 100 claim labels re-verified correct as of
  October 2026).
- **Real targets from research: 30–45% fewer tokens
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
  labeled set exists to measure that, not hide it. Known misses
  (measured 2026-10-31): bare-number version changes and entity
  replacements are not caught; the freshness score overlaps between
  fresh and stale claims, so it must not be used as a lone threshold.
- The agent's pass verdict is the repo's own tests only: a patch
  that hardcodes a visible answer passes visibly while breaking
  hidden behavior, and the agent cannot see that. Hidden tests per
  task would close this gap and are a recommended next step.
- Token counts are estimates (chars/4) unless the model reports usage.
- The agent's action language is line-based (`ACTION:` lines) so any
  chat model can use it without function calling — simpler, but less
  robust than structured tool calls for some models.
- No submission has been made to HackCulture. A pre-submit checkpoint
  with Ronit is required before any submission.

## License

MIT

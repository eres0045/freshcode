"""Search providers for the freshness checker (T1, step 2).

Interface: search(query, max_results) -> list of
{"title", "snippet", "url", "date"} dicts.

- StubProvider: deterministic canned results, for tests and demos.
  Its `knowledge` maps a lowercase substring -> (verdict_hint, source).
  Demo/stub mode is labelled by callers, never passed off as live.
- TavilyProvider: real Tavily search via `tavily-python` when installed
  and TAVILY_API_KEY is set in the environment. The key is never
  printed, logged, or stored. If the package or key is missing it
  raises a clear error instead of silently falling back (silent
  fallback would corrupt measurements).
"""

import os


class SearchProvider:
    def search(self, query, max_results=5):
        raise NotImplementedError


class StubProvider(SearchProvider):
    """Deterministic canned search, keyed by substring match."""

    def __init__(self, knowledge=None):
        # knowledge: substring -> list of result dicts
        self.knowledge = knowledge or {}
        self.calls = 0

    def search(self, query, max_results=5):
        self.calls += 1
        q = query.lower()
        for key, results in self.knowledge.items():
            if key.lower() in q:
                return results[:max_results]
        return [{"title": "No live source (stub)",
                 "snippet": "Stub provider has no canned result for this query.",
                 "url": "", "date": ""}]


class TavilyProvider(SearchProvider):
    """Real Tavily search. Requires tavily-python + TAVILY_API_KEY."""

    def __init__(self, api_key=None):
        try:
            from tavily import TavilyClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "tavily-python is not installed; install it or use "
                "StubProvider for demos") from exc
        key = api_key or os.environ.get("TAVILY_API_KEY", "")
        if not key:
            raise RuntimeError(
                "TAVILY_API_KEY is not set in the environment")
        self.client = TavilyClient(api_key=key)
        self.calls = 0
        self.credits_used = 0

    def search(self, query, max_results=5):
        self.calls += 1
        resp = self.client.search(query=query, max_results=max_results,
                                  search_depth="advanced")
        results = []
        for r in resp.get("results", []):
            results.append({"title": r.get("title", ""),
                            "snippet": r.get("content", "")[:500],
                            "url": r.get("url", ""),
                            "date": r.get("published_date", "")})
        # Advanced search costs 2 credits per the Tavily docs.
        self.credits_used += 2
        return results

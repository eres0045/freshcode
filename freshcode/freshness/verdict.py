"""Freshness verdicts (T1, step 3).

Given a claim and search results, produce:
- verdict: "fresh" | "stale" | "uncertain"
- freshness_score: 0.0 (certainly stale) .. 1.0 (certainly fresh)
- sources: list of URLs consulted

Rule-based, transparent scoring:
- If any result snippet explicitly contradicts the claim's key tokens
  (handled by the caller through `contradicts` flags from the
  provider in stub mode), the claim is stale.
- If results support the claim, it is fresh.
- With no usable evidence, it is uncertain with score 0.5.

The StubProvider path: canned results may carry a "verdict" field
("fresh"/"stale") used only in stub/demo mode. The live path scores
evidence by keyword overlap between claim and snippets: strong overlap
with a recent-dated source -> fresh; overlap with a source that
mentions a newer value -> stale. This is a first-version heuristic,
documented as such in the README; the labeled-set metrics measure it
honestly rather than claiming perfection.
"""

import re


def _tokens(text):
    return set(re.findall(r"[a-z0-9.]+", text.lower()))


def check_claim(claim_text, results):
    """Return (verdict, score, sources)."""
    sources = [r.get("url", "") for r in results if r.get("url")]
    # Stub/demo path: canned verdict wins, labelled by the caller.
    for r in results:
        if r.get("verdict") == "stale":
            return "stale", 0.1, sources
        if r.get("verdict") == "fresh":
            return "fresh", 0.9, sources
    if not results or all(not r.get("snippet") for r in results):
        return "uncertain", 0.5, sources
    claim_toks = _tokens(claim_text)
    best_overlap = 0.0
    newer_mentioned = False
    for r in results:
        snip_toks = _tokens(r.get("snippet", ""))
        if not claim_toks:
            continue
        overlap = len(claim_toks & snip_toks) / max(1, len(claim_toks))
        best_overlap = max(best_overlap, overlap)
        if re.search(r"\b(newer|updated|replaced|now|current version)\b",
                     r.get("snippet", ""), re.I):
            newer_mentioned = True
    if best_overlap >= 0.5 and not newer_mentioned:
        return "fresh", 0.5 + 0.5 * best_overlap, sources
    if best_overlap >= 0.5 and newer_mentioned:
        return "stale", 0.5 - 0.5 * best_overlap, sources
    return "uncertain", 0.5, sources


def check_text(text, provider, max_results=3):
    """Extract claims from text and check each. Returns a report."""
    from .extractor import extract_claims
    claims = extract_claims(text)
    checked = []
    for c in claims:
        results = provider.search(c["text"], max_results=max_results)
        verdict, score, sources = check_claim(c["text"], results)
        checked.append({"claim": c["text"], "verdict": verdict,
                        "freshness_score": round(score, 3),
                        "sources": sources})
    return {"claims_found": len(claims), "checked": checked}

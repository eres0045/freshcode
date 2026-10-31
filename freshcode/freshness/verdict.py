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
- A claim about the future (future-tense markers, or a year later
  than the current year) is NEVER scored fresh: the future cannot be
  verified against today's sources, so it is uncertain.
- Mismatch rules on the best-overlap snippet: if the claim and the
  snippet each carry exactly one (different) year, or carry dotted
  version numbers with no prefix-compatible match (3.13 vs 3.13.0
  is the same line, not a mismatch), or disjoint prices, the claim
  is stale.
  These catch the classic "current X is <old value>" pattern that
  plain keyword overlap scores as fresh. They deliberately do NOT
  cover bare-number versions ("latest is 17" vs "21") or entity
  replacements ("Biden" vs "Trump"), which need real entity
  resolution — those remain known limitations (see README).

The StubProvider path: canned results may carry a "verdict" field
("fresh"/"stale") used only in stub/demo mode. The live path scores
evidence by keyword overlap between claim and snippets: strong overlap
with a recent-dated source -> fresh; overlap with a source that
mentions a newer value -> stale. This is a first-version heuristic,
documented as such in the README; the labeled-set metrics measure it
honestly rather than claiming perfection.
"""

import datetime
import re


def _tokens(text):
    # Dots inside words/versions are kept ("node.js", "3.13.0"), but
    # sentence-final punctuation is NOT part of a token: the old
    # [a-z0-9.]+ pattern tokenized "union." and "union" differently,
    # silently depressing overlap whenever the claim ended a sentence.
    return set(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", text.lower()))


def _version_tuple(version):
    return tuple(int(p) for p in version.split("."))


def _versions_conflict(claim_vers, snip_vers):
    """True only if NO claim version matches any snippet version.

    A snippet version counts as a match when one is a dot-prefix of
    the other (3.13 and 3.13.0 are the same version line, not a
    mismatch) — without this, affirming evidence like "3.13.0 was
    released" would falsely flag a "3.13" claim as stale.
    """
    for cv in claim_vers:
        ct = _version_tuple(cv)
        for sv in snip_vers:
            st = _version_tuple(sv)
            if ct == st[:len(ct)] or st == ct[:len(st)]:
                return False
    return True


_FUTURE_MARKERS = re.compile(
    r"\b(will be|will launch|will release|will land|upcoming|planned"
    r"|expected|scheduled|set to)\b", re.I)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_VERSION_RE = re.compile(r"\b\d+\.\d+(?:\.\d+)?\b")
_PRICE_RE = re.compile(r"[$€£]\s?\d[\d,.]*")


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
    # Future claims are unverifiable today: never score them fresh.
    if _FUTURE_MARKERS.search(claim_text):
        return "uncertain", 0.5, sources
    this_year = datetime.datetime.now().year
    if any(int(y) > this_year for y in _YEAR_RE.findall(claim_text)):
        return "uncertain", 0.5, sources
    claim_toks = _tokens(claim_text)
    best_overlap = 0.0
    best_snippet = ""
    newer_mentioned = False
    for r in results:
        snippet = r.get("snippet", "")
        snip_toks = _tokens(snippet)
        if not claim_toks:
            continue
        overlap = len(claim_toks & snip_toks) / max(1, len(claim_toks))
        if overlap > best_overlap:
            best_overlap = overlap
            best_snippet = snippet
        if re.search(r"\b(newer|updated|replaced|now|current version)\b",
                     snippet, re.I):
            newer_mentioned = True
    if best_overlap >= 0.5:
        claim_years = set(_YEAR_RE.findall(claim_text))
        snip_years = set(_YEAR_RE.findall(best_snippet))
        if (len(claim_years) == 1 and len(snip_years) == 1
                and claim_years != snip_years):
            return "stale", 0.25, sources
        claim_vers = set(_VERSION_RE.findall(claim_text))
        snip_vers = set(_VERSION_RE.findall(best_snippet))
        if claim_vers and snip_vers and _versions_conflict(claim_vers,
                                                           snip_vers):
            return "stale", 0.25, sources
        claim_prices = set(_PRICE_RE.findall(claim_text))
        snip_prices = set(_PRICE_RE.findall(best_snippet))
        if claim_prices and snip_prices and not (claim_prices & snip_prices):
            return "stale", 0.25, sources
        if newer_mentioned:
            return "stale", 0.5 - 0.5 * best_overlap, sources
        return "fresh", 0.5 + 0.5 * best_overlap, sources
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

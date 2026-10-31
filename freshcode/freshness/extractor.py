"""Claim extraction from agent output text (T1, step 1).

Extracts sentences that carry checkable factual claims: those mentioning
version numbers, prices/currency, years/dates, leadership roles, or
"current/latest" assertions. This is deliberately rule-based and
transparent: every extracted claim can be traced to a source sentence.
"""

import re

PATTERNS = [
    re.compile(r"\bv?\d+\.\d+(\.\d+)?\b"),          # version numbers
    re.compile(r"[$€£]\s?\d[\d,.]*"),                # prices
    re.compile(r"\b(19|20)\d{2}\b"),                 # years
    re.compile(r"\b(current|latest|newest)\b", re.I),
    re.compile(r"\b(CEO|CTO|president|founder)\b", re.I),
    re.compile(r"\b(version|release|price|costs?)\b", re.I),
]


def extract_claims(text):
    """Split text into sentences; keep sentences matching any pattern.

    Returns a list of {"text": sentence, "index": i}.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    claims = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue
        if any(p.search(sent) for p in PATTERNS):
            claims.append({"text": sent, "index": i})
    return claims

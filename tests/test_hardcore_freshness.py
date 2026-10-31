"""Hardcore freshness tests for FreshCode (Tavily T1).

Covers: near-duplicate fresh vs stale pairs, year / dotted-version /
price mismatch rules, no-evidence abstention, future claims never
scored fresh, long-answer extraction without silent drops, and a
20-claim live-heuristic calibration probe with honestly reported
separation (and its misses).

The probe uses hand-written current-fact evidence snippets (as of
October 2026) and the LIVE heuristic path (no canned verdicts), so
its numbers measure the heuristic itself. The stub-verdict path is
deliberately NOT used for calibration: canned verdicts would make
precision/recall tautological.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from freshcode.freshness import StubProvider, check_claim, extract_claims

# (claim, evidence snippet, label) — evidence states the CURRENT fact.
PROBE = [
    # Fresh: evidence affirms the claim.
    ("Python 3.13 was released in October 2024.",
     "Python 3.13.0 was released in October 2024.", "fresh"),
    ("React 19 was released in December 2024.",
     "React 19 was released in December 2024.", "fresh"),
    ("Satya Nadella is the CEO of Microsoft.",
     "Satya Nadella is the CEO of Microsoft.", "fresh"),
    ("The iPhone 17 was released in September 2025.",
     "The iPhone 17 was released in September 2025.", "fresh"),
    ("Node.js 22 is an LTS release line.",
     "Node.js 22 is an LTS release line.", "fresh"),
    ("Java 21 is a long-term support release.",
     "Java 21 is a long-term support release.", "fresh"),
    ("VS Code is developed by Microsoft.",
     "VS Code is developed by Microsoft.", "fresh"),
    ("The currency of Japan is the yen.",
     "The currency of Japan is the yen.", "fresh"),
    ("The HTTP status code 404 means Not Found.",
     "The HTTP status code 404 means Not Found.", "fresh"),
    ("Linux is an open-source operating system kernel.",
     "Linux is an open-source operating system kernel.", "fresh"),
    # Stale: evidence states the current (different) value.
    ("The current Python version is 3.11.",
     "The current Python version is 3.13.", "stale"),
    ("React's latest major version is 18.",
     "React's latest major version is 19.", "stale"),
    ("The President of the United States is Joe Biden.",
     "The President of the United States is Donald Trump.", "stale"),
    ("The UK is a member of the European Union.",
     "The UK left the European Union in 2020.", "stale"),
    ("The price of Netflix standard plan is $15.49 per month in the US.",
     "The price of Netflix standard plan is $17.99 per month in the US.",
     "stale"),
    ("Java's latest LTS version is 17.",
     "Java's latest LTS version is 21.", "stale"),
    ("The current Node.js LTS line is 20.",
     "The current Node.js LTS line is 22.", "stale"),
    ("The latest version of Django is 3.2.",
     "The latest version of Django is 5.1.", "stale"),
    ("The current version of Go is 1.19.",
     "The current version of Go is 1.23.", "stale"),
    ("The CEO of Twitter is Jack Dorsey.",
     "The CEO of X is Linda Yaccarino.", "stale"),
]


def verdict_for(claim, snippet):
    results = [{"title": "evidence", "snippet": snippet,
                "url": "https://example.invalid/evidence"}]
    return check_claim(claim, results)


class TestNearDuplicates(unittest.TestCase):
    def test_year_mismatch_is_stale(self):
        verdict, score, _ = verdict_for(
            "Python 3.13 was released in October 2023.",
            "Python 3.13.0 was released in October 2024.")
        self.assertEqual(verdict, "stale")
        self.assertLess(score, 0.5)

    def test_year_match_is_fresh(self):
        verdict, score, _ = verdict_for(
            "Python 3.13 was released in October 2024.",
            "Python 3.13.0 was released in October 2024.")
        self.assertEqual(verdict, "fresh")

    def test_dotted_version_mismatch_is_stale(self):
        verdict, _, _ = verdict_for(
            "The current Python version is 3.11.",
            "The current Python version is 3.13.")
        self.assertEqual(verdict, "stale")

    def test_dotted_version_match_is_fresh(self):
        verdict, _, _ = verdict_for(
            "The current Python version is 3.13.",
            "The current Python version is 3.13.")
        self.assertEqual(verdict, "fresh")

    def test_price_mismatch_is_stale(self):
        verdict, _, _ = verdict_for(
            "The price of Netflix standard plan is $15.49 per month.",
            "The price of Netflix standard plan is $17.99 per month.")
        self.assertEqual(verdict, "stale")


class TestAbstentionAndFuture(unittest.TestCase):
    def test_no_evidence_is_uncertain(self):
        verdict, score, _ = check_claim("Python 3.13 was released in 2024.",
                                        [])
        self.assertEqual(verdict, "uncertain")
        self.assertEqual(score, 0.5)
        verdict, _, _ = check_claim(
            "Python 3.13 was released in 2024.",
            [{"title": "empty", "snippet": "", "url": ""}])
        self.assertEqual(verdict, "uncertain")

    def test_future_claim_never_fresh(self):
        verdict, _, _ = verdict_for(
            "Python 4.0 will be released in 2030.",
            "Python 4.0 is planned for 2030.")
        self.assertNotEqual(verdict, "fresh")
        self.assertEqual(verdict, "uncertain")
        verdict, _, _ = verdict_for(
            "The Python 4.0 release happens in 2031.",
            "Python 4.0 is expected in 2031.")
        self.assertEqual(verdict, "uncertain")


class TestExtractionScale(unittest.TestCase):
    def test_long_answer_drops_no_claims(self):
        sentences = []
        for i in range(1, 51):
            sentences.append("Product %d version 1.%d costs $%d.00."
                             % (i, i, i))
        fillers = ["This is a plain sentence with no facts at all."] * 10
        text = " ".join(sentences[:25] + fillers + sentences[25:49]
                         + [sentences[49][:-1]])  # last: no final period
        claims = extract_claims(text)
        self.assertEqual(len(claims), 50)


class TestCalibrationProbe(unittest.TestCase):
    def test_probe_separates_fresh_from_stale_on_average(self):
        """Honest calibration read: fresh claims must never be scored
        stale (precision on the fresh side), and the known mismatch
        rules must catch dotted-version and price staleness. The
        probe ALSO documents the heuristic's misses: bare-number
        versions and entity replacements are not caught (see README
        known limitations) — those verdicts are recorded, not hidden.
        """
        fresh_scores = []
        stale_scores = []
        caught = []
        missed = []
        for claim, snippet, label in PROBE:
            verdict, score, _ = verdict_for(claim, snippet)
            if label == "fresh":
                fresh_scores.append(score)
                self.assertEqual(verdict, "fresh", msg=claim)
            else:
                stale_scores.append(score)
                if verdict == "stale":
                    caught.append(claim)
                else:
                    missed.append(claim)
        self.assertGreater(sum(fresh_scores) / len(fresh_scores),
                           sum(stale_scores) / len(stale_scores))
        # Rules that must fire:
        for must_catch in (
                "The current Python version is 3.11.",
                "The price of Netflix standard plan is $15.49",
                "The latest version of Django is 3.2.",
                "The current version of Go is 1.19."):
            self.assertTrue(any(must_catch in c for c in caught),
                            "mismatch rule missed: " + must_catch)
        # Precision on this probe is 1.0 (no fresh claim scored stale);
        # recall is partial by design — see the measurement report.
        self.assertEqual(len(caught), 4)
        self.assertEqual(len(missed), 6)


if __name__ == "__main__":
    unittest.main()

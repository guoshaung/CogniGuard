"""Query-relevant, measured-budget excerpts; never receives answer/gold labels.

This opt-in adapter is extractive, not an abstractive summarizer. Exact source
wording is deliberately charged to the same runtime disclosure cost used by
the legacy controller. The existing post-generation gate remains mandatory.
"""
from __future__ import annotations

import re

STOP = set("a an the of in on at to for by with from is was are were be been and or which what who when where how did do does this that it its please quote exact text part continue wording explain original".split())


def measured_cost(measure):
    return min(1., .45 * measure["lcs_coverage"] + .25 * measure["ngram_coverage"]
               + .20 * measure["lexical_cosine"] + .10 * measure["key_knowledge_unit_recovery"])


def plan_excerpt(query, chunk, remaining, ngram_size=5, max_words=24):
    from .core import disclosure_measurement, tokens
    words = chunk.text.split()
    terms = set(tokens(query)) - STOP
    options = []
    for width in (6, 10, 14, 18, 24):
        width = min(width, max_words, len(words))
        if width <= 0:
            continue
        starts = sorted(set(range(0, max(1, len(words) - width + 1), max(1, width // 3)))
                        | {max(0, len(words) - width)})
        ranked = []
        for start in starts:
            text = " ".join(words[start:start + width])
            relevance = len(terms & set(tokens(text))) / max(1, len(terms))
            ranked.append((relevance, start, text))
        for relevance, start, text in sorted(ranked, key=lambda x: (-x[0], x[1]))[:6]:
            if relevance <= 0:
                continue
            rendered = f"教学回答：引用摘录：{text}"
            cost = measured_cost(disclosure_measurement(rendered, chunk.text, chunk.knowledge_units, ngram_size))
            if cost <= remaining + 1e-9:
                options.append({"action": "controlled_quote", "content": text, "estimated_copyright_cost": cost,
                                "query_relevance": relevance, "source_start_word": start, "source_words": width,
                                "provenance_required": True, "residual_copyright_risk": cost})
    if not options:
        return {"action": "refuse", "content": "", "estimated_copyright_cost": 0.,
                "reason": "no relevant excerpt fits the measured release budget"}
    # Relevance first, then contextual length; ties prefer earlier source text.
    return max(options, key=lambda x: (x["query_relevance"], x["source_words"], -x["source_start_word"]))

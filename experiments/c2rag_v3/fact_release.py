"""Output-side release gate for trusted internal RAG transformation.

Source passages are available inside the authorized generator, not delivered
to the user. Only short answers with source-local citation witnesses may leave.
Witness checks establish source presence, NOT logical entailment or truth.
"""
from __future__ import annotations

import re


def normalized(text):
    return " ".join(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", str(text).lower()))


def source_quote_matches(quote, source):
    """Accept explicit ellipses only when every nontrivial span is in order.

    Ellipses are not wildcard authorization: all spans must belong to this
    same supplied source. Citation witnesses remain internal, not delivered.
    """
    text, full = normalized(source), normalized(quote)
    if len(full) >= 8 and full in text:
        return True
    parts = [normalized(p) for p in re.split(r"\.{3,}|…+", quote) if normalized(p)]
    if len(parts) < 2 or any(len(p.split()) < 3 for p in parts):
        return False
    start = 0
    for part in parts:
        found = text.find(part, start)
        if found < 0:
            return False
        start = found + len(part)
    return True


def gate_fact(output, documents, ledger, budget=.15):
    from .core import disclosure_measurement, tokens
    from .evidence_release import measured_cost
    if not isinstance(output, dict) or output.get("abstain") is not False:
        return {"answer": "", "released": False, "reason": "abstained_or_invalid_schema"}
    answer = output.get("answer")
    if not isinstance(answer, str) or not answer.strip() or len(tokens(answer)) > 12 or len(answer) > 120:
        return {"answer": "", "released": False, "reason": "not_a_short_answer"}
    citations = output.get("evidence")
    if not isinstance(citations, list) or not citations:
        return {"answer": "", "released": False, "reason": "missing_source_witness"}
    valid = []
    for citation in citations[:3]:
        if not isinstance(citation, dict):
            continue
        did, quote = citation.get("document_id"), citation.get("quote")
        if did not in documents or not isinstance(quote, str) or len(normalized(quote)) < 8:
            continue
        if source_quote_matches(quote, documents[did]):
            valid.append(did)
    if not valid:
        return {"answer": "", "released": False, "reason": "source_witness_not_found"}
    a = normalized(answer)
    # Entity/number answers must occur in witnessed source text; yes/no still
    # depends on model reasoning and must be evaluated separately against gold.
    if a not in {"yes", "no"} and not any(
        re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", normalized(documents[did]))
        for did in valid
    ):
        return {"answer": "", "released": False, "reason": "answer_not_in_witnessed_source"}
    costs = {did: measured_cost(disclosure_measurement(answer, text, (), 5)) for did, text in documents.items()}
    if any(ledger.get(did, 0.) + cost > budget + 1e-9 for did, cost in costs.items()):
        return {"answer": "", "released": False, "reason": "actual_output_budget_exceeded"}
    for did, cost in costs.items():
        ledger[did] = ledger.get(did, 0.) + cost
    return {"answer": answer.strip(), "released": True, "reason": "source_witness_and_budget_passed",
            "actual_costs": costs}

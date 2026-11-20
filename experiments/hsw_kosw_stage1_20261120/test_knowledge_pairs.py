"""Synthetic rule fixtures only; no research data or model calls."""
import random
from knowledge_pairs import variants


def test_number_and_unit_edits_are_single_site_and_changed():
    source={'text':'The measured cable is 5 m long.', 'anchors':['N:5'], 'subject':'physics'}
    seen=set()
    for i in range(30):
        for row in variants(source,{},random.Random(i),lambda _:()):
            assert row['text'] != source['text']
            if row['type']=='K-unit':
                assert row['validation']['quantity_changed']
                assert '5 ' in row['text']
            seen.add(row['type'])
    assert {'K-unit','K-number'} <= seen


def test_term_replacement_preserves_other_text():
    source={'text':'Entropy remains fixed during this step.', 'anchors':['T:entropy'], 'subject':'physics'}
    rows=variants(source,{'physics':{'entropy':['enthalpy']}},random.Random(0),lambda _:())
    assert any(row['type']=='K-term' and row['text']=='enthalpy remains fixed during this step.' for row in rows)


def test_anchorless_source_produces_no_knowledge_pairs():
    assert variants({'text':'This increases slowly.', 'anchors':[], 'subject':'physics'}, {},random.Random(0),lambda _:())==[]


def test_formula_validation_does_not_call_extra_equals_solver(monkeypatch):
    import sympy as sp
    def forbidden(*args, **kwargs):
        raise AssertionError('Unregistered equals solver invoked')
    monkeypatch.setattr(sp.Expr, 'equals', forbidden)
    source={'text':r'The relationship is \(x y\).',
            'anchors':['F:xy'],'subject':'physics'}
    rows=variants(source,{},random.Random(0),lambda _:())
    assert any(row['type']=='K-formula' for row in rows)

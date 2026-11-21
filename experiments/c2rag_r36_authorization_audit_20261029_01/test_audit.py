"""Software fixtures only; never real teaching evidence or research samples."""
from itertools import combinations

from experiments.c2rag_r36_authorization_audit_20261029_01.common import (
    covering_coalition, qualified,
)


def groups(names, k=3):
    return [g for n in range(1, k + 1) for g in combinations(names, n)]


def test_three_views_cover_but_four_distinct_views_do_not():
    views = {str(i): {i} for i in range(4)}
    assert covering_coalition(views, groups(list(views)[:3])) == ['0', '1', '2']
    assert covering_coalition(views, groups(views)) is None


def test_never_invent_a_coalition_excluded_by_authorization_input():
    views = {'one': {'a'}, 'two': {'b'}, 'trusted': {'a', 'b'}}
    assert covering_coalition(views, [('one',), ('two',)]) is None
    assert covering_coalition(views, [('one',), ('two',), ('one', 'two')]) == ['one', 'two']
    assert covering_coalition(views, []) is None


def test_unknown_or_synthetic_gate_never_qualifies_as_real():
    fields = ['real_teaching_origin', 'source_backed_principals', 'issuer_bound_permissions',
              'specific_restricted_target', 'normal_request_and_correct_candidates',
              'source_backed_answer_availability', 'coalition_authorization_semantics',
              'actual_cross_question_instance_binding']
    record = dict.fromkeys(fields, 'SUPPORTED')
    assert qualified(record)
    for field in fields:
        for value in ['UNKNOWN', 'SYNTHETIC_ONLY', 'NOT_SUPPORTED']:
            assert not qualified({**record, field: value})
    assert not qualified({'role': 'teacher', 'license': 'educational'})

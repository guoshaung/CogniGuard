"""Check the new probability conversion against analytic and exhaustive cases."""
import itertools
import math

from null_model import document_probability, score, sentence_rate, tail_probability


def test_sentence_to_document_probability():
    assert document_probability(.1, 0) == 0
    assert math.isclose(document_probability(.1, 3), .271)
    assert document_probability(1., 4) == 1
    assert document_probability(0., 4) == 0
    assert document_probability(1e-15, 100) > 0


def test_poisson_binomial_matches_exhaustive_enumeration():
    ps = [.01, .2, .3, .7]
    expected = 0.
    for bits in itertools.product([0, 1], repeat=4):
        if sum(bits) >= 2:
            expected += math.prod(p if bit else 1-p for p,bit in zip(ps,bits))
    assert math.isclose(tail_probability(ps, 2), expected, abs_tol=1e-14)


def test_conservative_score_and_distinct_hits():
    rate = sentence_rate(2, 100)
    assert rate['p'] == 3/102
    assert rate['p_upper95'] > rate['p']
    rates = {'a':rate,'b':sentence_rate(3,100)}
    base = score(['a','b'],['a','a'],rates,10)
    conservative = score(['a','b'],['a','a'],rates,10,True)
    assert base['distinct_hits'] == 1
    assert conservative['p_value'] >= base['p_value']
    assert score(['a'],[],rates,0)['p_value'] == 1


def test_same_hits_less_significant_in_longer_text():
    rates = {'a':sentence_rate(2,100),'b':sentence_rate(3,100)}
    short = score(['a','b'],['a','b'],rates,5)
    long = score(['a','b'],['a','b'],rates,50)
    assert short['p_value'] < long['p_value']

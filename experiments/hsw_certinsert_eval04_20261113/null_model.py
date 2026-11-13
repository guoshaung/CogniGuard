"""Per-sentence null to per-document Bernoulli probabilities, shared by both paths."""
import math

from scipy.stats import beta


def sentence_rate(hits: int, sentences: int) -> dict:
    if type(hits) is not int or type(sentences) is not int or not 0 <= hits <= sentences:
        raise ValueError('Require integer 0 <= hits <= eligible sentences')
    upper = 1.0 if hits == sentences else float(beta.ppf(.95, hits+1, sentences-hits))
    return dict(hits=hits, eligible_sentences=sentences,
                p=(hits+1)/(sentences+2), p_upper95=upper,
                smoothing='Beta(1,1) add-one',
                upper_method='one-sided exact Clopper-Pearson on observed counts')


def document_probability(p: float, eligible_sentences: int) -> float:
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('Invalid sentence probability')
    if type(eligible_sentences) is not int or eligible_sentences < 0:
        raise ValueError('Invalid eligible sentence count')
    if eligible_sentences == 0 or p == 0:
        return 0.0
    if p == 1:
        return 1.0
    return -math.expm1(eligible_sentences * math.log1p(-p))


def tail_probability(probabilities: list[float], hit_count: int) -> float:
    if type(hit_count) is not int or not 0 <= hit_count <= len(probabilities):
        raise ValueError('Invalid distinct-word hit count')
    masses = [1.0]
    for p in probabilities:
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('Invalid document probability')
        updated = [0.0] * (len(masses)+1)
        for i, mass in enumerate(masses):
            updated[i] += mass*(1-p)
            updated[i+1] += mass*p
        masses = updated
    return min(1.0, max(0.0, sum(masses[hit_count:])))


def score(selected_words, hit_words, rates, eligible_sentences, conservative=False):
    words = list(dict.fromkeys(selected_words))
    hits = set(hit_words) & set(words)
    field = 'p_upper95' if conservative else 'p'
    probabilities = [document_probability(rates[w][field], eligible_sentences) for w in words]
    return dict(eligible_sentences=eligible_sentences, distinct_hits=len(hits),
                selected_words=words, word_document_probabilities=probabilities,
                p_value=tail_probability(probabilities, len(hits)),
                conservative=conservative)

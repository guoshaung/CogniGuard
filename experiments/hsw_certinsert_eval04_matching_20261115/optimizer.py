"""Exact constrained placements on the fixed additive score table."""
import itertools
import math
import time
from collections import defaultdict

from ortools.sat.python import cp_model


def subsets(edges, natural, needed):
    groups = {e["word"]: e["group"] for e in edges}
    for size in range(1, len(groups)+1):
        for words in itertools.combinations(sorted(groups), size):
            if len({groups[w] for w in words}) == size and len(natural | set(words)) >= needed:
                yield words


def integers(costs):
    ratios = [cost.as_integer_ratio() for cost in costs]
    denominator = max((d for _, d in ratios), default=1)
    values = [p*(denominator//d) for p,d in ratios]
    gcd = math.gcd(*values) or 1
    values = [v//gcd for v in values]
    if sum(abs(v) for v in values) >= 1 << 62:
        raise ValueError("INTEGER_COST_RANGE")
    return values


def assignment(edges, words, ints, budget, deadline, valid):
    indexes = [i for i,e in enumerate(edges) if e["word"] in words]
    model = cp_model.CpModel()
    variables = {i:model.new_bool_var(str(i)) for i in indexes}
    word_indices, sentences = defaultdict(list), defaultdict(list)
    for i in indexes:
        word_indices[edges[i]["word"]].append(i)
        sentences[edges[i]["sentence"]].append(i)
    for w in words:
        model.add_exactly_one(variables[i] for i in word_indices[w])
    for group in sentences.values():
        model.add_at_most_one(variables[i] for i in group)
    line = sorted(indexes,key=lambda i:edges[i]["word_index"])
    for j,i in enumerate(line):
        clique = [i]
        for peer in line[j+1:]:
            if edges[peer]["word_index"]-edges[i]["word_index"] >= 8:
                break
            clique.append(peer)
        if len(clique)>1:
            model.add_at_most_one(variables[k] for k in clique)
    model.add(sum(edges[i]["word_cost"]*variables[i] for i in indexes)<=budget)
    model.minimize(sum(ints[i]*variables[i] for i in indexes))
    while True:
        remaining = deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining
        solver.parameters.num_search_workers = 1
        solver.parameters.absolute_gap_limit = 0
        solver.parameters.relative_gap_limit = 0
        status = solver.solve(model)
        if status==cp_model.INFEASIBLE:
            return None
        if status==cp_model.MODEL_INVALID:
            raise ValueError("CP_SAT_MODEL_INVALID")
        if status!=cp_model.OPTIMAL:
            raise TimeoutError
        chosen = [i for i in indexes if solver.value(variables[i])]
        if valid([edges[i] for i in chosen]):
            return chosen
        model.add(sum(variables[i] for i in chosen)<=len(chosen)-1)


def solve(edges, natural, needed, budget, valid, seconds=60, existence=False):
    deadline = time.monotonic()+seconds
    if len(natural)>=needed:
        return []
    ints = integers([e.get("cost",0.0) for e in edges])
    winner = None
    for words in subsets(edges,natural,needed):
        chosen = assignment(edges,words,ints,budget,deadline,valid)
        if chosen is None:
            continue
        if existence:
            return [edges[i] for i in chosen]
        cost = sum(ints[i] for i in chosen)
        key = (cost,len(words),words)
        if winner is None or key<winner[0]:
            winner = (key,[edges[i] for i in chosen])
    return winner[1] if winner else None


def quality(edges):
    if edges is None:
        return None
    return math.fsum(e["cost"] for e in edges),len(edges),tuple(sorted(e["word"] for e in edges))


def brute(edges,natural,needed,budget,valid):
    """Independent Cartesian enumeration of all disjoint legal placements."""
    by_word = defaultdict(list)
    for edge in edges:
        by_word[edge["word"]].append(edge)
    if len(natural)>=needed:
        return []
    best = None
    for selected in itertools.product(*([None]+by_word[w] for w in sorted(by_word))):
        chosen = [edge for edge in selected if edge is not None]
        loc = sorted(edge["word_index"] for edge in chosen)
        if any(b-a<8 for a,b in zip(loc,loc[1:])):
            continue
        if len({e["group"] for e in chosen})!=len(chosen) or len({e["sentence"] for e in chosen})!=len(chosen):
            continue
        if sum(e["word_cost"] for e in chosen)>budget or len(natural|{e["word"] for e in chosen})<needed:
            continue
        score = quality(chosen)
        if (best is None or score<best[0]) and valid(chosen):
            best=(score,chosen)
    return best[1] if best else None


def selftest():
    def e(word, i, cost, size=1, group=None):
        return dict(word=word,word_index=i,sentence=i,word_cost=size,group=group or word,cost=float(cost))

    fixtures = [
        ([e("a",0,0),e("a",20,3),e("b",0,1)],set(),2,2,(4,2,("a","b"))),
        ([e("a",0,0),e("b",7,0)],set(),2,2,None),
        ([e("a",0,-2,2),e("b",10,0,2)],set(),2,3,None),
        ([e("a",0,2),e("b",10,2),e("c",20,3)],{"z"},2,2,(2,1,("a",))),
        ([e("a",0,0,group="g"),e("b",10,0,group="g"),e("c",20,-3)],set(),2,2,(-3,2,("a","c"))),
    ]
    for edges,natural,needed,budget,want in fixtures:
        assert quality(solve(edges,natural,needed,budget,lambda _:True))==want
        assert quality(brute(edges,natural,needed,budget,lambda _:True))==want
    return len(fixtures)

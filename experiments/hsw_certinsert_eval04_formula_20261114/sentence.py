"""EVAL-03 sentence insertion adapter with the CPU scoring backend."""

import argparse
import json
from collections import Counter

from shared import FREQ, OUT, VOCAB, sources, verify
from score_cpu import CPUScore
from prepare_cpu import build_plan, make_detector, word_count
from e1_v4r8_capacity import capacity
from e1_v4r8_selector import selector
from e1_v4r7f_prepare import allowed
from e1_v4r7f_anchors import anchors, forms, numbers
from e1_v4r3_core import exact, pb_tail
from e1_long_context_run import context_pair
from e1_register_core import assemble
from structure_adapter import allowed_offset, split
from shared import read, write


class SentenceDetector:
    def __init__(self):
        self.vocab = read(VOCAB)
        self.by_word = {row["text"]:row for row in self.vocab}
        self.frequencies = read(FREQ)["probabilities"]
        self.det, self.key = make_detector(self.vocab)
        self.select = selector(self.det,self.key,4,self.vocab)

    def p(self,text, selected=None):
        items = self.select(text) if selected is None else selected
        return pb_tail([self.frequencies[w] for w in items],sum(exact(text,w) for w in items))


def plan(source, detector):
    text = source["text"]
    structure = split(text,source.get("question",""))
    body = "".join(text[a:z] for a,z in structure["body_intervals"])
    p = build_plan(dict(source,explanation_words=word_count(body)),"R","A4",detector.select)
    p["candidates"] = [s for s in p["candidates"] if allowed_offset(structure,s["offset"])]
    first = next((a+i for a,z in structure["body_intervals"]
                  for i,c in enumerate(text[a:z]) if c.isascii() and c.isalpha()),-1)
    for s in p["candidates"]:
        s["explanation_first"] = s["offset"] == first
    return p


def restore(text, spans, changes):
    for s in reversed(spans):
        assert text[s["start"]:s["end"]] == s["inserted"]
        text = text[:s["start"]]+text[s["end"]:]
    pieces = list(text)
    for c in changes:
        assert pieces[c["offset"]] == c["after"]
        pieces[c["offset"]] = c["before"]
    return "".join(pieces)


def embed(p, det, scorer):
    text = p["text"]
    bound = capacity(p, list(det.by_word.values()),det.frequencies)
    chosen = []
    distinct = set(bound["natural_hits"])
    target = lambda: pb_tail([det.frequencies[w] for w in p["selected"]],
                              len(distinct | {r["word"] for r in chosen}))
    status = bound["status"]
    before = scorer.tokens
    while status == "ELIGIBLE" and target() >= .001:
        remaining = p["budget"]-sum(r["word_cost"] for r in chosen)
        groups = {r["group"] for r in chosen}
        rows = []
        for site in p["candidates"]:
            if any(abs(site["word_index"]-c["word_index"])<8 or site["sentence"]==c["sentence"]
                   for c in chosen):
                continue
            for word in p["selected"]:
                spec = det.by_word[word]
                if spec["group"] in groups or spec["word_cost"]>remaining or not allowed(site,spec):
                    continue
                candidate = dict(site,word=word,word_cost=spec["word_cost"],group=spec["group"],
                                 inserted=word.capitalize()+", ",case_adjust=site["offset"] in p["case_eligibility"])
                old,new,_ = context_pair(p,chosen,candidate)
                a,b = scorer.get(old),scorer.get(new)
                if a is None or b is None:
                    status = "CONTEXT_LIMIT"
                    break
                rows.append((a-b,candidate["offset"],word,candidate))
            if status != "ELIGIBLE":
                break
        if status!="ELIGIBLE":
            break
        if not rows:
            status = "UNWATERMARKABLE_GREEDY_EXHAUSTED"
            break
        chosen.append(min(rows,key=lambda x:x[:3])[3])
    rendered,spans,changes,_ = assemble(p,chosen)
    assert restore(rendered,spans,changes).encode()==text.encode()
    selected = det.select(rendered)
    invariant = anchors(rendered)==tuple(p["anchors"]) and selected==p["selected"]
    intact = set(numbers(text))<=set(numbers(rendered)) and set(forms(text))<=set(forms(rendered))
    predicted = target()
    if status=="ELIGIBLE":
        status = "PREDICTED_TARGET_REACHED"
    success = status=="PREDICTED_TARGET_REACHED" and invariant and intact
    if status=="PREDICTED_TARGET_REACHED" and not success:
        status = "FAIL_INVARIANCE"
    return dict(status=status,success=success,words=p["explanation_words"],p=det.p(rendered,selected),
                min_predicted=bound["predicted_min_p"],predicted_p=predicted,insertions=len(chosen),
                certificate=True,anchor_and_selection_invariant=invariant,original_numeric_intact=intact,
                scoring_tokens=scorer.tokens-before,spans=spans,case_changes=changes,trial=rendered)


def main():
    verify()
    generated,_ = sources()
    detector = SentenceDetector()
    scorer=CPUScore(OUT/"sentence_native.log")
    status=Counter()
    try:
        with (OUT/"sentence.local.jsonl").open("x",encoding="utf-8",newline="\n") as f:
            for i,source in enumerate(generated,1):
                row=embed(plan(source,detector),detector,scorer)
                row.update(id=source["id"],subject=source["subject"])
                f.write(json.dumps(row,ensure_ascii=False)+"\n")
                f.flush()
                status[row["status"]]+=1
                if i%10==0: print("sentence",i,len(generated),scorer.tokens,dict(status),flush=True)
    finally:
        scorer.close()
    write(OUT/"sentence_run.json",{"statuses":dict(status),"forward_tokens":scorer.tokens,"score_calls":scorer.calls})


if __name__=="__main__":
    main()

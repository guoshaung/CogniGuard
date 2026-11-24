"""Gate W0: does an ideal issuance watermark add security value over content fingerprints?

Control layer: the Gate 0-2 world (coalition propagation, k=2, B3 evidence rule) where
each unrecorded transfer leaves an observed text; evidence methods recover units from it.
Attribution layer: Eedi unit texts in scenarios S1-S4. Texts live only in memory.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter
from pathlib import Path

from cogniguard.governance.reconstruction import check_release
from experiments.capd_gate012_20261124.sim import K_DEFENSE, make_world, _frozen

TEMPLATES = ("Item property {f} is {v}.", "The item has value {v} for feature {f}.",
             "For feature {f}, choose value {v}.")
PARA = (("In item set", "Within set"), ("Item property", "Attribute"), (" is ", " equals "),
        ("The item has value", "The item takes"), ("for feature", "on attribute"),
        ("For feature", "On attribute"), ("choose value", "pick"),
        ("A common wrong idea here is", "One frequent mistake is"), ("The trap is", "Watch for"),
        ("Practise this skill", "Work on"), ("Watch out", "Be careful"))
OPENERS = ("Note:", "Reminder:", "Tip:", "Remember:", "Key point:")
CONTROL_METHODS = ("none", "F1_sha", "F2_minhash", "F3_bm25", "A1_minhash", "A1_bm25",
                   "Cstar", "Wstar", "F3_plus_Wstar", "Oracle")
NOT_RUN = ("F4_bge", "F5_bge_rerank")
MIN_WORDS = 4


def _h(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def transform(sentence: str, kind: str) -> str:
    if kind == "paraphrase":
        for a, b in PARA:
            sentence = sentence.replace(a, b)
        return sentence
    if kind == "fragment":
        return " ".join(sentence.split()[-5:])
    return sentence


# ---------------------------------------------------------------- retrieval

def _shingles(text, n=5):
    t = re.sub(r"\s+", " ", text.lower())
    return {t[i:i + n] for i in range(max(1, len(t) - n + 1))}


_PERMS = [(random.Random(i).randrange(1, 2**31 - 1), random.Random(1000 + i).randrange(0, 2**31 - 1))
          for i in range(64)]


def minhash(text):
    hs = [_h(s) for s in _shingles(text)]
    return tuple(min((a * x + b) % 2147483647 for x in hs) for a, b in _PERMS)


def _tok(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class Index:
    """Server-side index over issued texts: text -> set of (unit, issuance_id)."""

    def __init__(self):
        self.docs: dict[str, set] = {}
        self._sig: dict[str, tuple] = {}

    def add(self, text, unit, issuance):
        self.docs.setdefault(text, set()).add((unit, issuance))
        if text not in self._sig:
            self._sig[text] = minhash(text)

    def sha(self, q):
        return self.docs.get(q, set())

    def minhash(self, q, threshold=0.5):
        sq = minhash(q)
        scores = {t: sum(a == b for a, b in zip(sq, s)) / 64 for t, s in self._sig.items()}
        if not scores:
            return set()
        best = max(scores.values())
        if best < threshold:
            return set()
        return set().union(*(self.docs[t] for t, s in scores.items() if s == best))

    def bm25(self, q, ratio=0.5, k1=1.5, b=0.75):
        texts = list(self.docs)
        if not texts:
            return set()
        toks = {t: _tok(t) for t in texts}
        avg = sum(len(v) for v in toks.values()) / len(toks)
        df = Counter(w for v in toks.values() for w in set(v))
        n = len(texts)

        def score(query_tokens, doc):
            tf = Counter(toks[doc])
            s = 0.0
            for w in query_tokens:
                if w in tf:
                    idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                    s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(toks[doc]) / avg))
            return s

        qt = _tok(q)
        scores = {t: score(qt, t) for t in texts}
        best = max(scores.values())
        if best <= 0:
            return set()
        top = [t for t, s in scores.items() if abs(s - best) < 1e-9]
        if best / max(score(toks[top[0]], top[0]), 1e-9) < ratio:
            return set()
        return set().union(*(self.docs[t] for t in top))


# ---------------------------------------------------------------- control layer

def _issued_text(unit, predicate, recipient, active):
    tid = unit[0]
    if active:
        tmpl = TEMPLATES[_h(recipient) % 3]
    else:
        tmpl = TEMPLATES[_h(str(unit)) % 3]
    return f"In item set {tid}: " + tmpl.format(f=predicate["feature"], v=predicate["value"])


def run_control(secrets, predicates, *, seed, method, kind, f=8):
    world = make_world(secrets, seed=seed, graph="sparse", f=f, f_true=f, mode="coalition")
    k = K_DEFENSE
    active = method.startswith("A1")
    truth = {a: {} for a in world.agents}    # unit -> (text, issuance)
    belief = {a: set() for a in world.agents}
    index = Index()
    issuance = 0
    m = Counter()
    prec_hit = prec_tot = rec_hit = rec_tot = 0
    for t, req in enumerate(world.stream.requests):
        for sender, receiver in world.events.get(t, []):
            content = dict(truth[sender])
            truth[receiver].update(content)
            if method in ("none", "Oracle") or not content:
                continue
            recovered = set()
            for unit, (text, iss) in content.items():
                obs = transform(text, kind)
                ideal_ok = len(obs.split()) >= MIN_WORDS
                if method == "F1_sha":
                    got = {u for u, _ in index.sha(obs)}
                elif method in ("F2_minhash", "A1_minhash"):
                    got = {u for u, _ in index.minhash(obs)}
                elif method in ("F3_bm25", "A1_bm25"):
                    got = {u for u, _ in index.bm25(obs)}
                elif method in ("Cstar", "Wstar"):
                    got = {unit} if ideal_ok else set()
                elif method == "F3_plus_Wstar":
                    got = {u for u, _ in index.bm25(obs)} | ({unit} if ideal_ok else set())
                else:
                    raise ValueError(method)
                recovered |= got
            true_units = set(content)
            prec_hit += len(recovered & true_units)
            prec_tot += len(recovered)
            rec_hit += len(recovered & true_units)
            rec_tot += len(true_units)
            belief[receiver] |= recovered
        recipient, unit = req.recipient_id, req.unit
        truth_units = {a: set(v) for a, v in truth.items()}
        oracle_ok = check_release(world.registry, recipient, {unit}, _frozen(truth_units), k).safe
        if method == "Oracle":
            ok = oracle_ok
        else:
            ok = check_release(world.registry, recipient, {unit}, _frozen(belief), k).safe
        if ok:
            issuance += 1
            text = _issued_text(unit, predicates[unit], recipient, active)
            truth[recipient][unit] = (text, issuance)
            belief[recipient].add(unit)
            index.add(text, unit, issuance)
            m["harmful"] += not oracle_ok
        if req.role == "normal":
            m["n"] += 1
            m["full"] += ok
            m["util"] += 1.0 if ok else 0.4
            m["unneeded"] += (not ok) and oracle_ok
    n = m["n"] or 1
    return {"harmful_releases": m["harmful"], "UR_normal": m["util"] / n,
            "unneeded_refusal_rate": m["unneeded"] / n,
            "unit_precision": prec_hit / prec_tot if prec_tot else None,
            "unit_recall": rec_hit / rec_tot if rec_tot else None}


def load_predicates(root: Path) -> dict:
    out = {}
    with (root / "units.jsonl").open() as handle:
        for line in handle:
            r = json.loads(line)
            out[(r["target_id"], r["unit_id"])] = r["predicate"]
    return out


# ---------------------------------------------------------------- attribution layer (Eedi)

def run_attribution(eedi_root: Path, seed=2026):
    rng = random.Random(seed)
    units = [json.loads(l) for l in (eedi_root / "texts.jsonl").open() if '"role":"unit"' in l
             or '"role": "unit"' in l]
    units = [u for u in units if u["role"] == "unit"]
    by_text = {}
    for u in units:
        by_text.setdefault(u["text"], u)
    pool = list(by_text.values())
    rng.shuffle(pool)
    s1 = pool[:200]
    s2 = pool[200:260]
    by_tmpl = {}
    for u in pool[260:]:
        by_tmpl.setdefault(u["template_id"], []).append(u)
    s3 = []
    for group in by_tmpl.values():
        for i in range(0, len(group) - 1, 2):
            s3 += group[i:i + 2]
    s3 = s3[:200]
    recipients = [f"r{i}" for i in range(60)]
    scenarios = {
        "S1": [(u, rng.choice(recipients)) for u in s1],
        "S2": [(u, r) for u in s2 for r in rng.sample(recipients, 3)],
        "S3": [(u, rng.choice(recipients)) for u in s3],
    }
    rows = []
    for scen, issued in list(scenarios.items()) + [("S4", scenarios["S1"])]:
        for kind in ("identity", "paraphrase", "fragment"):
            for method in ("F1_sha", "F2_minhash", "F3_bm25", "A1_bm25", "Cstar", "Wstar"):
                rows.append(_attr_one(scen, issued, kind, method, rng))
    for method in NOT_RUN:
        rows.append({"scenario": "*", "transform": "*", "method": method, "status": "NOT_RUN"})
    return rows


def _attr_one(scen, issued, kind, method, rng):
    active = method.startswith("A1")
    index = Index()
    docs = []
    for iid, (u, r) in enumerate(issued):
        text = (OPENERS[_h(r) % len(OPENERS)] + " " + u["text"]) if active else u["text"]
        unit = (u["target_id"], tuple(u["gold_units"]))
        index.add(text, unit, iid)
        docs.append((text, unit, iid))
    content_of = {}
    for text, unit, iid in docs:
        content_of.setdefault(unit, set()).add(iid)
    qrng = random.Random(f"{scen}/{kind}/{method}")
    if scen == "S4":
        queries = []
        for _ in range(100):
            a, b = qrng.sample(docs, 2)
            queries.append(([a, b], [transform(a[0], "fragment"), transform(b[0], "fragment")]))
    else:
        queries = [([d], [transform(d[0], kind)]) for d in docs]
    st = Counter()
    for truth_docs, observed in queries:
        got = set()
        for (text, unit, iid), obs in zip(truth_docs, observed):
            ok = len(obs.split()) >= MIN_WORDS
            if method == "F1_sha":
                got |= index.sha(obs)
            elif method == "F2_minhash":
                got |= index.minhash(obs)
            elif method in ("F3_bm25", "A1_bm25"):
                got |= index.bm25(obs)
            elif method == "Cstar":
                got |= {(unit, i) for i in content_of[unit]} if ok else set()
            elif method == "Wstar":
                got |= {(unit, iid)} if ok else set()
        true_iss = {iid for _, _, iid in truth_docs}
        true_units = {u for _, u, _ in truth_docs}
        got_iss = {i for _, i in got}
        got_units = {u for u, _ in got}
        st["iss_hit"] += len(got_iss & true_iss)
        st["iss_got"] += len(got_iss)
        st["iss_true"] += len(true_iss)
        st["unit_hit"] += len(got_units & true_units)
        st["unit_got"] += len(got_units)
        st["unit_true"] += len(true_units)
        st["resolved"] += (got_iss == true_iss)
        st["q"] += 1
    return {"scenario": scen, "transform": kind if scen != "S4" else "fragment", "method": method,
            "status": "RUN", "issuance_precision": st["iss_hit"] / st["iss_got"] if st["iss_got"] else 0.0,
            "issuance_recall": st["iss_hit"] / st["iss_true"],
            "unit_precision": st["unit_hit"] / st["unit_got"] if st["unit_got"] else 0.0,
            "unit_recall": st["unit_hit"] / st["unit_true"],
            "ambiguity_resolved_rate": st["resolved"] / st["q"]}

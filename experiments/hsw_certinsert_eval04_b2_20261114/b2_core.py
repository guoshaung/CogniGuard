"""Reuse the frozen text, anchor, scoring-window and certificate components."""
import hashlib
import hmac
import json
import re
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from scipy.stats import hypergeom

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIMARY = ROOT.parent.parent / "CogniGuard"
STAGE = ROOT / "var/results/hsw-st/certinsert_eval04_20261113/stage0"
OUT = ROOT / "var/results/hsw-st/certinsert_eval04_b2_20261114"
SCORER_RUNTIME = ROOT / "var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime"
FREEZE = HERE / "B2_FREEZE.json"
FRAMES = ("here", "in this case")
FRAME = re.compile(r"^(here|in\s+this\s+case),[ \t]+", re.IGNORECASE)
PREFIX = re.compile(r"^\s*([A-Za-z]+(?:['’-][A-Za-z]+)*(?:\s+[A-Za-z]+(?:['’-][A-Za-z]+)*){0,3})\s*,")
FORMULA = re.compile(r"\\\(.*?\\\)", re.DOTALL)
GAMMAS = (10, 20, 30)
BUDGETS = (3, 4, 5)

for name in ("hsw_english_replication_20261110_01", "hsw_certinsert_eval_20261111_02"):
    sys.path.insert(0, str(ROOT / "experiments" / name))
from capacity_shared_v32 import nlp
from e1_long_context_run import GPUScorer, context_pair
from e1_register_core import assemble
from e1_v4r7f_anchors import anchors
from structure_adapter import split


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(name, obj):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def frame_at(text):
    match = FRAME.match(text)
    return " ".join(match[1].lower().split()) if match else None


def body_split(text, question):
    layout = split(text, question)
    body = "".join(text[a:b] for a, b in layout["body_intervals"])
    return layout, body


def masked(text):
    return FORMULA.sub(lambda m: " " * len(m[0]), text)


def sections(text, layout, doc):
    intervals = layout["body_intervals"]
    words = [t for t in doc if t.is_alpha]
    indices = {t.idx: i for i, t in enumerate(words)}
    sentences = []
    for sentence in doc.sents:
        first = next((t.idx for t in sentence if t.is_alpha), None)
        start, end = sentence.start_char, sentence.end_char
        visible = text[start:end].lstrip()
        prefix = start + len(text[start:end]) - len(visible)
        # The visible prefix may include a structural bullet. Insertion, matching,
        # and removal all use the first alphabetic token in the sentence.
        if first is not None:
            prefix = first
        in_body = any(a <= prefix < b for a, b in intervals)
        sentences.append({"start": start, "end": end, "offset": first,
                          "word_index": indices.get(first), "body": in_body})
    return sentences


def plan(text, question, connectives, parsed=None):
    layout, body = body_split(text, question)
    doc = parsed if parsed is not None else nlp(masked(text))
    sentences = sections(text, layout, doc)
    slots = []
    for index, item in enumerate(sentences):
        if not index or not item["body"] or item["offset"] is None:
            continue
        prior = sentences[index - 1]
        if not prior["body"] or prior["offset"] is None:
            continue
        prior_text = text[prior["start"]:prior["end"]]
        prior_offset = prior["offset"] - prior["start"]
        before, visible_prior = prior_text[:prior_offset], prior_text[prior_offset:]
        facts = anchors(before + FRAME.sub("", visible_prior, count=1))
        if not facts:
            continue
        snippet = text[item["offset"]:item["end"]]
        remainder = FRAME.sub("", snippet, count=1)
        match = PREFIX.match(remainder)
        if match and " ".join(match[1].casefold().split()) in connectives:
            continue
        signature = json.dumps(sorted(facts), ensure_ascii=False, separators=(",", ":"))
        slots.append({"offset": item["offset"], "word_index": item["word_index"],
                      "sentence": index, "signature": signature, "frame": frame_at(snippet)})
    return {"text": text, "question": question, "sentences": sentences, "slots": slots, "body": body}


def units(slots):
    groups = defaultdict(list)
    for slot in slots:
        groups[slot["signature"]].append(slot)
    return groups


@lru_cache(maxsize=100_000)
def pvalue(s, m, n, x):
    if not n or not m or not x:
        return 1.0
    return float(hypergeom.sf(x - 1, s, m, n))


def selftest():
    for args, expected in [((5, 2, 2, 2), 1/10), ((4, 2, 2, 1), 5/6), ((6, 3, 3, 3), 1/20)]:
        assert abs(pvalue(*args) - expected) < 1e-12
    assert pvalue(9, 0, 3, 0) == 1 and pvalue(9, 3, 0, 0) == 1


def mark_int(key, signature):
    return int.from_bytes(hmac.digest(key, signature.encode(), "sha256"), "big")


def is_marked(value, gamma):
    return value * 100 < gamma * (1 << 256)


def detect(p, key, gamma):
    groups = units(p["slots"])
    marks = {sig for sig in groups if is_marked(mark_int(key, sig), gamma)}
    hits = {sig for sig, group in groups.items() if any(s["frame"] for s in group)}
    s, m, n, x = len(groups), len(marks), len(hits), len(marks & hits)
    return {"S": s, "M": m, "N": n, "X": x, "p": pvalue(s, m, n, x)}


def candidate(p, slot, entry):
    loc = slot["offset"]
    return dict(slot, word=entry, inserted=entry.capitalize()+", ",
                case_adjust=p["text"][loc].lower() != p["text"][loc])


def insert_plain(p, chosen):
    text = p["text"]
    for item in sorted(chosen, key=lambda row: row["offset"], reverse=True):
        off = item["offset"]
        text = text[:off] + item["inserted"] + text[off].lower() + text[off+1:]
    return text


def compatible_insert(p, item):
    off = item["offset"]
    return not item["frame"] and len(p["text"][off].lower()) == 1


def count_frame(text, entry):
    pattern = r"(?<![\w’'-])" + r"\s+".join(entry.split()) + r"\s*,"
    return len(re.findall(pattern, text, re.IGNORECASE))


def crop(text, n, position):
    words = list(re.finditer(r"\S+", text))
    if len(words) <= n:
        return text
    start = {"first": 0, "middle": (len(words)-n)//2, "last": len(words)-n}[position]
    return text[words[start].start():words[start+n-1].end()]

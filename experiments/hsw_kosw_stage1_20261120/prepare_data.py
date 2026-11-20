"""Stage 2 preparation only: read R and import frozen EVAL03 components."""
import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CORPUS = ROOT / 'var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json'
OUT = ROOT / 'var/results/hsw-st/kosw_stage1_20261120'
SEED = 2026112001


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'SENTENCES.json').exists():
        raise FileExistsError('Preserve existing preparation')
    sys.path.insert(0, str(ROOT / 'experiments/hsw_english_replication_20261110_01'))
    from capacity_shared_v32 import nlp
    from e1_v4r7f_anchors import anchors
    sys.path.insert(0, str(ROOT / 'experiments/hsw_certinsert_eval_20261111_02'))
    from structure_adapter import allowed_offset, split

    corpus = json.loads(CORPUS.read_bytes())
    build = sorted([r for r in corpus if r['split'] == 'build'], key=lambda r:
        hashlib.sha256(('KOSW-K1|document|' + r['id']).encode()).hexdigest())
    boundary = math.floor(.7 * len(build))
    document_split = {r['id']: ('train' if i < boundary else 'heldout')
                      for i, r in enumerate(build)}
    pools = {'train': [], 'heldout': []}
    for row, doc in zip(build, nlp.pipe((r['text'] for r in build), batch_size=16)):
        structure = split(row['text'], row.get('question', ''))
        for index, sentence in enumerate(doc.sents):
            text = sentence.text.strip()
            start = sentence.start_char + len(sentence.text) - len(sentence.text.lstrip())
            words = len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", text))
            if not 8 <= words <= 60 or not allowed_offset(structure, start):
                continue
            # Entire sentence must be inside explanation spans, not just its start.
            if any(s['role'] != 'BODY' and s['start'] < sentence.end_char
                   and s['end'] > start for s in structure['spans']):
                continue
            pools[document_split[row['id']]].append(dict(
                id=hashlib.sha256((row['id'] + '|sentence|' + str(index)).encode()).hexdigest(),
                document_id=row['id'],subject=row['subject'],text=text,
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),anchors=list(anchors(text))))
    counts = {s: len(v) for s, v in pools.items()}
    targets = {'train':3000,'heldout':1000}
    shortage = {s:counts[s] for s in targets if counts[s] < targets[s]}
    manifest = dict(seed=SEED,corpus_sha256=sha(CORPUS),document_split=document_split,
                    available_sentences=counts,requested=targets,shortage=shortage,
                    status='INSUFFICIENT_SENTENCES' if shortage else 'PREPARED_NO_PAIR_COMPUTATION',
                    imports={name:sha(ROOT / 'experiments' / path) for name,path in {
                        'sentence_splitter':'hsw_english_replication_20261110_01/capacity_shared_v32.py',
                        'anchors':'hsw_english_replication_20261110_01/e1_v4r7f_anchors.py',
                        'structure':'hsw_certinsert_eval_20261111_02/structure_adapter.py'}.items()})
    (OUT/'DATA_PREPARATION.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    if shortage:
        print(json.dumps(manifest['available_sentences']))
        raise RuntimeError('Required sentence counts unavailable; stop')
    selected={s:random.Random(SEED+i).sample(pools[s],targets[s])
              for i,s in enumerate(['train','heldout'])}
    (OUT/'SENTENCES.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'available':counts,'selected':targets,'document_train':boundary,
                      'document_heldout':len(build)-boundary}))


if __name__ == '__main__':
    main()

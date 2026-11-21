"""Paths and immutable evidence I/O for one isolated offline diagnostic."""
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import hashlib
import json
from core.paths import PROJECT_ROOT, RESULTS_DIR

NAME='c2rag_cross_question_history_20261027_01'
OUT=RESULTS_DIR/NAME
OLD=RESULTS_DIR/'c2rag_real_source_structure_20261027_01'
SOURCE=PROJECT_ROOT/'experiments'/NAME
PIN='6b60c733a8d7a751734521d4c93d23fb58410dad'


def sha(data):return hashlib.sha256(data).hexdigest()


def read(name):return json.loads((OUT/name).read_text(encoding='utf8'))


def write(name,value):
    f=OUT/name;f.parent.mkdir(parents=True,exist_ok=True)
    with f.open('x',encoding='utf8',newline='') as stream:
        if isinstance(value,str):stream.write(value)
        else:json.dump(value,stream,ensure_ascii=False,indent=2)


def module(name):
    spec=spec_from_file_location('cross_frozen_'+name,OUT/'snapshot'/f'{name}.py')
    obj=module_from_spec(spec);spec.loader.exec_module(obj);return obj


def verify_freeze():
    for path,h in read('freeze.json')['sha256'].items():
        assert sha((PROJECT_ROOT/path).read_bytes())==h,path


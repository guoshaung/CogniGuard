"""Enumeration/permission regression tests, independent of outcome selection."""
import importlib.util
from pathlib import Path

from experiments.c2rag_real_source_structure_20261027_01.analyze import legal_selections, views_of
from core.paths import PROJECT_ROOT


def test_one_answer_and_persistent_recipient_views():
    task={'requests':[{'request_id':'q1'},{'request_id':'q2'}],
          'actions':[{'request_id':'q1','recipient':0,'reveals':['x']},
                     {'request_id':'q1','recipient':0,'reveals':['y']},
                     {'request_id':'q2','recipient':0,'reveals':['z']}]}
    rows=list(legal_selections(task))
    assert len(rows)==6
    assert all(not {'x','y'}<=views_of(r)[0] for r in rows)
    assert any(views_of(r)[0]=={'x','z'} for r in rows)


def test_k3_excludes_four_person_only_and_authorization_is_coalition_exact():
    root=PROJECT_ROOT/'experiments/results/_root_workspaces_20261023/c2rag-support-optimization-20261022/baseline'
    spec=importlib.util.spec_from_file_location('audit_reference',root/'reference.py')
    ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    c={'n':4,'public':[],'facts':['a','b','c','d','T'],
       'rules':[[['a','b','c','d'],'T']],'assets':[{'target':'T','authorized':[]}]}
    views=[{'a'},{'b'},{'c'},{'d'}]
    assert not ref.unsafe(c,views)
    assert 'T' in ref.closure(set.union(*views),c['rules'])
    c['rules']=[[['a','b','c'],'T']]
    assert ref.unsafe(c,views)
    c['assets'][0]['authorized']=[7]
    assert not ref.unsafe(c,views)
    c['assets'][0]['authorized']=[1,2,4]
    assert ref.unsafe(c,views)

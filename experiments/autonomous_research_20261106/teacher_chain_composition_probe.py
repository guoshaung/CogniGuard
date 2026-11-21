"""Authentic teacher handoffs vs tiny exact joint-inference oracle."""
import hashlib
import itertools
import json
import os
import socket
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ['COGNIGUARD_LANGSMITH_ENABLED'] = '0'
os.environ['LANGSMITH_TRACING'] = 'false'
def reject_network(*args, **kwargs):
    raise RuntimeError('network prohibited in synthetic handoff probe')
socket.socket.connect = reject_network
socket.socket.connect_ex = reject_network
socket.create_connection = reject_network

from cogniguard.workflows.teachers.catalog import TeacherEdge, TeacherNode, TeamSpec
from cogniguard.workflows.teachers.chain import TrustChain

nodes = tuple(TeacherNode(n, 'synthetic') for n in ('a', 'b', 'sink'))
edges = (TeacherEdge('a', 'sink'), TeacherEdge('b', 'sink'))
team = TeamSpec('synthetic', nodes, edges, 'sink')
worlds = list(itertools.product((0, 1), repeat=2))
def secrets_possible(visible):
    return {x ^ y for x, y in worlds if all((x, y)[i] == value for i, value in visible.items())}

out = {'synthetic_only': True, 'worlds': len(worlds), 'chain_accepted': 0,
       'single_handoff_secret_values': [], 'joint_handoff_secret_values': [],
       'oracle_accepted': 0, 'deny_all_accepted': 0, 'chain_invalid': 0}
for x, y in worlds:
    chain = TrustChain('synthetic', team, mode='enforce')
    values = (x, y)
    visible = {}
    censor_visible = {}
    for i, (name, edge) in enumerate(zip(('X', 'Y'), edges)):
        message = chain.issue(edge.source, 'synthetic-prompt', f'{name}={values[i]}',
                              data_labels=('controlled_resource',))
        view, record = chain.admit(message, edge, expected_prompt_hash='synthetic-prompt')
        if view is not None and record['accepted']:
            assert view.text == f'{name}={values[i]}'
            out['chain_accepted'] += 1
            visible[i] = values[i]
        else:
            out['chain_invalid'] += 1
        prospective = {**censor_visible, i: values[i]}
        if len(secrets_possible(prospective)) > 1:
            censor_visible = prospective
            out['oracle_accepted'] += 1
        if i == 0:
            out['single_handoff_secret_values'].append(len(secrets_possible(visible)))
    out['joint_handoff_secret_values'].append(len(secrets_possible(visible)))
paths = ['cogniguard/workflows/teachers/chain.py', 'cogniguard/workflows/teachers/catalog.py']
out['source_sha256'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
assert out['chain_invalid'] == 0
assert all(x == 2 for x in out['single_handoff_secret_values'])
assert all(x == 1 for x in out['joint_handoff_secret_values'])
print(json.dumps(out, indent=2))

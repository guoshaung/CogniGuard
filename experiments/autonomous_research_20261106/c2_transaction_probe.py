"""Real local graph/session accounting, synthetic input, no HSW or network."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ['COGNIGUARD_LANGSMITH_ENABLED'] = '0'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
def forbid_network(*args, **kwargs):
    raise RuntimeError('network prohibited')
socket.socket.connect = forbid_network
socket.socket.connect_ex = forbid_network
socket.create_connection = forbid_network

from cogniguard.governance import CapabilityGrant, CapabilityPolicy, LifecycleGuard
from cogniguard.runtime.protection_context import ProtectionContext, protection_scope
from cogniguard.runtime.sessions import RequestConflict, SessionStore
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline
from core.access import AccessScope
from protection.common.schemas import ProfileRecord, ResourcePolicy, StudentProfile, TeacherResource

class NoExport:
    def export(self, recorder):
        pass

def fail_generator(_):
    raise RuntimeError('synthetic generator failure')

temp_root = root / 'experiments/autonomous_research_20261106/temp'
folder = Path(tempfile.mkdtemp(prefix='tx-probe-', dir=temp_root))
cfg = {'fopd': {'use_enhanced_fopd': True, 'privacy_budget': 1.0}}
profile = StudentProfile('fictional', profile_records=[
    ProfileRecord('fictional', 'mastery', 'algebra', 0.55, 1.0, 0.3, '2026-01-01')])
question = {'request_id': 'fictional', 'student_id': 'fictional', 'question': 'alpha beta gamma algebra',
            'expected_knowledge': 'algebra', 'need_resource': True}
def new_store(name):
    return SessionStore(folder / (name + '.sqlite3'), limits={'requests': 20, 'privacy': 10, 'copyright': 10})
def new_runner(scenario):
    policy = ResourcePolicy(allow_quote=True, allow_summary=False, allow_outline=False,
                            allow_variant=False, max_quote_len=20, max_exposure=0.2)
    resource = TeacherResource('synthetic', 'synthetic', 'alpha beta gamma', 'algebra', 'basic',
                               'basic', 'example', 0.0, policy)
    grants = [CapabilityGrant('service', dest, frozenset({'education'})) for dest in ('teaching', 'delivery')]
    guard = LifecycleGuard(CapabilityPolicy(grants)) if scenario == 'guard' else None
    runner = LangGraphProtectionPipeline(cfg, [resource], guard=guard, watermark=None,
                                        generator=fail_generator if scenario == 'generator_error' else None,
                                        monitor=NoExport())
    assert runner.watermark is None
    return runner

def run_scenario(scenario):
    session = new_store(scenario).get_or_create()
    runner = new_runner(scenario)
    calls = 0
    def invoke(request_id):
        nonlocal calls
        try:
            with session.request(request_id, fingerprint='fixed-synthetic-payload') as request:
                if request.cached:
                    return 'cached'
                with session.transaction() as state:
                    state['synthetic_marker'] = True
                    frame = ProtectionContext(session, request_id, 'synthetic', state)
                    with protection_scope(frame):
                        calls += 1
                        runner.run(profile, question, access=AccessScope('fictional'))
                        if scenario == 'downstream_error':
                            raise RuntimeError('synthetic downstream failure')
                request.complete({'status': 'synthetic success'})
            return 'returned'
        except RequestConflict:
            return 'request_conflict'
        except PermissionError:
            if scenario != 'guard':
                raise
            return 'permission_error'
        except RuntimeError as e:
            if (scenario, str(e)) not in {('generator_error', 'synthetic generator failure'),
                                          ('downstream_error', 'synthetic downstream failure')}:
                raise
            return 'runtime_error'
    first = invoke('same-request')
    first_budget = session.budget('copyright')
    first_ledger = runner.budget.get('synthetic')
    first_marker = bool(session.load_state().get('synthetic_marker'))
    retry = invoke('same-request')
    out = {'scenario': scenario, 'first': first, 'same_id_retry': retry,
           'graph_executions_after_retry': calls, 'first_memory_exposure': first_ledger,
           'memory_exposure_after_retry': runner.budget.get('synthetic'),
           'first_durable_copyright': first_budget,
           'durable_copyright_after_retry': session.budget('copyright'),
           'state_marker_persisted': first_marker}
    if scenario == 'guard':
        out['new_id_result'] = invoke('new-request')
        out['graph_executions_after_new_id'] = calls
        out['memory_exposure_after_new_id'] = runner.budget.get('synthetic')
        out['durable_copyright_after_new_id'] = session.budget('copyright')
    return out

def concurrency():
    session = new_store('concurrency').get_or_create()
    entered, release = threading.Event(), threading.Event()
    calls = []
    def first():
        with session.request('shared', fingerprint='same') as request:
            calls.append('executed')
            entered.set()
            assert release.wait(5)
            request.complete({'status': 'ok'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(first)
        assert entered.wait(5)
        try:
            with session.request('shared', fingerprint='same'):
                duplicate = 'unexpected_body'
        except RequestConflict:
            duplicate = 'request_conflict'
        finally:
            release.set()
        running.result(timeout=5)
    with session.request('shared', fingerprint='same') as replay:
        cached = replay.cached
    distinct = new_store('distinct').get_or_create()
    lock, counts = threading.Lock(), {'active': 0, 'maximum': 0, 'calls': 0}
    def work(request_id):
        with distinct.request(request_id, fingerprint='fixed') as request:
            with lock:
                counts['active'] += 1
                counts['calls'] += 1
                counts['maximum'] = max(counts['maximum'], counts['active'])
            time.sleep(0.03)
            with lock:
                counts['active'] -= 1
            request.complete({'status': 'ok'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(work, ('one', 'two')))
    return {'duplicate_in_flight': duplicate, 'duplicate_body_calls': len(calls),
            'completed_replay_cached': cached, 'distinct_calls': counts['calls'],
            'distinct_max_critical_section_overlap': counts['maximum']}

out = {'wrapper': 'session_request_transaction_protection_scope_not_gateway', 'synthetic_only': True,
       'network_blocked': True, 'scenarios': [run_scenario(x) for x in
           ('success', 'guard', 'generator_error', 'downstream_error')], 'concurrency': concurrency()}
print(json.dumps(out, indent=2))

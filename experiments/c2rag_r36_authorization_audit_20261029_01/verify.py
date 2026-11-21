"""Independent recount, locator validation and field-incidence bitmask reference.

This is independent computation, not independent human annotation or a security test.
"""
import hashlib
import itertools
import json
import re
from collections import Counter

from experiments.c2rag_r36_authorization_audit_20261029_01.common import (
    PROJECT_ROOT, covering_coalition, frozen, read, write,
)


def main():
    frozen()
    paths = read('freeze.json')['source_sha256']
    records = 0
    recounted = {}
    for path, expected in paths.items():
        data = (PROJECT_ROOT / path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
        txt = data.decode('utf8')
        if path.endswith('.jsonl'):
            values = [json.loads(s) for s in txt.splitlines() if s.strip()]
        elif path.endswith('.json'):
            value = json.loads(txt)
            values = value if isinstance(value, list) else [value]
        else:
            values = []
        recounted[path] = len(values)
        records += len(values)
    assert records == read('scan_summary.json')['json_records']
    for scanned in read('file_scan.json'):
        assert recounted[scanned['path']] == scanned['records']
    anchors = 0
    for family in read('review_adjudications.json')['families']:
        for location in family['evidence']:
            lines = (PROJECT_ROOT / location['path']).read_text(encoding='utf8').splitlines()
            for n in location['lines']:
                assert location['marker'] in lines[n - 1]
                anchors += 1

    # Build incidence bitmasks independently from source lines, not review.team_fields.
    lines = (PROJECT_ROOT / 'configs/teacher-teams.yaml').read_text(encoding='utf8').splitlines()
    source_teams = {}
    team = None
    for n, line in enumerate(lines, 1):
        if line.startswith('  ') and not line.startswith('   ') and line.endswith(':'):
            team = line.strip()[:-1]
            source_teams[team] = []
        if 'view_fields: [' in line:
            fields = line.split('view_fields: [', 1)[1].split(']', 1)[0].split(',')
            ident = line.split('{id: ', 1)[1].split(',', 1)[0]
            source_teams[team].append((ident, {f.strip() for f in fields}, n))
    team_checks = []
    for row in read('static_input_field_covers.json'):
        nodes = source_teams[row['team']]
        all_fields = sorted({f for _, fields, _ in nodes for f in fields})
        bitmap = {field: 1 << i for i, field in enumerate(all_fields)}
        masks = [sum(bitmap[f] for f in fs) for _, fs, _ in nodes]
        total = (1 << len(all_fields)) - 1
        feasible = []
        for plan in range(1, 1 << len(nodes)):
            union = 0
            for i, mask in enumerate(masks):
                if plan & (1 << i):
                    union |= mask
            if union == total:
                feasible.append((plan.bit_count(), plan))
        minimum = min(n for n, _ in feasible)
        assert minimum == row['minimum_input_field_cover_nodes']
        witnesses = {tuple(nodes[i][0] for i in range(len(nodes)) if plan & (1 << i))
                     for n, plan in feasible if n == minimum}
        assert witnesses == {tuple(w) for w in row['minimum_cover_witnesses']}
        assert [(n['id'], set(n['fields']), n['line']) for n in row['nodes']] == nodes
        # Only a software cross-check, not declaring these groups unauthorized in real life.
        all_groups = [g for k in range(1, min(3, len(nodes)) + 1)
                      for g in itertools.combinations([n[0] for n in nodes], k)]
        cover = covering_coalition({ident: fs for ident, fs, _ in nodes}, all_groups)
        assert (cover is not None) == (minimum <= 3)
        team_checks.append({'team': row['team'], 'bitmask_minimum': minimum,
                            'witness_sets_match': True, 'meaning': 'initial field names only'})
    facts = read('source_facts.json')
    pilots = [json.loads((PROJECT_ROOT / p['path']).read_text(encoding='utf8')) for p in facts['pilot']]
    assert len(pilots) == 20
    assert Counter(p['source_type'] for p in pilots) == {'synthetic_original_AI_assisted': 20}
    assert all('simulated restricted' in p['copyright_and_permissions']['fact_policy'] for p in pilots)
    assert all('single author' in p['annotation'] for p in pilots)
    master = [json.loads(s) for s in (PROJECT_ROOT / facts['master']['path']).read_text(encoding='utf8').splitlines() if s.strip()]
    assert len(master) == 30
    assert len({re.sub('[0-9]+', '#', r['content']) for r in master}) == 1
    assert read('decision.json')['gap'] is None
    frozen()
    write('VERIFICATION.json', {'status': 'PASS', 'frozen_files_unchanged': len(paths),
                              'recounted_json_records': records, 'source_marker_lines_checked': anchors,
                              'team_input_field_bitmask_reference': team_checks,
                              'pilot_synthetic_records_checked': len(pilots),
                              'independent_computation_not_independent_human_review': True,
                              'real_unauthorized_coalition_certificates': 0,
                              'real_task_attack_or_optimizer_runs': 0})
    print(f'PASS: {len(paths)} source hashes; {records} record recount; {anchors} source anchors; 6 field-cover checks.')


if __name__ == '__main__':
    main()

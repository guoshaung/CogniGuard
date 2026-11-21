"""Final integrity and direct constraint checks; preserve wording fixes."""
import json

from experiments.c2rag_r37_joint_constraint_audit_20261029_01.common import (
    OUT, SOURCE, frozen, read, sha, write,
)


def main():
    frozen()
    p = OUT/'MATHEMATICAL_MODEL.md'
    initial = p.read_text(encoding='utf8')
    corrected = initial.replace('engines.py:11(Compiled)、:54(Exact)、:64(trial)',
                                'engines.py:10(Compiled)、:47(Exact)、:55(Exact.trial)')
    corrected = corrected.replace('reference.py:5(closure)、:27(reconstruct)、:36(unsafe)',
                                   'reference.py:5(closure)、:23(reconstruct)、:32(unsafe)')
    changed = corrected != initial
    if changed:
        write('backups/MATHEMATICAL_MODEL_initial_readout.md', initial)
        # Only this new, unfrozen report is corrected; old evidence stays untouched.
        p.write_text(corrected, encoding='utf8', newline='\n')
    write('backups/CODE_VERSION_initial.json', read('CODE_VERSION.json'))
    (OUT/'CODE_VERSION.json').write_text(json.dumps({
        'scripts':{q.name:sha(q.read_bytes()) for q in SOURCE.glob('*.py')},
        'scripts_are_audit_only':True,'production_edits':False}, indent=2), encoding='utf8')
    table = read('MINIMAL_JOINT_TRUTH_TABLE.json')
    for row in table:
        s = set(row['observed'])
        # Standard 0-1 hypergraph constraints, independently from closure/reference.
        feasible = sum(f in s for f in ['a','b']) <= 1 and sum(f in s for f in ['b','c','d']) <= 2
        assert feasible == (not row['unsafe'])
    rs = read('MINIMAL_JOINT_SAVED_PLANS.json')
    assert rs['independent_opt']['plan_masks'] == [14]
    assert all(r['correct']==2 for r in rs['plans'] if r['method'] not in ['NoGate','Counter4'])
    assert all(r['correct']==4 for r in rs['plans'] if r['method'] in ['NoGate','Counter4'])
    assert read('THREE_AGENT_WITNESS.json')[0]['k_min'] == 3
    write('REPORTING_CORRECTION.json', {'kind':'source_line_navigation_only',
                                      'correction_needed_in_this_reproduction':changed,
                                      'initial_retained':'backups/MATHEMATICAL_MODEL_initial_readout.md',
                                      'cause':'manual line references disagreed with computed SOURCE_LOCATORS',
                                      'truth_data_score_protocol_changed':False,'extra_method_runs':0})
    frozen()
    write('FINAL_QA.json', {'status':'PASS','direct_hypergraph_constraints_checked':len(table),
                          'manual_OPT_mask':14,'manual_OPT_utility':3,
                          'historical_sources_unchanged':len(read('freeze.json')['sources']),
                          'new_method_runs':0,'new_assets':0,'all_synthetic_reused_not_independent_samples':True,
                          'code_and_report_line_correction_preserved':True})
    print('PASS: direct hypergraph truth table, manual optimum, actual old decisions and source hashes.')


if __name__ == '__main__':
    main()

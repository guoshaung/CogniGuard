"""Independent polynomial audit of every frozen implication at this instance.

Postprocessing only: no candidate, rule, method or plan is changed. This makes
the Horn enumeration upper-bound argument auditable independently of replay.
"""
import time
import sympy as S
from experiments.c2rag_cross_question_history_20261027_02.common import read,write,verify_freeze


def main():
    verify_freeze();data=read('instance.json');start=time.process_time()
    env=dict(zip(data['variables'],S.symbols('m u F f d',real=True)))
    variables=list(env.values());world={env[k]:S.Rational(v) for k,v in data['nominal_evaluator_only'].items()}
    fields={k:S.sympify(expr,locals=env) for k,expr in data['fields'].items()}
    values={k:S.cancel(expr.subs(world)) for k,expr in fields.items()}
    results=[]
    targets={a['target']:a['fields'] for a in data['assets']}
    for body,head in data['rules']:
        equations=[S.together(fields[k]-values[k]).as_numer_denom()[0] for k in body]
        basis=S.groebner(equations,*variables)
        checked={}
        for h in targets.get(head,[head]):
            polynomial=S.together(fields[h]-values[h]).as_numer_denom()[0]
            remainder=basis.reduce(polynomial)[1]
            assert remainder==0,(body,head,remainder)
            checked[h]={'polynomial':str(polynomial),'remainder':'0'}
        results.append({'body':body,'head':head,'body_observation_polynomials':[str(x) for x in equations],
                        'head_certificates':checked,'valid_for_this_instance_values':True})
    cpu=time.process_time()-start
    total=cpu+read('mathematical_certificates.json')['cpu_seconds']
    assert total<data['cpu_budgets_seconds']['mathematical_verification']
    write('rule_soundness.json',{'all_frozen_rules_sound':True,'rules':results,'cpu_seconds':cpu,
         'combined_math_cpu_seconds':total,'budget_seconds':data['cpu_budgets_seconds']['mathematical_verification'],
         'scope':'nominal instance observations and public equations; nonzero positive denominators retained',
         'uses_engine_or_set_reference':False})
    print('Independent polynomial rule certificates:',len(results),'combined math CPU:',total)


if __name__=='__main__':main()

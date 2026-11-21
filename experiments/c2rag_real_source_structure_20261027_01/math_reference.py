"""Independent public-equation oracle; never imports Horn engines or their rules.

Run with the already installed .venv SymPy. Nonuniqueness is certified by two
actual rational worlds, never inferred from a failed solve or a finite sample.
"""
import itertools
import json
import sys
import sympy as S


def check(task, known):
    symbols=S.symbols(' '.join(task['variables']), real=True)
    if not isinstance(symbols,tuple):symbols=(symbols,)
    env=dict(zip(task['variables'],symbols))
    original={x:S.Rational(a) for x,a in zip(symbols,task['actual'])}
    fields={k:S.sympify(e,locals=env) for k,e in task['fields'].items()}
    values={k:S.cancel(e.subs(original)) for k,e in fields.items()}
    rounded=task.get('rounded_fields',{})
    equations=[S.together(fields[k]-values[k]).as_numer_denom()[0] for k in known if k not in rounded]
    equations=[e for e in equations if e!=0]
    basis=S.groebner(equations,*symbols) if equations else None
    certificates={}
    for target in task['target_fields']:
        if target in known:
            certificates[target]='direct observed exact value or reported rounded interval'
        else:
            poly=S.together(fields[target]-values[target]).as_numer_denom()[0]
            remainder=basis.reduce(poly)[1] if basis else poly
            if remainder==0:certificates[target]='Groebner remainder 0: '+str(poly)
    common={'known':sorted(known),'actual_world':{str(k):str(v) for k,v in original.items()},
            'actual_target':{k:str(values[k]) for k in task['target_fields']},
            'exact_observation_polynomials':[str(e) for e in equations],
            'uniqueness_certificates':certificates}
    if len(certificates)==len(task['target_fields']):
        return dict(common,status='UNIQUE',proof='public polynomial consequences; positive/nonzero denominator assumptions retained')

    def valid(world):
        if any(e.subs(world)!=0 for e in equations):return False
        if task['positivity'] and any(not (v.is_Rational and v>0) for v in world.values()):return False
        if any(not bool(S.sympify(g,locals=env).subs(world)) for g in task.get('guards',[])):return False
        for k in known:
            value=S.cancel(fields[k].subs(world))
            if value.has(S.zoo,S.nan,S.oo) or value.free_symbols:return False
            if k in rounded:
                obs=S.Rational(rounded[k]['reported']);step=S.Rational(rounded[k]['step'])
                if not (obs-step/2<=value<obs+step/2):return False
            elif value!=values[k]:return False
        return True

    def differs(world):
        for k in task['target_fields']:
            val=S.cancel(fields[k].subs(world))
            if k in rounded:
                if S.floor(val+S.Rational(1,2))!=S.Rational(rounded[k]['reported']):return True
            elif val!=values[k]:return True
        return False

    assert valid(original)
    attempts=0
    for variable in symbols:
        nominal=original[variable]
        changes=[nominal/2,nominal*2,nominal*S.Rational(100001,100000),nominal*S.Rational(99999,100000),nominal+1,nominal-1]
        for changed in changes:
            if changed==nominal:continue
            attempts+=1
            solutions=S.solve(equations+[variable-changed],symbols,dict=True,simplify=False)
            for sol in solutions:
                free=set().union(*(e.free_symbols for e in sol.values()))|set(symbols)-set(sol)
                # The fixed search is for counterexamples only; no uniqueness by exhaustion.
                free=sorted(free,key=str)
                for factor in [S.Rational(1),S.Rational(1,2),S.Rational(2),S.Rational(100001,100000),S.Rational(99999,100000)]:
                    assignment={x:original[x]*factor for x in free if x in original}
                    world={x:S.cancel(sol.get(x,x).subs(assignment)) for x in symbols}
                    if any(v.free_symbols or not v.is_Rational for v in world.values()):continue
                    if valid(world) and differs(world):
                        return dict(common,status='NONUNIQUE',search_attempts=attempts,
                                    alternate_world={str(k):str(v) for k,v in world.items()},
                                    alternate_target={k:str(S.cancel(fields[k].subs(world))) for k in task['target_fields']},
                                    proof='two rational worlds satisfy all visible observations and public premises; target differs')
    return dict(common,status='UNKNOWN',search_attempts=attempts,
                reason='neither polynomial uniqueness nor a rational countermodel found; never scored safe')


def main():
    tasks=json.load(open(sys.argv[1],encoding='utf8'))
    queries=json.load(open(sys.argv[2],encoding='utf8'))
    results={}
    for t in tasks:
        tid=t['task_id'];results[tid]={}
        for known in queries[tid]:
            key='|'.join(sorted(known))
            results[tid][key]=check(t,set(known))
        print(tid,len(results[tid]),flush=True)
    with open(sys.argv[3],'x',encoding='utf8') as f:
        json.dump({'sympy_version':S.__version__,'results':results},f,ensure_ascii=False,indent=2)


if __name__=='__main__':main()

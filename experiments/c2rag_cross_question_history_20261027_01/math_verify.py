"""Independent polynomial/world oracle, no imports from ExactK3 or Horn reference."""
import itertools
import time
import sympy as S
from experiments.c2rag_cross_question_history_20261027_01.common import read,write,verify_freeze

WANTED=['K_initial','F_push','f','d_push','v1_sq','d_stop']


def main():
    verify_freeze();data=read('instance.json');queries=read('math_queries.json')
    started=time.process_time();limit=data['cpu_budgets_seconds']['mathematical_verification']
    symbols=S.symbols('m u F f d',real=True);env=dict(zip(data['variables'],symbols))
    nominal={env[k]:S.Rational(v) for k,v in data['nominal_evaluator_only'].items()}
    fields={k:S.sympify(expr,locals=env) for k,expr in data['fields'].items()}
    values={k:S.cancel(expr.subs(nominal)) for k,expr in fields.items()}
    output={};issues=[]
    for index,known in enumerate(queries):
        key='|'.join(known)
        if time.process_time()-started>=limit:
            output[key]={'known':known,'fields':{k:{'status':'UNKNOWN','reason':'CPU budget exhausted'} for k in WANTED}}
            continue
        equations=[S.together(fields[k]-values[k]).as_numer_denom()[0] for k in known]
        equations=[e for e in equations if e!=0]
        try:
            basis=S.groebner(equations,*symbols) if equations else None
            states={}
            for target in WANTED:
                poly=S.together(fields[target]-values[target]).as_numer_denom()[0]
                remainder=basis.reduce(poly)[1] if basis else poly
                if remainder==0:
                    states[target]={'status':'UNIQUE','polynomial':str(poly),'remainder':'0'}
                else:states[target]={'status':'UNKNOWN','reason':'countermodel not yet found'}
            if any(v['status']=='UNKNOWN' for v in states.values()):
                for variable in symbols:
                    n=nominal[variable]
                    for changed in [n/2,n*2,n*S.Rational(100001,100000),n*S.Rational(99999,100000),n+1,n-1]:
                        if changed==n or time.process_time()-started>=limit:break
                        try:solutions=S.solve(equations+[variable-changed],symbols,dict=True,simplify=False)
                        except (NotImplementedError,ValueError) as error:
                            issues.append({'query':key,'operation':'solve','error':str(error)});continue
                        for solution in solutions:
                            free=set().union(*(x.free_symbols for x in solution.values())) | (set(symbols)-set(solution))
                            for factor in [S.Rational(1),S.Rational(1,2),S.Rational(2),S.Rational(100001,100000),S.Rational(99999,100000)]:
                                assignment={x:nominal[x]*factor for x in free if x in nominal}
                                world={x:S.cancel(solution.get(x,x).subs(assignment)) for x in symbols}
                                if any(x.free_symbols or not x.is_Rational or x<=0 for x in world.values()):continue
                                if world[env['F']]<=world[env['f']]:continue
                                if any(e.subs(world)!=0 for e in equations):continue
                                for target in WANTED:
                                    alt=S.cancel(fields[target].subs(world))
                                    if states[target]['status']=='UNKNOWN' and alt!=values[target]:
                                        states[target]={'status':'NONUNIQUE','actual':str(values[target]),'alternate':str(alt),
                                            'alternate_world':{str(k):str(v) for k,v in world.items()}}
                        if all(v['status']!='UNKNOWN' for v in states.values()):break
                    if all(v['status']!='UNKNOWN' for v in states.values()) or time.process_time()-started>=limit:break
            output[key]={'known':known,'observation_polynomials':[str(e) for e in equations],
                         'actual_world':{str(k):str(v) for k,v in nominal.items()},'fields':states}
        except Exception as error:
            issues.append({'query':key,'operation':'proof','error':str(error)})
            output[key]={'known':known,'fields':{k:{'status':'UNKNOWN','reason':str(error)} for k in WANTED}}
        if (index+1)%25==0:print('math queries',index+1,'CPU',round(time.process_time()-started,2),flush=True)
    unknown=sum(s['status']=='UNKNOWN' for q in output.values() for s in q['fields'].values())
    write('mathematical_certificates.json',{'sympy_version':S.__version__,'budget_cpu_seconds':limit,
          'cpu_seconds':time.process_time()-started,'queries':output,'unknown_field_count':unknown,'issues':issues,
          'uses_horn_rules':False,'evaluated_fields':WANTED})
    print('math complete',len(output),'unknown fields',unknown,flush=True)


if __name__=='__main__':main()

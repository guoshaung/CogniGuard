"""Frozen bounded grammars and mature exact constraints, not a new C2 algorithm."""
import importlib.util,re
from fractions import Fraction as F
from pathlib import Path

P=Path(__file__).resolve().parent
def imported(name,file):
    spec=importlib.util.spec_from_file_location(name,P/file)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def norm(text):
    text=text.replace('\u2212','-').replace('–','-').replace('\u00a0',' ').replace('’',"'")
    return re.sub(r'\s+',' ',text).strip()
def number(s):return str(F(s.replace(',','')))
def atom(*v):return tuple(str(x) for x in v)
NUM=r'-?\d+(?:,\d{3})*(?:\.\d+)?(?:/\d+)?'

def typed(text,query,contract):
    """Generic finite grammar; receives public contract, never target gold/source."""
    t=norm(text);q=norm(query);low=t.lower();facts=set();unsupported=[]
    if not t:return facts,unsupported
    if 'not linear' in low or 'need not be linear' in low or 'not the case' in low:
        return set(),['negation outside supported constraint grammar']
    if 'first equation' in low or 'other two' in low:
        return set(),['unresolved equation anaphora / restrictive premise']
    if 'initial power quickly decreases' in low:
        unsupported.append('transient covariation/process relation not modeled; no causal claim')
    # Public family and procedure statements are represented, never blanket safe.
    if 'linear function' in low or 'growing linearly' in low or 'rule is affine' in low:
        facts.add(atom('family','affine'))
    if 'calculate and interpret the slope' in low:facts.add(atom('goal','calculate_interpret_slope'))
    if t=='Use the known relationship and keep the units consistent.':
        facts.add(atom('instruction','apply_known_relation_check_units'))
    if 'hot and cold states are distinct' in low:facts.add(atom('premise','hot_cold_distinct'))
    if 'not universally valid' in low and "ohm's law" in low:
        facts.add(atom('scope','ohm_law','not_universal'))
    if 'ohmic materials' in low and 'independent of voltage' in low:
        facts.update([atom('conditional_independence','R','V','ohmic_material'),
                      atom('conditional_independence','R','I','ohmic_material')])
    if 'unit for resistance is an ohm' in low:
        facts.add(atom('unit','R','ohm'))
    if contract['kind']=='affine':
        iu,ou=contract['input_unit'],contract['output_unit']
        for x,y in re.findall(r'\(\s*('+NUM+r')\s*,\s*('+NUM+r')\s*\)',t):
            facts.add(atom('point',number(x),number(y),iu,ou))
        for x,y in re.findall(r'f\(\s*('+NUM+r')\s*\)\s*=\s*('+NUM+r')',t):
            facts.add(atom('point',number(x),number(y),iu,ou))
        for year,value in re.findall(r'(?:In|By)\s+(\d{4}),\s+(?:the |a town.s )?population (?:was|had grown to)\s+('+NUM+r')',t,re.I):
            facts.add(atom('point',str(int(year)-contract.get('time_origin',0)),number(value),iu,ou))
        for months,value in re.findall(r'After\s+('+NUM+r')\s+months from \d{4},\s+the population is\s+('+NUM+r')',t,re.I):
            facts.add(atom('point',str(F(number(months))/12),number(value),iu,ou))
        if 'year 2004 would correspond to t=0' in low or 'time origin is 2004' in low:
            facts.add(atom('time_origin','2004'))
        if 'assume this trend continues' in low:facts.add(atom('premise','linear_trend_continues'))
    if contract['kind'] in ['ohm','hotcold']:
        for state,var,pattern in [
            ('cold','R',r'cold resistance was\s+('+NUM+r')\s*(?:Ω|ohms?)'),
            ('hot','P',r'The\s+('+NUM+r')\s*W dissipated by the hot headlight'),
            ('cold','P',r'the\s+('+NUM+r')\s*W when cold')]:
            for value in re.findall(pattern,t,re.I):facts.add(atom('value',state,var,number(value),'ohm' if var=='R' else 'W'))
        if contract['kind']=='ohm':
            # State comes from the declared same-device, same-operating-state contract.
            for value,unit in re.findall(r'('+NUM+r')\s*(mA|mV|A|V)\b',t):
                var='I' if unit.endswith('A') else 'V';v=F(number(value))/(1000 if unit.startswith('m') else 1)
                facts.add(atom('value','operating',var,str(v),'A' if var=='I' else 'V'))
    if not facts:unsupported.append('no supported relation; text is not silently empty knowledge')
    return facts,unsupported

def r8_front(text,query,contract):
    r8=imported('r8_current','frozen/r8_runner.py')
    status,pt=r8.parse_pair(query,text)
    if status!='OK' or (text and pt is None):return set(),['R8 current frontend unsupported query/reply']
    return ({atom('point',str(pt[0]),str(pt[1]),contract['input_unit'],contract['output_unit'])} if pt else set()),[]

def slots(text,query,contract):
    old=imported('old_slots','frozen/content_risk.py')
    d=old.parse('affine' if contract['kind']=='affine' else 'power',text)
    return {atom('legacy_slot',k,v) for k,v in d.items()},([] if d or not text else ['legacy slot grammar unsupported'])

def old_rules(text,query,contract):
    old=imported('old_rules','frozen/symbolic_attacker.py')
    schema='multiplier times x plus offset' if contract['kind']=='affine' else 'current and power'
    out=old.attack({'known_task_schema':schema,'observed_query_reply_pairs':[{'query':query,'reply':text}]})
    # Existing rule binds a bare numeric resistance but drops unit/state.
    facts=set()
    if out['expr'] is not None:facts.add(atom('legacy_expression',out['expr']))
    for pair in out['evidence']:
        n=old.single_number(pair['reply'])
        if n is not None and 'resistance' in query.lower():facts.add(atom('unscoped_value','resistance',number(n)))
    return facts,([] if facts else ['existing rule has no supported relation'])

EXTRACTORS={'Current-Slots':slots,'Existing-RelationRules':old_rules,
            'Arithmetic-Logical-Representation':typed,'Conditional-Current-Frontend':r8_front}

def history_facts(history,contract,extractor=typed):
    facts=set();unknown=[]
    for q,r in history:
        # Query measurements are visible even when the reply is refused.
        if contract['kind']=='ohm':
            for val,unit in re.findall(r'('+NUM+r')\s*(mA|A)\b',norm(q)):
                v=F(number(val))/(1000 if unit=='mA' else 1)
                facts.add(atom('value','operating','I',str(v),'A'))
        if r:
            f,u=extractor(r,q,contract);facts|=f;unknown+=u
    return facts,unknown

def closure(facts,contract):
    """Exact Fraction arithmetic; function equivalence is algebraic, no probes."""
    kind=contract['kind'];target=None;parts={};status='KNOWN';constraints=[]
    if kind=='affine':
        points=[(F(a[1]),F(a[2])) for a in facts if a[0]=='point']
        constraints=sorted(set(points))
        if points:
            x0,y0=points[0]
            if any(x==x0 and y!=y0 for x,y in points):status='UNKNOWN_INCONSISTENT'
            else:
                parts={'point_constraints':len(set(points))}
                other=next(((x,y) for x,y in points if x!=x0),None)
                if other:
                    x1,y1=other;a=(y1-y0)/(x1-x0);b=y0-a*x0
                    if all(a*x+b==y for x,y in points):target=(str(a),str(b))
                    else:status='UNKNOWN_INCONSISTENT'
    else:
        values={}
        for a in facts:
            if a[0]=='value':
                key=(a[1],a[2]);v=F(a[3])
                if key in values and values[key]!=v:status='UNKNOWN_INCONSISTENT'
                values[key]=v
        if kind=='ohm':
            i,v=values.get(('operating','I')),values.get(('operating','V'))
            if i is not None:parts['I']=str(i)
            if v is not None:parts['V']=str(v)
            if i is not None and v is not None:
                if not i:status='UNKNOWN_ZERO_DIVISION'
                else:target=(str(v/i),)
        else:
            # Public known voltage is model context, not a target coefficient.
            voltage=F(contract['known_voltage']);hot=values.get(('hot','P'));cold=values.get(('cold','R'))
            if hot is not None and hot:parts['hot_R']=str(voltage**2/hot)
            if cold is not None:parts['cold_R']=str(cold)
            if {'hot_R','cold_R'}<=parts.keys():target=(parts['hot_R'],parts['cold_R'])
    return {'status':status,'complete':target is not None and status=='KNOWN','parameters':target,'parts':parts,
            'constraints':[[str(x),str(y)] for x,y in constraints]}

def assess(history,contract,method='B4-Closure'):
    extractor=r8_front if method=='B5-Conditional-Current' else slots if method=='B3-SharedSet-RuleClosure' else typed
    facts,unknown=history_facts(history,contract,extractor)
    if method=='B3-SharedSet-RuleClosure':
        needed={'a','b'} if contract['kind']=='affine' else {'r','p'}
        present={a[1] for a in facts if a[0]=='legacy_slot'}
        return {'risk':int(needed<=present),'unknown':bool(unknown),'unsupported':unknown,'facts':sorted(facts)}
    if unknown:return {'risk':None,'unknown':True,'unsupported':unknown,'facts':sorted(facts)}
    out=closure(facts,contract)
    return {'risk':int(out['complete']) if out['status']=='KNOWN' else None,
            'unknown':out['status']!='KNOWN','unsupported':[],'facts':sorted(facts),'closure':out}

def attacker(history,contract):
    # Caller passes actual visible pairs and public contract only, never gold.
    facts,unknown=history_facts(history,contract)
    out=closure(facts,contract)
    out.update({'unknown':bool(unknown) or out['status']!='KNOWN','unsupported':unknown,'visible_fact_atoms':sorted(facts)})
    if out['unknown']:out['complete']=None
    return out

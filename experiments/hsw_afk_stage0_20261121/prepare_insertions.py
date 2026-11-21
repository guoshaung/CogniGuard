"""Quick-pilot insertions with source-backed arithmetic/unit evidence only."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import sympy as sp

from forms import UREG

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'var/results/hsw-st/afk_stage0_20261121'


def main():
    target=OUT/'QUICK_SCENARIOS.json'
    if target.exists():raise FileExistsError(target)
    sys.path.insert(0,str(ROOT/'experiments/hsw_certinsert_eval04_formula_20261114'))
    # The original F module is reused as requested; it isolates its own CPU path.
    from carrier import Carrier, Renderer, FORMULAS, parse_equation, equation_proposals
    import prepare_cpu as legacy
    from structure_adapter import split,allowed_offset
    from e1_v4r7f_anchors import numbers
    rows=json.loads((OUT/'QUICK_INPUTS.json').read_bytes())
    corpus=json.loads((ROOT/'var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json').read_bytes())
    sources={r['id']:r for r in corpus if r['kind']=='generated'}
    result=[];rejections=[]
    with Renderer() as renderer:
        carrier=Carrier(renderer)
        for index,row in enumerate(rows,1):
            source=sources[row['source_id']];text=row['original'];question=source.get('question','')
            structure=split(text,question)
            def body(a,b):return any(l<=a and b<=r for l,r in structure['body_intervals'])
            plan=legacy.build_plan(dict(id=row['id'],text=text),'AFK_DEV','A4',lambda _:[])
            slots=[s for s in plan['candidates'] if allowed_offset(structure,s['offset'])]
            chosen=[]
            for slot in slots:
                if len(chosen)==2:break
                if chosen and abs(slot['word_index']-chosen[-1]['word_index'])<8:continue
                chosen.append(slot)
            connective=text;connective_edits=[]
            for slot in reversed(chosen):
                off=slot['offset'];old=text[off:off+1]
                prefix='Here, ' if len(connective_edits)==0 else 'In this case, '
                following=old.lower() if off in plan['case_eligibility'] else old
                connective=connective[:off]+prefix+following+connective[off+1:]
                connective_edits.append(dict(start=off,inserted=prefix,validation='FROZEN_CERTINSERT_SLOT',kind='connective'))
            scenarios=[dict(kind='variant',text=row['variant'],edits=row['edits'],
                            status='READY' if row['edits'] else 'NOT_APPLICABLE_NO_ATTESTED_GROUP'),
                       dict(kind='connective',text=connective,edits=connective_edits,
                            status='READY' if connective_edits else 'NOT_APPLICABLE_NO_FROZEN_SLOT')]
            # Parenthetical equalities reuse F's exact generation, proof and renderer.
            inserted=[]
            inventory=carrier.inventory(text,question)
            for slot in inventory['slots']:
                if slot['kind']!='equation' or not slot['alternates']:continue
                value=slot['alternates'][0]
                inserted.append(dict(offset=slot['offset'],inserted=' (equivalently, '+
                    (r'\('+value['text']+r'\)' if slot['latex'] else value['text'])+')',
                    validation=value['validation'],new_equation=value['text']))
                if len(inserted)==2:break
            altered=text
            for change in sorted(inserted,key=lambda x:x['offset'],reverse=True):
                off=change['offset'];altered=altered[:off]+change['inserted']+altered[off:]
            scenarios.append(dict(kind='equivalent_parenthesis',text=altered,edits=inserted,
                status='READY' if inserted else 'NOT_APPLICABLE_NO_VERIFIED_EQUATION'))
            intermediate=[];substitution=[]
            for match in FORMULAS.finditer(text):
                if not body(*match.span()):continue
                raw=next(g for g in match.groups() if g is not None)
                try:
                    parts=parse_equation(raw,True)
                except Exception:continue
                left,right=parts
                if not right.free_symbols and sp.count_ops(right)>0:
                    value=sp.cancel(right)
                    if value.is_real and value.is_finite and str(value) in numbers(text):
                        new=sp.latex(left)+' = '+sp.latex(right)+' = '+sp.latex(value)
                        if renderer.valid(new) and sp.cancel(right-value)==0:
                            intermediate.append(dict(offset=match.end(),inserted='\nIntermediate step: '+r'\('+new+r'\)'+'.\n',
                                validation='SYMPY_EXACT_ARITHMETIC_SOURCE_RESULT',equation=new))
                # Unit-bearing numerical substitution uses only explicit source bindings.
                variables=sorted(right.free_symbols,key=str)
                if variables and len(variables)<=3 and all(re.fullmatch('[A-Za-z]',str(v)) for v in variables):
                    bindings={};displays={}
                    for v in variables:
                        pattern=r'(?<!\w)'+re.escape(str(v))+r'\s*=\s*([-+]?\d+(?:\.\d+)?)\s*(kg|g|m/s\^2|m/s²|m/s|m|s|N|J)\b'
                        found=re.search(pattern,text)
                        if not found:break
                        numeric,unit=found.groups()
                        bindings[v]=UREG.Quantity(float(numeric),unit.replace('²','**2').replace('^','**'))
                        displays[v]='('+numeric+' '+unit+')'
                    if len(bindings)==len(variables):
                        try:
                            # SymPy lambdify evaluates arithmetic on pint quantities.
                            calculation=sp.lambdify(variables,right,modules='math')(*[bindings[v] for v in variables])
                            assert hasattr(calculation,'dimensionality')
                            original=right
                            rendered=sp.sstr(original)
                            for v in variables:rendered=re.sub(r'\b'+re.escape(str(v))+r'\b',displays[v],rendered)
                            substitution.append(dict(offset=match.end(),inserted='\nSubstitution: '+str(left)+' = '+rendered+'.\n',
                                validation='SYMPY_ORIGINAL_FORMULA_AND_PINT_EVALUATION',
                                source_bindings={str(k):str(v) for k,v in bindings.items()},result=str(calculation)))
                        except Exception:pass
                if len(intermediate)>=2 and len(substitution)>=2:break
            for kind,edits in [('intermediate_arithmetic',intermediate[:2]),('unit_substitution',substitution[:2])]:
                altered=text
                for change in sorted(edits,key=lambda x:x['offset'],reverse=True):
                    off=change['offset'];altered=altered[:off]+change['inserted']+altered[off:]
                scenarios.append(dict(kind=kind,text=altered,edits=edits,
                    status='READY' if edits else 'NOT_APPLICABLE_NO_SOURCE_VERIFIED_SUBSTITUTION'))
            # Dimensional checks require all participating units in the source.
            dimensional=[]
            for expression,target_unit,label,patterns in [
                ('kg*m/s**2','N','kg·m/s² = N',[r'\bkg\b',r'm\s*/\s*s(?:\^2|²)',r'\bN\b']),
                ('N*m','J','N·m = J',[r'\bN\b',r'\bm\b',r'\bJ\b'])]:
                if all(re.search(p,text) for p in patterns) and UREG.Quantity(1,expression)==UREG.Quantity(1,target_unit):
                    dimensional.append(dict(inserted='\nCheck: '+label+'.\n',validation='PINT_EXACT_DIMENSION_AND_SCALE',
                                            source_units=patterns))
            edits=dimensional[:2]
            off=structure['body_intervals'][-1][1] if structure['body_intervals'] else None
            if off is None:edits=[]
            altered=text
            if edits:altered=text[:off]+''.join(x['inserted'] for x in edits)+text[off:]
            scenarios.append(dict(kind='dimension_check',text=altered,edits=edits,
                status='READY' if edits else 'NOT_APPLICABLE_SOURCE_UNITS_MISSING'))
            result.append(dict(id=row['id'],source_id=row['source_id'],original=text,scenarios=scenarios))
            print('Quick insertion prepare',index,'/30',flush=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    freeze=dict(status='QUICK_INSERTIONS_FROZEN_BEFORE_COMPRESSION',inputs_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        eligible_by_kind={kind:sum(s['status']=='READY' for r in result for s in r['scenarios'] if s['kind']==kind)
            for kind in [s['kind'] for s in result[0]['scenarios']]},
        rule='At most2 each; only source-backed symbolic/pint proof; no substitute fabricated data')
    (HERE/'QUICK_INSERTION_FREEZE.json').write_text(json.dumps(freeze,indent=2),encoding='utf8')


if __name__=='__main__':main()

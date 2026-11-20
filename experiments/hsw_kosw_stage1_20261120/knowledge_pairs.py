"""Five task-specified minimal knowledge-edit families; no LLM calls."""
import itertools
import re
from decimal import Decimal

import pint
import sympy as sp
from sympy.parsing.latex import parse_latex

UNITS=pint.UnitRegistry()
NUMBER=re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
UNIT=re.compile(r'(?<!\w)([-+]?\d+(?:\.\d+)?)\s+(mm|cm|km|m|mg|kg|g|ms|s|min|h|mL|L|Pa|kPa|J|kJ)\b')
UNIT_SIBLINGS={'mm':['cm','m'],'cm':['mm','m'],'km':['m'],'m':['cm','km'],
 'mg':['g'],'kg':['g'],'g':['mg','kg'],'ms':['s'],'s':['ms','min'],'min':['s','h'],
 'h':['min'],'mL':['L'],'L':['mL'],'Pa':['kPa'],'kPa':['Pa'],'J':['kJ'],'kJ':['J']}
POLARITY={'increases':'decreases','decreases':'increases','higher':'lower','lower':'higher',
          'more':'less','less':'more','positive':'negative','negative':'positive'}


def replace(text,a,b,value):
    return text[:a]+value+text[b:]


def variants(source,siblings,rng,anchors):
    text=source['text']
    if not source['anchors']:
        return []
    choices=[]
    for match in NUMBER.finditer(text):
        old=Decimal(match[0])
        for factor in ['0.5','2','10']:
            new=old*Decimal(factor)
            if new!=old:
                value=format(new,'f')
                choices.append(dict(type='K-number',text=replace(text,*match.span(),value),
                    validation=dict(old=str(old),new=str(new),factor=factor,unequal=True)))
    for match in UNIT.finditer(text):
        value,unit=match.groups()
        for other in UNIT_SIBLINGS[unit]:
            old=UNITS.Quantity(float(value),unit)
            new=UNITS.Quantity(float(value),other)
            if old.dimensionality==new.dimensionality and old.to_base_units()!=new.to_base_units():
                choices.append(dict(type='K-unit',text=replace(text,*match.span(2),other),
                    validation=dict(number=value,old=unit,new=other,same_dimension=True,quantity_changed=True)))
    for term,alternatives in siblings.get(source['subject'],{}).items():
        matches=list(re.finditer(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text,re.I))
        if not matches:
            continue
        match=matches[0]
        for other in alternatives:
            choices.append(dict(type='K-term',text=replace(text,*match.span(),other),
                validation=dict(old=match[0],new=other,unequal=match[0].casefold()!=other.casefold())))
    for match in re.finditer(r'\b(increases|decreases|higher|lower|more|less|positive|negative)\b',text,re.I):
        new=POLARITY[match[0].lower()]
        choices.append(dict(type='K-polarity',text=replace(text,*match.span(),new),
                            validation=dict(old=match[0],new=new,edited_occurrences=1)))
    for match in re.finditer(r'\b(is|are|was|were)\b(?!\s+not\b)',text,re.I):
        choices.append(dict(type='K-polarity',text=replace(text,match.end(),match.end(),' not'),
                            validation=dict(insertion='not',offset=match.end(),edited_occurrences=1)))
    for match in re.finditer(r'\\\((.*?)\\\)|\\\[(.*?)\\\]',text,re.S):
        raw=match[1] or match[2]
        try:
            expr=parse_latex(raw,strict=True)
            if isinstance(expr,sp.Equality):
                expr=expr.lhs-expr.rhs
            if not isinstance(expr,sp.Expr):
                continue
            mutants=[]
            symbols=sorted(expr.free_symbols,key=str)
            for a,b in itertools.combinations(symbols,2):
                mutants.append(expr.xreplace({a:b,b:a}))
            for atom in sp.preorder_traversal(expr):
                if isinstance(atom,sp.Mul) and len(atom.args)>=2:
                    mutants.append(expr.xreplace({atom:atom.args[0]/sp.Mul(*atom.args[1:])}))
                if isinstance(atom,sp.Pow):
                    mutants.append(expr.xreplace({atom:sp.Pow(atom.base,atom.exp+1)}))
            for new in mutants:
                difference=sp.simplify(expr-new)
                if difference==0 or difference.equals(0) is not False:
                    continue
                output=replace(text,*match.span(),'\\('+sp.latex(new)+'\\)')
                choices.append(dict(type='K-formula',text=output,validation=dict(
                    original_latex=raw,new_latex=sp.latex(new),difference=str(difference),non_equivalent=True)))
        except (Exception,):
            # Task explicitly allows a formula parse/validation failure to skip that formula.
            continue
    grouped={kind:[v for v in choices if v['type']==kind] for kind in sorted({v['type'] for v in choices})}
    rng.shuffle(choices)
    selected=[];seen={text}
    for _ in range(rng.randint(1,2)):
        available={kind:[v for v in values if v['text'] not in seen] for kind,values in grouped.items()}
        available={k:v for k,v in available.items() if v}
        if not available:
            break
        kind=rng.choice(sorted(available));item=rng.choice(available[kind]);seen.add(item['text'])
        selected.append(item)
    return selected

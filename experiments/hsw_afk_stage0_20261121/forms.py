"""Attested surface forms only; spans retain original bytes and unit magnitudes."""
import re
from decimal import Decimal

import pint
import sympy as sp
from sympy.parsing.latex import parse_latex

UREG = pint.UnitRegistry(non_int_type=Decimal)
MATH = re.compile(r'\\\((.*?)\\\)|\\\[(.*?)\\\]|\$\$(.*?)\$\$|(?<!\\)\$(?!\$)(.*?)(?<!\\)\$', re.S)
NUMBER = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
COUNT_WORDS = dict(enumerate('zero one two three four five six seven eight nine ten'.split()))


def plain(text, spans):
    chars = list(text)
    for start,end in spans:
        chars[start:end] = ' '*(end-start)
    return ''.join(chars)


def formula_class(raw):
    """Keep equation-side order; never solve, transpose or swap factors as an edit."""
    if len(raw)>400 or raw.count('=')>1 or any(x in raw for x in ['<','>','\\begin','\\text']):
        raise ValueError('unsupported formula boundary')
    values=[]
    for side in raw.split('='):
        side=side.replace('½',r'\frac{1}{2}').replace('²','^2').replace('³','^3')
        x=parse_latex(side,strict=True)
        if not isinstance(x,sp.Expr) or x.atoms(sp.Function) or sp.count_ops(x)>35:
            raise ValueError('unsupported expression')
        # Arithmetic normalization of rational coefficients, not general equals().
        values.append(sp.srepr(sp.cancel(x)))
    return '|EQ|'.join(values)


def formula_items(task):
    raw = task
    try:
        canonical=formula_class(raw)
        styles=[]
        if re.search(r'\\(?:d?frac)\s*\{\s*1\s*\}\s*\{\s*[2-9]\s*\}',raw):
            styles.append(('fraction_coefficient','latex_fraction'))
        elif re.search(r'\(?1\s*/\s*[2-9]\)?',raw):
            styles.append(('fraction_coefficient','inline_fraction'))
        elif re.search(r'/\s*[2-9]\s*$',raw):
            styles.append(('fraction_coefficient','trailing_division'))
        elif '½' in raw:
            styles.append(('fraction_coefficient','unicode_half'))
        multiplication=[('latex_times',r'\times'),('latex_cdot',r'\cdot'),('unicode_times','×'),('unicode_dot','·')]
        for label,token in multiplication:
            if token in raw:
                styles.append(('multiplication',label))
        return dict(raw=raw,canonical=canonical,styles=styles,status='PARSED')
    except Exception as exc:
        return dict(raw=raw,status='UNSUPPORTED',reason=type(exc).__name__)


def count_slots(doc):
    """Count nouns from the frozen spaCy pipeline, excluding physical quantities."""
    items=[]
    for token in doc:
        word=token.text.casefold()
        if word in COUNT_WORDS.values():
            value=next(n for n,w in COUNT_WORDS.items() if w==word);style='word'
        elif re.fullmatch(r'(?:[0-9]|10)',word):
            value=int(word);style='digit'
        else:continue
        noun=token.head if token.head.pos_=='NOUN' and token.head.i>token.i else None
        if noun is None or noun.i-token.i>3 or any(t.text in ['=','%','°'] for t in doc[token.i:noun.i]):continue
        # Unit nouns carry numerical quantities rather than discrete counts.
        try:
            UREG.Unit(noun.lemma_)
            continue
        except Exception:pass
        if token.idx>0 and doc.text[token.idx-1] in '_^':continue
        items.append(dict(dimension='small_count',canonical=str(value)+'|'+noun.lemma_.casefold(),
            style=style,start=token.idx,end=token.idx+len(token.text),raw=token.text,
            validation='SPACY_COUNT_NOUN_AND_EXACT_INTEGER'))
    return items


def scan(text, parsed, counts=None):
    found=[]; math=list(MATH.finditer(text)); prose=plain(text,[m.span() for m in math])
    def add(dim,canonical,style,start,end,raw,validation):
        found.append(dict(dimension=dim,canonical=canonical,style=style,start=start,end=end,
                          raw=raw,validation=validation))
    for m in math:
        raw=next(g for g in m.groups() if g is not None)
        item=parsed.get(raw,{})
        for dim,style in item.get('styles',[]):
            add(dim,item['canonical'],style,m.start(),m.end(),m[0],'SYMPY_CANONICAL')
    # Only allow equivalent spellings for the SAME unit, never scale conversions.
    atom=lambda token:r'(?:\\(?:mathrm|text)\s*\{\s*'+token+r'\s*\}|'+token+r')'
    sep=r'(?:\s|\\[,;! ]|~)*'
    power=r'(?:\s*(?:\^\{?[−-]?\d\}?|[⁻¹²³]))*'
    unit_rx=re.compile(r'(?<![A-Za-z])(?P<u>(?:'+atom('m')+sep+r'/'+sep+atom('s')+power+
        r'|'+atom('m')+sep+r'(?:[·⋅]|\\cdot)?'+sep+atom('s')+sep+r'(?:\^\{?[−-][12]\}?|⁻[¹²])'+
        r'|\\(?:mathrm|text)\s*\{\s*m\s*/\s*s(?:\^\{?2\}?|²)?\s*\}'+
        r'|meters? per second(?: squared)?))(?![A-Za-z])')
    for m in unit_rx.finditer(text):
        raw=m['u']; compact=re.sub(r'\s+','',raw)
        squared=bool(re.search(r'2|²|squared',raw))
        canonical='m/s**2' if squared else 'm/s'
        if 'per second' in raw:style='words'
        elif '/' in raw:
            style=('solidus_unicode' if '²' in raw else 'solidus_caret' if re.search(r'\^\{?2',raw) else 'solidus')
            if '\\mathrm' in raw or '\\text' in raw:style='latex_'+style
        elif '·' in raw or '⋅' in raw:style='dot_negative_power'
        else:style='space_negative_power'
        try:
            quantity=UREG.Quantity(Decimal(1),canonical)
            # Recognized templates have exact fixed integer exponents and unit names.
            expected='m/s**2' if squared else 'm/s'
            assert quantity==UREG.Quantity(Decimal(1),expected)
            add('unit_spelling',canonical,style,m.start(),m.end(),raw,'PINT_EXACT')
        except Exception:
            continue
    occupied=[(a['start'],a['end']) for a in found if a['dimension']=='unit_spelling']
    # Broaden to SI symbols and spelled unit names. A bare symbol requires a
    # preceding numerical quantity, avoiding prose letters such as "a" or "s".
    symbols='kg|mg|km|cm|mm|mol|kPa|MPa|Pa|kJ|J|kW|W|kN|N|mL|L|Hz|kHz|MHz|m|g|s|h|K|A|V'
    names={'kilograms':'kg','kilogram':'kg','grams':'g','gram':'g','meters':'m','meter':'m',
        'centimeters':'cm','centimeter':'cm','seconds':'s','second':'s','hours':'h','hour':'h',
        'liters':'L','liter':'L','newtons':'N','newton':'N','joules':'J','joule':'J',
        'watts':'W','watt':'W','pascals':'Pa','pascal':'Pa','moles':'mol','mole':'mol',
        'kelvin':'K','volts':'V','volt':'V','amperes':'A','ampere':'A'}
    rx=re.compile(r'\\(?:mathrm|text)\s*\{\s*('+symbols+r')\s*\}|(?<![A-Za-z])('+symbols+r')(?![A-Za-z])|\b('+ '|'.join(names)+r')\b')
    for m in rx.finditer(text):
        if any(a<m.end() and b>m.start() for a,b in occupied):continue
        raw=m[0];wrapped=m[1] is not None;word=m[3] is not None
        before=text[max(0,m.start()-25):m.start()]
        if not re.search(r'\d\s*(?:\\[,; ]|~|\}|\)|\*)?\s*$',before):continue
        unit=m[1] or m[2] or names[m[3]]
        try:
            parsed_unit=UREG.Unit(unit)
        except Exception:continue
        style='latex_wrapped_symbol' if wrapped else 'word_unit' if word else 'plain_symbol'
        add('unit_spelling',str(parsed_unit),style,*m.span(),raw,'PINT_IDENTICAL_UNIT_NO_CONVERSION')
    for m in re.finditer(r'(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d{4,})(?![\w,]|\.\d)',text):
        add('large_number',m[0].replace(',',''),'comma' if ',' in m[0] else 'plain',*m.span(),m[0],'EXACT_DIGITS')
    for dim,rx,symbol,word in [
        ('angle',rf'(?<![\w.])({NUMBER})\s*(°|degrees?)(?!\w)','°','degrees'),
        ('percentage',rf'(?<![\w.])({NUMBER})\s*(%|percent)(?!\w)','%','percent')]:
        for m in re.finditer(rx,text,re.I):
            add(dim,str(Decimal(m[1].replace(',',''))),'symbol' if m[2]==symbol else 'word',*m.span(),m[0],'EXACT_VALUE_SAME_UNIT')
    # Small integers: only explicit grammatical count followed by an unambiguous
    # count noun. Adjectival quantities/results are not treated as word/digit slots.
    count_nouns='objects|particles|students|samples|trials|coins|dice|balls|electrons|protons|neutrons|molecules|atoms|points|sides|vertices|groups|steps'
    options='|'.join(COUNT_WORDS.values())+'|[0-9]|10'
    for m in re.finditer(r'\b('+options+r')\s+('+count_nouns+r')\b',prose,re.I):
        word=m[1].lower();value=int(word) if word.isdigit() else next(n for n,w in COUNT_WORDS.items() if w==word)
        add('small_count',str(value)+'|'+m[2].lower(),'digit' if word.isdigit() else 'word',m.start(1),m.end(1),m[1],'COUNT_CONTEXT_EXACT_INTEGER')
    for m in re.finditer(r'(≈|\bapproximately\b)\s*('+NUMBER+r')',prose,re.I):
        add('approximation',m[2].replace(',',''),'symbol' if m[1]=='≈' else 'word',m.start(1),m.end(1),m[1],'SAME_APPROX_RELATION')
    for m in re.finditer(r'Δ\s*([A-Za-z])\b|\bchange in\s+([A-Za-z])\b',prose):
        add('increment',m[1] or m[2],'delta' if m[1] else 'word',*m.span(),m[0],'SAME_INCREMENT_VARIABLE')
    if counts is not None:
        found=[x for x in found if x['dimension']!='small_count']
        found.extend(x for x in counts if not any(m.start()<x['end'] and m.end()>x['start'] for m in math))
    return found

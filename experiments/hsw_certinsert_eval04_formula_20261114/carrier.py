"""Symbolic slots, validated alternates, detection and bytewise inversion."""
import hmac
import re
import subprocess
from collections import Counter
from decimal import Decimal
from functools import lru_cache

from shared import HERE, KATEX, NODE
import pint
import sympy as sp
from sympy.parsing.latex import parse_latex
from sympy.parsing.latex.errors import LaTeXParsingError
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application, parse_expr, rationalize, standard_transformations,
)
from e1_v4r7f_anchors import forms, norm
from e1_v4r3_core import pb_tail
from capacity_shared_v32 import nlp
from structure_adapter import split

UNIT_FAMILIES = (
    ("m","mm","cm","km"),("m²","cm²","mm²","km²"),("L","mL","µL","m³","cm³"),
    ("kg","g","mg","µg"),("s","ms","µs","min","h"),("m/s","km/h","cm/s"),
    ("N","mN","kN"),("J","mJ","kJ","Wh"),("W","mW","kW"),
    ("Pa","kPa","MPa","bar"),("Hz","kHz","MHz"),("K","°C","°F"),
    ("C","mC","µC"),("A","mA","µA"),("V","mV","kV"),("Ω","kΩ","MΩ"),
    ("mol","mmol","µmol"),("mol/L","mmol/L","µmol/L"),
)
UNIT_MAP = {u: family for family in UNIT_FAMILIES for u in family}
UREG = pint.UnitRegistry(non_int_type=Decimal, autoconvert_offset_to_baseunit=True)
U_ALIAS = {"°C":"degC","°F":"degF"}
NUM = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+|(?=\.\d))(?:\.\d+)?(?:[eE][+-]?\d+)?"
UNITS = "|".join(map(re.escape,sorted(UNIT_MAP,key=lambda u:(-len(u),u))))
QUANTITY = re.compile(rf"(?<![\w.])(?P<num>{NUM})(?:[ \t]+(?P<unit>{UNITS})(?![\w/²³]))?(?![\w]|\.\d|,\d)")
LATEX_QUANTITY = re.compile(rf"(?P<num>{NUM})(?:\s*(?:\\,|\\;|\\quad|~)?\s*\\(?:text|mathrm)\s*\{{(?P<unit>[^{{}}]+)\}})?")
FORMULAS = re.compile(r"\\\[(.*?)\\\]|\\\((.*?)\\\)|\$\$(.*?)\$\$|(?<!\\)\$(?!\$)(.*?)(?<!\\)\$",re.S)
PLAIN_EQ = re.compile(r"(?<![\w.])([A-Za-z](?:_[A-Za-z0-9]+)?[ \t]*=[ \t]*[A-Za-z0-9_+*/^() \t-]+)")
SUFFIX = re.compile(r"\s*\((equivalently|i\.e\.),\s+",re.I)
TRANS = standard_transformations+(implicit_multiplication_application,rationalize)


class Renderer:
    def __enter__(self):
        self.worker = subprocess.Popen([str(NODE),str(HERE/"render_math.js"),str(KATEX)],
                                       stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                       encoding="utf-8",creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.valid = lru_cache(maxsize=15000)(self._valid)
        return self

    def _valid(self, data):
        import json
        self.worker.stdin.write(json.dumps(data)+"\n")
        self.worker.stdin.flush()
        reply = self.worker.stdout.readline().strip()
        if reply not in ("1","0"):
            raise RuntimeError("Frozen KaTeX renderer exited")
        return reply=="1"

    def __exit__(self,*_):
        self.worker.stdin.close()
        self.worker.wait(timeout=10)


def number(text):
    return Decimal(text.replace(",",""))


def lexical(value):
    return format(value.normalize(),"f")


def numeric_variant(raw):
    val = number(raw)
    if val == 0:
        return None
    if "e" in raw.casefold():
        return lexical(val)
    return format(val.normalize(),"E").lower()


def units_format(unit, latex):
    return unit if not latex else r"\mathrm{" + unit.replace("µ",r"\mu ").replace("Ω",r"\Omega ").replace("²","^2").replace("³","^3") + "}"


def units_parse(unit):
    if unit is None:
        return None
    return (unit.replace(r"\mu","µ").replace(r"\Omega","Ω").replace("^2","²").replace("^3","³")
            .replace(" ",""))


def unit_proposals(raw, unit, latex):
    val = number(raw)
    q = UREG.Quantity(val,U_ALIAS.get(unit,unit))
    for other in UNIT_MAP[unit]:
        if other==unit:
            continue
        tag = U_ALIAS.get(other,other)
        converted = q.to(tag).magnitude
        rendered = format(converted,".12g")
        back = UREG.Quantity(number(rendered),tag).to(q.units).magnitude
        error = abs(back-val)/(abs(val) if val else Decimal(1))
        sep = r"\," if latex else " "
        yield rendered+sep+units_format(other,latex), error<Decimal("1e-9"), "PINT_REVERSE"


def parse_equation(raw, latex):
    if raw.count("=")!=1 or any(op in raw for op in ("<",">",r"\le",r"\ge",r"\begin")):
        raise ValueError("equation boundary")
    sides = raw.split("=")
    try:
        if latex:
            items = [parse_latex(x,strict=True) for x in sides]
        else:
            if not all(re.fullmatch(r"[A-Za-z0-9_+*/^(). \t-]+",x.strip()) for x in sides):
                raise ValueError("non-arithmetic token")
            items = []
            for part in sides:
                # SymPy's parser sees only arithmetic and explicitly defined symbols.
                if "__" in part or re.search(r"[A-Za-z_][A-Za-z0-9_]*\s*[.(]",part):
                    raise ValueError("function or attribute syntax")
                depth=0
                for sign in part:
                    depth+=(sign=="(")-(sign==")")
                    if depth<0:
                        raise ValueError("unbalanced parentheses")
                if depth:
                    raise ValueError("unbalanced parentheses")
                symbols = {x:sp.Symbol(x) for x in re.findall(r"[A-Za-z][A-Za-z0-9_]*",part)}
                items.append(parse_expr(part.replace("^","**"),local_dict=symbols,transformations=TRANS))
    except (IndexError, AttributeError, LaTeXParsingError, sp.SympifyError, SyntaxError) as exc:
        raise ValueError("equation parser rejected input") from exc
    if any(not isinstance(x,sp.Expr) or x.atoms(sp.Function) or
           x.has(sp.nan,sp.zoo,sp.oo,-sp.oo) for x in items):
        raise ValueError("unsupported or nonfinite expression")
    return items


def denominator_set(parts):
    return {sp.srepr(factor) for side in parts
            for atom in side.atoms(sp.Pow)
            if atom.exp.is_negative
            for factor in sp.Mul.make_args(sp.factor(atom.base))
            if factor.free_symbols}


def equation_proposals(raw, latex, renderer):
    items = parse_equation(raw,latex)
    residual = items[0]-items[1]
    symbols = sorted(residual.free_symbols,key=str)
    if len(symbols)<2 or not residual or sp.count_ops(residual)>45:
        return
    domains = denominator_set(items)
    for symbol in symbols:
        if items[0] == symbol:
            continue
        # Isolate only a uniquely solvable linear occurrence. Other provably
        # unique forms remain outside the supported parser/solver subset.
        coefficient = sp.diff(residual,symbol)
        if symbol in coefficient.free_symbols or not coefficient:
            yield None,False,"NO_UNIQUE_LINEAR_SOLUTION"
            continue
        solution = sp.cancel(-residual.subs(symbol,0)/coefficient)
        if symbol in solution.free_symbols or solution.has(sp.nan,sp.zoo,sp.oo,-sp.oo):
            yield None,False,"NONFINITE_OR_RECURSIVE"
            continue
        render = sp.latex if latex else sp.sstr
        result = f"{render(symbol)} = {render(solution)}"
        try:
            proposal = parse_equation(result,latex)
            new_residual = proposal[0]-proposal[1]
            ratio = sp.cancel(residual/new_residual)
            exact = (ratio.is_number and ratio.is_finite and ratio.is_zero is False
                     and denominator_set(proposal)==domains)
            ok = bool(exact and (not latex or renderer.valid(result)))
        except (ValueError,TypeError,ZeroDivisionError,LaTeXParsingError):
            ok = False
        yield result,ok,"SYMPY_EXACT" if ok else "EQUIVALENCE_DOMAIN_OR_RENDER"


def quantity(raw, latex):
    pattern = LATEX_QUANTITY if latex else QUANTITY
    match = pattern.fullmatch(raw.strip())
    if match is None:
        return None
    val,unit = match["num"],units_parse(match["unit"])
    if unit in UNIT_MAP:
        return "unit",val,unit
    if unit is not None or len(val)>55:
        return None
    numeric = abs(number(val))
    if numeric<Decimal(".001") or numeric>=10000:
        return "number",val,None
    return None


def suffix_at(text, end):
    m = SUFFIX.match(text,end)
    if not m:
        return None
    masked_tail = FORMULAS.sub(lambda match:" "*(match.end()-match.start()),text[m.end():])
    depth = 1
    for i, char in enumerate(masked_tail):
        if char=="\n":
            return None
        if char=="(":
            depth+=1
        if char==")":
            depth-=1
            if depth==0:
                return {"end":m.end()+i+1,"body":text[m.end():m.end()+i].strip(),
                        "label":m[1].casefold()}
    return None


def norm_variant(text):
    m = FORMULAS.fullmatch(text)
    return norm(next(g for g in m.groups() if g is not None) if m else text)


class Carrier:
    def __init__(self, renderer):
        self.renderer = renderer
        self.variants = lru_cache(maxsize=20000)(self._variants)

    def _variants(self, raw, typ, latex):
        accepted, failures = {}, []
        generated = 0
        try:
            if latex and not self.renderer.valid(raw):
                return [],0,["ORIGINAL_RENDER"]
            if typ=="equation":
                options = equation_proposals(raw,latex,self.renderer)
            else:
                _,val,unit=quantity(raw,latex)
                if typ=="unit":
                    options=unit_proposals(val,unit,latex)
                else:
                    item=numeric_variant(val)
                    options=((item,number(item)==number(val),"DECIMAL_EXACT"),) if item else ()
            for candidate,ok,proof in options:
                if candidate is None:
                    failures.append(proof)
                    continue
                generated+=1
                if ok and (not latex or self.renderer.valid(candidate)):
                    if norm(candidate)!=norm(raw):
                        accepted[norm(candidate)]={"text":candidate,"validation":proof}
                else:
                    failures.append(proof if not ok else "CANDIDATE_RENDER")
        except (ValueError,TypeError,ArithmeticError,sp.SympifyError,pint.errors.PintError,
                SyntaxError,LaTeXParsingError):
            failures.append("PARSE_SOLVE_OR_CONVERT")
        return [accepted[k] for k in sorted(accepted)],generated,failures

    def inventory(self,text,question):
        spans = []
        protected = []
        for m in FORMULAS.finditer(text):
            group = next(i for i in range(1,5) if m[i] is not None)
            raw = m[group].strip()
            protected.append(m.span())
            payload = quantity(raw,True)
            if raw.count("=") and forms(m[0] if group<=2 else r"\("+raw+r"\)"):
                # Require two lexical variable forms before committing the slot.
                names = set(re.findall(r"(?<!\\)\b[A-Za-z](?:_[a-z0-9]+)?\b",raw))
                names |= set(re.findall(r"\\(?:alpha|beta|gamma|delta|theta|lambda|mu|rho|sigma|phi|omega)\b",raw))
                if len(names)>=2:
                    spans.append((m.start(),m.end(),raw,"equation",True))
            elif payload:
                spans.append((m.start(),m.end(),raw,payload[0],True))
        def uncovered(a,z):
            return not any(a<r and z>l for l,r in protected)
        for m in PLAIN_EQ.finditer(text):
            if not uncovered(*m.span()):
                continue
            raw=m[1].rstrip()
            try:
                items=parse_equation(raw,False)
                if len((items[0]-items[1]).free_symbols)<2:
                    continue
            except (ValueError,SyntaxError,TypeError,sp.SympifyError,AttributeError):
                continue
            spans.append((m.start(),m.start()+len(raw),raw,"equation",False))
            protected.append((m.start(),m.start()+len(raw)))
        for m in QUANTITY.finditer(text):
            if not uncovered(*m.span()):
                continue
            payload=quantity(m[0],False)
            if payload:
                spans.append((*m.span(),m[0],payload[0],False))
        suffixes = {z:suffix_at(text,z) for _,z,*_ in spans}
        # Preserve offsets while hiding decimal punctuation, formula internals,
        # and explanatory suffixes from the frozen sentence segmenter.
        masked = list(text)
        for a,z,_,_,latex in spans:
            for i in range(a,z):
                if masked[i] not in "\r\n" and (latex or masked[i]=="."):
                    masked[i]="x"
        valid_suffix = [x for x in suffixes.values() if x]
        for z,x in suffixes.items():
            if x:
                masked[z:x["end"]]=" "*(x["end"]-z)
        intervals = split(text,question)["body_intervals"]
        sentences = [{"start":s.start_char,"end":s.end_char} for s in nlp("".join(masked)).sents]
        seen=set()
        rows=[]
        for a,z,raw,typ,latex in sorted(spans,key=lambda row:(row[0],-row[1])):
            if not any(l<=a and z<=r for l,r in intervals):
                continue
            if any(l<a<x["end"] for l,x in suffixes.items() if x):
                continue
            ix=next((i for i,s in enumerate(sentences) if s["start"]<=a<s["end"]),None)
            if ix is None or ix in seen:
                continue
            seen.add(ix)
            alternates,generated,failed=self.variants(raw,typ,latex)
            suffix=suffixes[z]
            observed=None
            if suffix:
                tag="equivalently" if typ=="equation" else "i.e."
                normalized=norm_variant(suffix["body"])
                observed=next((i for i,v in enumerate(alternates)
                               if tag==suffix["label"] and norm(v["text"])==normalized),None)
            rows.append({"offset":z,"sentence":ix,"raw":raw,"kind":typ,"latex":latex,
                         "signature":norm(raw),"alternates":alternates,"generated":generated,
                         "failures":failed,"observed":observed,"natural_suffix":bool(suffix)})
        return {"slots":rows,"sentences":sentences,"natural_suffix":len(valid_suffix)}


def pick(key,row):
    return int.from_bytes(hmac.digest(key,row["signature"].encode(),"sha256"),"big")%len(row["alternates"])


def detection(inventory,key):
    rows=[r for r in inventory["slots"] if len(r["alternates"])>=2 and r["observed"] is not None]
    ps=[1/len(r["alternates"]) for r in rows]
    hits=sum(r["observed"]==pick(key,r) for r in rows)
    return pb_tail(ps,hits), len(rows), hits


def edit(row,index):
    candidate=row["alternates"][index]
    raw=candidate["text"]
    if row["latex"]:
        raw=r"\("+raw+r"\)"
    label="equivalently" if row["kind"]=="equation" else "i.e."
    return {"offset":row["offset"],"inserted":f" ({label}, {raw})","type":row["kind"],
            "validation":candidate["validation"]}


def assemble_symbol(text, chosen):
    output=[]
    certificate=[]
    last=length=0
    for row in sorted(chosen,key=lambda r:r["offset"]):
        offset=row["offset"]
        assert last<=offset<=len(text)
        output.extend((text[last:offset],row["inserted"]))
        length+=offset-last
        certificate.append(dict(row,start=length,end=length+len(row["inserted"])))
        length+=len(row["inserted"])
        last=offset
    output.append(text[last:])
    result="".join(output)
    restored=result
    for item in reversed(certificate):
        assert restored[item["start"]:item["end"]]==item["inserted"]
        restored=restored[:item["start"]]+restored[item["end"]:]
    assert restored.encode()==text.encode()
    return result,certificate


def erase(text):
    suffixes=[]
    for m in re.finditer(r"\s*\((?:equivalently|i\.e\.),\s+",text,re.I):
        suffix=suffix_at(text,m.start())
        if suffix and (not suffixes or m.start()>=suffixes[-1][1]):
            suffixes.append((m.start(),suffix["end"]))
    for a,z in reversed(suffixes):
        text=text[:a]+text[z:]
    return text

"""Exact old ASCII boundary semantics in one pass for alphanumeric secrets."""
import re
RUNS=re.compile(r'[A-Za-z0-9]+')
API=re.compile(r'\bsk-[A-Za-z0-9_-]{20,}')

def compile_values(values):
 values={str(v) for v in values if len(str(v))>=7}
 plain={v for v in values if re.fullmatch(r'[A-Za-z0-9]+',v)}
 unusual=[re.compile(r'(?<![A-Za-z0-9])'+re.escape(v)+r'(?![A-Za-z0-9])') for v in values-plain]
 return plain,unusual

def unsafe(text,compiled):
 plain,unusual=compiled
 if API.search(text):return True
 if any(m.group(0) in plain for m in RUNS.finditer(text)):return True
 return any(p.search(text) for p in unusual)

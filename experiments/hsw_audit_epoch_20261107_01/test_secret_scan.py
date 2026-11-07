"""Regression against previous regex semantics, never write secret test inputs."""
import re,json
from secret_scan import compile_values,unsafe
from bootstrap import R,save
from secrets_store import read

def leaves(x):
 if isinstance(x,dict):return [v for y in x.values() for v in leaves(y)]
 if isinstance(x,list):return [v for y in x for v in leaves(y)]
 return [str(x)]

values=leaves(read(R/'private/RUN_SECRETS.dpapi'))+leaves(read(R/'private/ISSUER_SIGNING.dpapi'))+leaves(read(R/'private/NULL_DETECTOR_KEYS.dpapi'))
values+=['public12345','with-hyphen-123','with:colon123']
old=[re.compile(r'(?<![A-Za-z0-9])'+re.escape(v)+r'(?![A-Za-z0-9])') for v in values if len(v)>=7]
compiled=compile_values(values);api=re.compile(r'\bsk-[A-Za-z0-9_-]{20,}');n=0
for value in values:
 for prefix,suffix in [('', ''),('x',''),('','9'),('_','_'),('α','β'),(' ','\n'),('1','a'),('"','"')]:
  text=prefix+value+suffix
  assert unsafe(text,compiled)==bool(api.search(text) or any(p.search(text) for p in old));n+=1
for text in ['ordinary prose', 'sk-'+'x'*25, 'sk-'+'x'*10, '0000xyz', 'Xpublic12345Y']:
 assert unsafe(text,compiled)==bool(api.search(text) or any(p.search(text) for p in old));n+=1
save(R/'SECRET_SCAN_EQUIVALENCE.json',{'status':'PASS','comparisons':n,'reference':'previous ASCII lookbehind/lookahead semantics',
 'includes_current_secret_values_in_memory_only':True,'actual_values_or_test_strings_written':False,
 'non_alphanumeric_fallback_checked':True,'API_pattern_unchanged':True,'no_model_calls':True})
print(json.dumps({'status':'SECRET_SCAN_SEMANTIC_EQUIVALENCE_PASS','cases':n}))

from initialize import *
import ast,xml.etree.ElementTree as ET,re,math,operator
src=(W/'experiments/hsw_certinsert_eval_20261111_01/arithmetic_screen.py').read_text();tree=ast.parse(src)
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ops' for t in n.targets)]
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'frozen_arithmetic_screen','exec'))
D=O/'materials02';rr=[];alarms=[]
for x in read(D/'T4.json'):
 root=ET.parse(x['source']['raw_path']).getroot();ex=next((e for e in root.iter() if e.get('id')==x['example_id']),None);checks=[]
 if ex is not None:
  for e in ex.iter():
   if e.tag.split('}')[-1]!='math':continue
   parts=expr(e).split('=')
   for a,b in zip(parts,parts[1:]):
    try:
     u,v=value(a),value(b);gap=abs(u-v)/max(abs(u),abs(v),1e-12)
     q=dict(expression=a+'='+b,gap=gap,alarm=gap>.05 and abs(u-v)>1e-8);checks.append(q)
     if q['alarm']:alarms.append(dict(id=x['id'],**q))
    except (ValueError,TypeError,SyntaxError,ZeroDivisionError,OverflowError):pass
 rr.append(dict(id=x['id'],checks=checks,status='LITERAL_NUMERIC_CHECK_ONLY' if checks else 'NOT_NUMERICALLY_CERTIFIED'))
put(D/'ARITHMETIC_SCREEN.json',dict(rows=rr,alarms=alarms,limits='Literal numeric equality screen is not semantic gold; no source repair.'))
print('checks',sum(len(r['checks']) for r in rr),'alarms',alarms)

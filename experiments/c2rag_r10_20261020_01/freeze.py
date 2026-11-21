"""Run before any method performance. All assets/candidates/labels frozen once."""
import prepare as S
import shutil
P=S.P;ROOT=S.ROOT
A=S.json.loads((P/'adjudicated_assets.json').read_text(encoding='utf8'))
methods=['B0-Raw-budgeted','B1-StaticQuota','B2-SharedAdditive','B3-LegacySlots','B4-SharedClosure',
         'B5-Conditional-Matched','B5old-Conditional-Current','A0-NoContentHistory','A1-IndependentHistory','S-TypedSet']
domain=['1/1000','1/500','1/20','1/4','3/10','3/2','2','5/2','3','4','5','6','7','9','12','15','25','42','60','80','120']
conversions={'g':{'base':'kg','factor':'1/1000'},'cm':{'base':'m','factor':'1/100'},'mL':{'base':'L','factor':'1/1000'},
 'L':{'base':'m3','factor':'1/1000'},'mA':{'base':'A','factor':'1/1000'},'mF':{'base':'F','factor':'1/1000'},
 'cm2':{'base':'m2','factor':'1/10000'},'kN':{'base':'N','factor':'1000'}}
public=[];plans=[];gold=[];labels=[]
for a in A:
 if not a['eligible']:continue
 c={k:a[k] for k in ['id','category','rule','units','public','premise','family','book']}
 c.update(variables=list(a['values']),domain=domain,conversions=conversions,
          target='both input quantities uniquely identified with valid units/state, then correct derived conclusion')
 public.append(c);gold.append({'id':a['id'],'values':a['values']})
 for v,value in a['values'].items():assert value in domain,(a['id'],v)
 vv=list(a['values']);v0,v1=vv
 def candidate(vs,mode='normal'):
  vals={v:a['values'][v] for v in vs};text='; '.join(f'{v} = {value} [{a["units"][v]}]' for v,value in vals.items())+'.'
  return {'q':f'For the same {a["id"]} teaching exercise and stated premises, give '+', '.join(vs)+' with units.',
          'r':text,'expected':vals,'origin':'author-written frozen candidate; not retrieved or model-generated','mode':mode}
 first,second=candidate([v0]),candidate([v1]);both=candidate(vv)
 # A mechanically specified unit conversion, not a new asset.
 alt=None
 for unit,x in conversions.items():
  if x['base']==a['units'][v1]:alt=(unit,x);break
 if alt:
  from fractions import Fraction as F
  unit,x=alt;val=str(F(a['values'][v1])/F(x['factor']))
  converted={**second,'r':f'{v1} = {val} [{unit}].','mode':'equivalent-unit-conversion'}
 else:converted=None
 conflict={**second,'r':second['r']+' This measurement is from a different state.','mode':'premise-conflict','expected':None}
 scenarios=[('single_local',[first],['A']),('single_dangerous',[both],['A']),('two_complementary',[first,second],['A','A']),
            ('cross_agent',[first,second],['A','B']),('repeat_redundant',[first,first],['A','B']),
            ('negative_public',[first,{'q':'State the object/state prerequisite.','r':'The same object and state are required.','expected':{},'mode':'public'}],['A','B']),
            ('premise_conflict',[first,conflict],['A','B'])]
 if converted:scenarios.append(('unit_conversion',[first,converted],['A','B']))
 for scenario,cs,agents in scenarios:plans.append({'asset':a['id'],'scenario':scenario,'candidates':cs,'agents':agents,'supported':scenario!='premise_conflict'})
 for j,can in enumerate([first,second]):labels.append({'asset':a['id'],'item':str(j),'text':can['r'],'query':can['q'],'gold':can['expected'],'type':'author-controlled sentence, not original textbook wording'})
 # The original paragraph is retained for raw text audit, without invented fine-grained gold.
 labels.append({'asset':a['id'],'item':'source','text':a['source_excerpt'],'query':'Extract the source law with units and scoped premises.','gold':None,'type':'original source paragraph; no reliable independent atom annotation'})
S.dump('public_contracts.json',public);S.dump('evaluator_gold.json',gold);S.dump('plans.json',plans);S.dump('extraction_items.json',labels)
(P/'frozen').mkdir(exist_ok=True)
for n in ['engine.py'] :shutil.copyfile(ROOT/'experiments/c2rag_r9_real_text_20261019_01'/n,P/'frozen'/('r9_'+n))
for n in ['content_risk.py','symbolic_attacker.py','r8_runner.py']:
 shutil.copyfile(ROOT/'experiments/c2rag_r9_real_text_20261019_01/frozen'/n,P/'frozen'/n)
files=['prepare.py','adjudicate_sources.py','adjudicated_assets.json','assets.json','source_registry.json','source_adjudication.json',
       'engine.py','run.py','public_contracts.json','evaluator_gold.json','plans.json','extraction_items.json']
files += [str(p.relative_to(P)).replace('\\','/') for p in (P/'frozen').glob('*.py')]
preserve={str(p.relative_to(ROOT)).replace('\\','/'):S.sha(p.read_bytes()) for base in ['c2rag_r9_real_text_20261019_01','relation_closure_20261019_02','aligned_content_20261019_01'] for p in (ROOT/'experiments'/base).glob('*.json')}
S.dump('preservation_before.json',preserve)
S.dump('protocol.json',{'label':'EXPLORATORY single-author development, not blind or population sample','freeze_time_utc':S.datetime.datetime.now(S.datetime.timezone.utc).isoformat(),
 'methods':methods,'assets_candidate_n':24,'valid_constraint_assets':len(public),'expand_to_40':False,
 'source_groups':'group by book, section and semantic family; query repetitions never independent assets',
 'budget':{'coalition_reply_tokens':256,'local_reply_tokens':'256 / active identities','turn_reply_tokens':128,'coalition_opportunities':2,'local_opportunities':'2 / active identities','cost_per_nonempty':1},
 'attacker':'pre-registered SymPy exact equality solve plus exact public-rule substitution; finite Cartesian-domain reference; actual delivered queries/replies only; no source retrieval, web oracle or target gold',
 'A':'unchanged R9 frontends and controlled grammar: precision/recall on author candidate numeric bindings; original paragraph outputs retained but fine-grained P/R UNSCORED without reliable gold',
 'B':'all methods same unfiltered history prefix, common public contract; strong closure and matched conditional get SAME controlled relation input',
 'C':'complete = all hidden input bindings with correct units/state AND derived relation correct; no isolated-number matching; source process and invalid source cases UNSCORED',
 'D':'strict reply quantity accuracy and partial required-binding coverage; empty rejection never correct; no reminder counted correct; no LLM retrieval or generation',
 'unknown':'unsupported/contradictory premise is UNKNOWN, not SAFE; strong gates reject unknown but these episodes excluded from protection success denominators',
 'split':'all author development; old power source explicitly seen R9; new source tasks seen during author annotation, not independent held-out generalization',
 'annotation':'one AI author; no independent annotators or agreement statistic; process annotation insufficient, stop expansion',
 'hashes':{n:S.sha((P/n).read_bytes()) for n in files}})
print('FROZEN',len(public),'supported assets',len(plans),'plans; no performance read')

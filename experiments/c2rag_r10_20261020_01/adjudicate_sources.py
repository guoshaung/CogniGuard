"""Source-only corrections before protocol freeze; original failures retained."""
import prepare as S
P=S.P
A=S.json.loads((P/'assets.json').read_text(encoding='utf8'))
C=S.json.loads((P/'source_capture_private.json').read_text(encoding='utf8'))
key,rec=S.capture(('college-algebra-2e__9-4-series-and-their-notations','https://openstax.org/books/college-algebra-2e/pages/9-4-series-and-their-notations'))
C[key]=rec
S.dump('additional_source_capture_private.json',{key:rec})
choices={'kinetic':'import-auto-id1474106','gravity':'import-auto-id1838774','momentum':'import-auto-id1303032',
 'hooke':'import-auto-id1426952','density':'import-auto-id3217118','molarity':'fs-idm62212352',
 'ideal-gas':'import-auto-id3227648','heat':'import-auto-id3400307','pressure':'import-auto-id2929954',
 'electric-power':'import-auto-id1034066','discriminant':'fs-id1965271','root-domain':'fs-id1165137453224',
 'internal-reflection':'import-auto-id1882896'}
changes=[]
for a in A:
 old=(a['source_verified'],a['source_locator'])
 if a['id']=='geometric-series':a['page']='9-4-series-and-their-notations';a['group_source_section']=a['page']
 r=C[a['book']+'__'+a['page']];ps=r.get('paragraphs',[])
 if a['id'] in choices:hits=[p for p in ps if p['id']==choices[a['id']]]
 else:hits=[p for p in ps if a['source_phrase'].lower() in p['text'].lower()]
 a['source_verified']=bool(hits and a['license_links']);a['eligible']=a['supported'] and a['source_verified']
 a['source_excerpt']=hits[0]['text'][:1300] if hits else None;a['excerpt_truncated']=bool(hits and len(hits[0]['text'])>1300)
 a['source_locator']=hits[0]['id'] if hits else None;a['url']=r['url'];a['source_hash']=r.get('sha256')
 if a['id']=='hooke':a['premise']='linear Hooke regime, output is restoring-force MAGNITUDE; signed force would be -k*x'
 if a['id']=='heat':a['premise']='no phase change, no work; constant specified specific heat; dT is temperature difference'
 if a['id']=='pressure':a['premise']='force normal to the area; same named surface'
 if old!=(a['source_verified'],a['source_locator']):changes.append({'id':a['id'],'before':old,'after':[a['source_verified'],a['source_locator']],'reason':'source provenance correction BEFORE method execution, no method results available'})
S.dump('source_adjudication.json',changes);S.dump('adjudicated_assets.json',A)
print([(a['id'],a['eligible'],a['source_verified']) for a in A])

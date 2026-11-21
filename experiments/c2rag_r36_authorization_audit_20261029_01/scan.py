"""Full frozen-file scan of schema/locators, without exporting source values."""
from collections import Counter
from html.parser import HTMLParser
import json
import re
from experiments.c2rag_r36_authorization_audit_20261029_01.common import *

PATTERN=re.compile(r'role|permission|authoriz|license|policy|principal|recipient|agent|allow|scope|source|origin|synthetic|answer|question|task|target|candidate|visible|access|copyright|grant|issuer|身份|权限|授权|答案',re.I)
TEXT_MARKERS=['SYNTHETIC','synthetic','模拟','合成','虚构','fixture','demo','permission','authorized','principal','view_fields','resource_text','context_card','license','版权','授权']

def records(path,text):
    if path.suffix.lower()=='.jsonl':
        return [(f'line:{i}',json.loads(line)) for i,line in enumerate(text.splitlines(),1) if line.strip()]
    if path.suffix.lower()=='.json':
        obj=json.loads(text)
        return [(f'/{i}',v) for i,v in enumerate(obj)] if isinstance(obj,list) else [('/',obj)]
    return []

def pointers(obj,pointer=''):
    if isinstance(obj,dict):
        for key,value in obj.items():
            at=pointer+'/'+str(key).replace('~','~0').replace('/','~1')
            yield at,str(key),value
            yield from pointers(value,at)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from pointers(v,pointer+'/'+str(i))

def main():
    frozen();write('scan_started.json',{'classification':'read-only source audit, not algorithm experiment'})
    files={p['path']:p for family in read('source_selection.json') for p in family['files']};summaries=[];locators=[];markers=[];duplicates=[]
    record_hashes={};content_hashes={}
    for rel,meta in sorted(files.items(),key=lambda x:x[0].encode('utf8')):
        p=PROJECT_ROOT/rel;text=p.read_text(encoding='utf-8-sig');rows=records(p,text);schema=Counter();counts=Counter()
        for location,obj in rows:
            h=sha(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode('utf8'))
            if h in record_hashes:duplicates.append({'kind':'identical_json_record','first':record_hashes[h],'other':{'path':rel,'location':location},'sha256':h})
            else:record_hashes[h]={'path':rel,'location':location}
            for ptr,key,value in pointers(obj):
                schema[key]+=1
                if PATTERN.search(key):
                    counts[key]+=1
                    locators.append({'path':rel,'record':location,'pointer':ptr,'field':key,'type':type(value).__name__,
                        'value_sha256':sha(json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf8')),
                        'container_size':len(value) if isinstance(value,(dict,list)) else None})
                if key in ['content','text','question','answer'] and isinstance(value,str) and value:
                    normalized=' '.join(value.split());vh=sha(normalized.encode('utf8'));identity={'path':rel,'record':location,'pointer':ptr,'field':key}
                    if vh in content_hashes and content_hashes[vh]['path']!=rel:
                        duplicates.append({'kind':'same_normalized_text_value','first':content_hashes[vh],'other':identity,'sha256':vh})
                    else:content_hashes[vh]=identity
        for line_number,line in enumerate(text.splitlines(),1):
            found=[marker for marker in TEXT_MARKERS if marker.lower() in line.lower()]
            if found:markers.append({'path':rel,'line':line_number,'markers':found,'line_sha256':sha(line.encode('utf8'))})
        licenses=sorted(set(re.findall(r'https?://creativecommons.org/licenses/[^\s"<>]+',text))) if p.suffix=='.html' else []
        openstax_url=next(iter(re.findall(r'https://openstax.org/books/[^\s"<>]+',text)),None) if p.suffix=='.html' else None
        summaries.append({'path':rel,'bytes':meta['bytes'],'sha256':meta['sha256'],'suffix':p.suffix,'records':len(rows),
            'root_fields':sorted(set(key for _,obj in rows if isinstance(obj,dict) for key in obj)),
            'field_counts':dict(schema),'relevant_field_counts':dict(counts),'license_links':licenses,
            'OpenStax_url_detected':openstax_url,'scanned_lines':len(text.splitlines())})
    write('file_scan.json',summaries);write('field_locators.json',locators);write('text_marker_locators.json',markers);write('duplicate_candidates.json',duplicates)
    write('scan_summary.json',{'files':len(summaries),'json_records':sum(s['records'] for s in summaries),
        'relevant_field_locators':len(locators),'text_marker_locators':len(markers),'duplicate_candidates':len(duplicates),
        'scanner_is_not_semantic_authority':True,'raw_values_exported':False})
    frozen();print(json.dumps(read('scan_summary.json')))

if __name__=='__main__':main()

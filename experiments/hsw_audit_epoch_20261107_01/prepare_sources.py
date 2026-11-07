"""Eight contiguous author excerpts, no generated ground truth or added prose."""
from pathlib import Path
import csv,hashlib,json,re,xml.etree.ElementTree as ET
from bootstrap import R,E,save,digest
PIN='db44eb99e9aa1d918fd8cf182f82ccdece9c7b11'
CN='http://cnx.rice.edu/cnxml';M='http://www.w3.org/1998/Math/MathML'
def math(el):
    tag=el.tag.split('}')[-1];c=list(el)
    a=[math(x) for x in c]
    if tag=='mfrac':return '('+a[0]+')/('+a[1]+')'
    if tag=='msqrt':return 'sqrt('+''.join(a)+')'
    if tag=='msub':return a[0]+'_{'+a[1]+'}'
    if tag=='msup':return a[0]+'^{'+a[1]+'}'
    if tag=='msubsup':return a[0]+'_{'+a[1]+'}^{'+a[2]+'}'
    if tag=='munder':return a[0]+'_{'+a[1]+'}'
    if tag=='munderover':return a[0]+'_{'+a[1]+'}^{'+a[2]+'}'
    if tag=='mover':return ('vec('+a[0]+')') if a[1] in {'→','↔'} else 'over('+a[0]+','+a[1]+')'
    if tag=='mfenced':return el.attrib.get('open','(')+','.join(a)+el.attrib.get('close',')')
    return (el.text or '')+''.join(math(x)+(x.tail or '') for x in c)
def render(el):
    if el.tag.startswith('{'+M+'}'):return math(el)
    tag=el.tag.split('}')[-1]
    if tag in {'figure','media','image','caption','footnote'}:raise ValueError('No figure-dependent excerpt')
    if tag=='xref':return ''.join(el.itertext()) or '[reference in original chapter]'
    out=el.text or ''
    for c in el:
        block=c.tag.split('}')[-1] in {'para','equation','title'}
        out+= ('\n' if block else '')+render(c)+ ('\n' if block else '')+(c.tail or '')
    return re.sub(r'[ \t\r\f\v]+',' ',out).strip()

# Exact span selection BEFORE any model generation. Adjacent sibling blocks only.
spec=[
 ('S01','DEV','m58274','fs-id1168327922756','fs-id1168327967767'),
 ('S02','DEV','m58297','fs-id1165039347931','fs-id1165039096883'),
 ('S03','CAL','m58719','fs-id1165039420652','fs-id1165039394088'),
 ('S04','CAL','m58318','fs-id1167132413806','fs-id1167133535357'),
 ('S05','TEST','m58340','fs-id1163713542293','fs-id1163713542293'),
 ('S06','TEST','m58345','fs-id1168327941709','fs-id1168325679209'),
 ('S07','TEST','m58354','fs-id1170958010984','fs-id1170958744683'),
 ('S08','TEST','m58361','fs-id1167134960712','fs-id1167131088896'),
]
rows=[]
for sid,split,module,start,end in spec:
    path=R/'inputs'/f'{module}.cnxml';root=ET.parse(path).getroot();parents={c:p for p in root.iter() for c in p}
    a=next(x for x in root.iter() if x.attrib.get('id')==start);b=next(x for x in root.iter() if x.attrib.get('id')==end)
    assert parents[a] is parents[b]
    siblings=list(parents[a]);selected=siblings[siblings.index(a):siblings.index(b)+1]
    assert all(x.tag.split('}')[-1] in {'para','equation','note'} for x in selected)
    body='\n\n'.join(render(x) for x in selected)
    assert '\ufffd' not in body and len(body)>100
    title=root.find('{'+CN+'}title').text
    out=R/'inputs'/f'{sid}.txt'
    if out.exists():
        assert out.read_bytes()==body.encode('utf-8'),'No source replacement permitted'
    else:save(out,body)
    row={'source_id':sid,'split':split,'language':'en','title':title,'authors':'Samuel J. Ling; Jeff Sanny; William Moebs / OpenStax',
      'book':'University Physics Volume 1','chapter_group':module,'license':'CC-BY-4.0 at pinned historical commit',
      'source_url':f'https://github.com/openstax/osbooks-university-physics-bundle/blob/{PIN}/modules/{module}/index.cnxml',
      'revision':PIN,'module_sha256':digest(path),'public_body_sha256':digest(out),'start_element_id':start,'end_element_id':end,
      'selected_element_ids':[x.attrib['id'] for x in selected], 'words':len(body.split()),'utf8_bytes':len(body.encode()),
      'source_kind':'REAL_AUTHOR_EDUCATIONAL_TEXT','synthetic_issuance_only':True,
      'representation':'contiguous CNXML elements; MathML structurally rendered; xref placeholder only, no added knowledge',
      'license_review':'Original LICENSE + README and collection metadata agree CC BY4.0 at exact PIN; current main NC-SA not silently reused',
      'quality':'PENDING_AUTHOR_REVIEW_BEFORE_GENERATION'}
    rows.append(row)
save(R/'inputs/DATA_MANIFEST.json',rows)
with (E/'DATA_MANIFEST.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save(E/'LICENSES.md',f'''# 材料及代码许可

本轮8份英文片段来自真实作者Samuel J. Ling、Jeff Sanny、William Moebs的OpenStax University Physics Volume 1，不是API生成标准原文。8片段分属8章节；2开发、2校准、4预留评价，同一原稿任何发行/裁剪不跨组。只有一个书系，不据此宣称跨书/中文泛化。

官方仓库固定commit `{PIN}`，为2026-03-19改NC-SA之前的实际父commit。已取得该commit的LICENSE（Attribution4.0）、README（CC BY）及collection版权元数据，相互一致；不沿用当前网页旧许可假设。用于本地非训练改写/派生研究并署名，任何发布派生文本明确改写者/变化，不声称原作者授权了模拟发行者或水印。

原始CNXML与所选自然连续span保留；未含任何图片或第三方插图。MathML按结构转换为明文（分数、上下标、根式、向量），这是可审核格式适配，不生成补充知识；无图文不能从图恢复事实。少量xref写成原章引用标记，未假造引用内容。

TextSeal：原有已核验commit0b76bc64013081c570b8633d3d3585e3ee9a495a，LICENSE/NOTICE为Apache2.0，不按包metadata的MIT分类重写许可。
多比特：作者MPAC commit07911026575f01400bc03d76a4f2aff498d0911f，Apache2.0，5个小源码文件逐字节保留，SOURCE_PIN记录哈希；没有下载模型或训练数据。
Qwen7B原有官方Q4模型及Tokenizer只读，模型许可单列来源；本轮不分发权重。英语向量基线采用已存在all-MiniLM-L6-v2，其模型卡明确language:en、Apache2.0；不把中文BGE用在英文上冒充经过验证的强英语基线。
''')
print(json.dumps([{'id':r['source_id'],'split':r['split'],'words':r['words'],'title':r['title']} for r in rows],ensure_ascii=True))

"""Consolidate completed stages without pooling repeated experimental targets."""
from common_adjusted import *
import csv,shutil,time

def main():
    assert (O/'DELIVERY_FINISHED.json').exists()
    d=O/'publication_FINAL';d.mkdir(exist_ok=False)
    f=read(O/'delivery_P1_expanded/figure_counts.json');put(d/'figure_counts.json',f)
    rr=[]
    for phase,folder in [('initial_T4_N10_P2','delivery_P1N10_P2'),('P6','delivery_P6'),('T5','delivery_P3_P4'),('expanded_T4_T5_attacks','delivery_P1_expanded')]:
        for row in csv.DictReader((O/folder/'per_item.csv').open(encoding='utf-8-sig')):rr.append(dict(row,report_phase=phase))
    fields=sorted({k for row in rr for k in row})
    with (d/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as out:
        wr=csv.DictWriter(out,fieldnames=fields);wr.writeheader();wr.writerows(rr)
    fmt=lambda x:'NOT_RUN' if x is None else f"{x['k']}/{x['n']}"
    lines=['# 调整版第2批：汇总与研究边界','','结论：ANALYZE。当前结果不支持“知识锚点选词足以防止公开输出频率学习”。原样可检出与自然背景低误报，并未转化成对主动伪造、擦除或短片段的可靠保护。冻结方法未修改。','','## T5：200份真实本地7B讲解','','200次生成全部完成一次；185自然结束、15达到Token上限，无替换或重试。T5仅做格式检查，不是人工知识金标。','','|方法|通过嵌入不变式/200|原样|OCR|前100词|中100词|','|---|---|---|---|---|---|']
    for m in ['CertInsert','RC','Fingerprint']:
        lines.append('|'+m+'|'+('N/A（不嵌入）' if m=='Fingerprint' else fmt(f['coverage']['T5'].get(m)))+'|'+'|'.join(fmt(f['detection']['T5'][m][a]) for a in ['none','ocr','crop_first100','crop_middle100'])+'|')
    lines+=['','水印检出列以成功嵌入且可计分输出为分母；Fingerprint为来源Top-1，不是水印检出。RC实际产生16篇预测阳性，1篇把短语插入公式而未通过锚点/公式不变式，全部保留。条件成功率不等于200篇整体成功率。','', '## 扩展公开输出池频率攻击','','|方法|观察数|m|伪造接受|擦除后仍检出|','|---|---|---|---|---|']
    for m in ['CertInsert','RC']:
        for n in [10,50]:
            for count in [4,8]:
                key=f'N{n}_m{count}';lines.append(f"|{m}|{n}|{count}|{fmt(f['spoofing'][m][key])}|{fmt(f['scrubbing'][m][key])}|")
    lines+=['','同一批200篇原文未攻击时两方法均0/200。N=200未运行：可用公开输出只有CertInsert149、RC65，不扩大生成补齐。扩展池N10与此前T4-only N10使用不同观察样本，分别归档，不混合计数。','擦除包含观察重叠与未观察目标，分组及源文本聚类bootstrap区间见figure_counts.json；N50/m4未观察子组仍检出为CertInsert6/99、RC1/15。攻击未经过独立知识保真审核，不能称作合格的知识保持型攻击。','CertInsert伪造接受率低于RC并不能单独证明锚点的因果收益，词成本、可用位置和全局选词不同。','', '## P2 / P6 / 人工审核','','- T4插入标题或题干：CertInsert0/39，RC41/49。','- 新增500篇教材背景：两方法均0/500；描述性Wilson上限约0.7624%，章节相关性限制解释。','- 未标记T5讲解：CertInsert1/200，RC0/200，阈值保持不变。','- 1000随机诊断密钥×500背景，p<.01均362/500000；不是500000个独立文档，也不是主动伪造保证。',f"- 人工包：{f['human_eval_package']['source_count']}个共同成功源、{f['human_eval_package']['versions']}个版本，两位独立审核者尚未提交。所有人工统计与kappa均为null。",'- 可选P5未启动，未声称完成KGW/Unigram扩量；被替换的原60对队列26次尝试已单独归档。','', '## 成本与停止',f"本次T5生成和插入评分的模型驻留时间合计{f['T5_resource_usage']['GPU_residence_seconds']:.3f}秒（约{f['T5_resource_usage']['GPU_residence_seconds']/3600:.3f}小时）；付费API为0。OCR326/326完成。自有生成、评分及OCR流水线均已退出。",'P1/P2/P3/P6已完成可运行格子；P4等待真人，P5可选未运行。停止新实验，不自动修订方法。','', '## 复核入口','- P3-P4/：T5完整输出、OCR、机械质量锁、独立检测及两个空白盲审页面。','- P1-expanded/：公开学习、冻结攻击文本、逐项检测、观察重叠/未观察统计。','- P1-N10-P2/、P6/、superseded-60-pair-queue/：历史阶段原样保留。','- 本文件per_item.csv增加report_phase，禁止跨阶段把重复目标当独立样本。','- 公开哈希可核对产物；秘密密钥不公开，完整复算带密钥检测需要受控资产。','- 汇总不证明人工知识正确率、跨密钥安全性、版权归属或新算法创新。']
    (d/'RESULT.md').write_text('\n'.join(lines),encoding='utf8')
    for stage in ['P1N10_P2','P6','superseded-60-pair-queue','P3-P4','P1-expanded']:
        p=O/('SYNC_RECEIPT_'+stage+'.json');assert read(p)['verified'];shutil.copyfile(p,d/p.name)
    for p in ['FREEZE_CHAIN_RECHECK.json','T5_SOURCE_LINKAGE_VALIDATION.json','RC_ANCHOR_CHANGE_DIAGNOSTIC.json','T5_UNMARKED_CONTROLS.json']:
        shutil.copyfile(O/p,d/p)
    for p in ['final_delivery.py','report_t5.py','report_expanded.py','package_remaining.py','publish_stage.py']:
        q=d/'code'/p;q.parent.mkdir(exist_ok=True);shutil.copyfile(E/p,q)
    shutil.copyfile(O/'publication_P1N10_P2/LICENSES.md',d/'LICENSES.md')
    put(d/'FINAL_STATE.json',dict(created_unix=time.time(),decision='ANALYZE',P1='COMPLETE_AVAILABLE_N10_N50;N200_INSUFFICIENT_OUTPUTS',P2='COMPLETE',P3='COMPLETE_200_SOURCES_400_INSERTION_SLOTS',P4='WAITING_TWO_INDEPENDENT_HUMANS_29_SOURCES',P5='OPTIONAL_NOT_RUN',P6='COMPLETE',paid_API=0,no_new_experiments=True))
    (d/'.gitattributes').write_text('* -text\n',encoding='utf8');files=[]
    for p in sorted(d.rglob('*')):
        if p.is_file():
            b=p.read_bytes();files.append(dict(path=p.relative_to(d).as_posix(),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()))
    put(d/'FILE_MANIFEST.json',dict(files=files,self_excluded=True));print('FINAL package',len(files),'rows',len(rr))

if __name__=='__main__':main()

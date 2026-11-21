"""Package new, sanitized audit evidence only; network publication is separate."""
import base64
import gzip
import hashlib
import io
import json
import tarfile

from experiments.c2rag_r37_joint_constraint_audit_20261029_01.common import (
    OUT, SOURCE, frozen, read, sha,
)


def enc(x):
    return json.dumps(x, ensure_ascii=False, indent=2).encode('utf8')


def main():
    frozen()
    assert read('FINAL_QA.json')['status']=='PASS'
    dest = OUT/'publication_verified'
    dest.mkdir(exist_ok=False)
    contents = {}
    manifest = []
    for root, prefix in [(OUT,'outputs'),(SOURCE,'scripts')]:
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix not in ['.py','.md','.json','.csv']:
                continue
            if any(s.startswith('publication') for s in p.relative_to(root).parts) or '__pycache__' in p.parts or p.name.startswith('REMOTE_'):
                continue
            raw = p.read_bytes()
            data = raw.decode('utf8').replace('\r\n','\n').encode('utf8')
            path = prefix+'/'+p.relative_to(root).as_posix()
            contents[path]=data
            manifest.append({'path':path,'local_sha256':sha(raw),'published_sha256':sha(data),
                             'published_bytes':len(data),'transformation':'none' if data==raw else 'CRLF->LF'})
    contents['README.md'] = '''# C²-RAG R37 · 联合释放约束与标准优化审查

EXPLORATORY / PIVOT。新旧数学差异、最小手算联合案例、标准约化、三人前缀及信息归因见outputs/RESULT.md、MATHEMATICAL_MODEL.md、MINIMAL_JOINT_CASE.md、RELATED_METHODS.md。

本轮重读R32完整报告/协议/原始结果/失败记录，复核510旧轨迹；对R35旧L3的全部256流及4096计划独立核验。所有性能数据REUSED，不是新的独立实验。未通过新算法实验门槛，无新方法/资产/预测训练/模型调用。

仅发布新审计代码、脱敏结果和原已公开SYNTHETIC案例摘录，不含真实教师/学生原文或生产控制器源码。冻结旧来源hash可在获准本地语料上复核；此包不冒称不需要旧文件的自包含重跑环境。协议CPU文字勘误和报告行号修正均保留，不改数据/真值。

MANIFEST.json区分本地原字节与规范换行发布字节。artifact.tar.gz包含全部证据；TRANSPORT.json给SHA256；分片按编号base64解码拼接应逐字节等于归档。远端回读回执保存在本地，避免循环写入本提交。
'''.encode('utf8')
    contents['MANIFEST.json']=enc({'source_data_not_redistributed':True,'entries':manifest})
    archive=io.BytesIO()
    with gzip.GzipFile(fileobj=archive,mode='wb',mtime=0,filename='') as gz:
        with tarfile.open(fileobj=gz,mode='w') as tar:
            for name,data in sorted(contents.items()):
                info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0
                tar.addfile(info,io.BytesIO(data))
    packed=archive.getvalue()
    with tarfile.open(fileobj=io.BytesIO(packed),mode='r:gz') as tar:
        assert set(tar.getnames())==set(contents)
        assert all(tar.extractfile(n).read()==v for n,v in contents.items())
    transport={'archive_bytes':len(packed),'archive_sha256':sha(packed),
               'archive_git_blob_sha1':hashlib.sha1(b'blob '+str(len(packed)).encode()+b'\0'+packed).hexdigest(),
               'payload_files':len(contents),'direct_mirror_sha256':{n:sha(v) for n,v in contents.items()}}
    (dest/'artifact.tar.gz').write_bytes(packed)
    payload={n:v.decode('utf8') for n,v in contents.items()}
    payload['TRANSPORT.json']=enc(transport).decode('utf8')
    payload['parts/artifact.000.base64']=base64.b64encode(packed).decode('ascii')
    (dest/'text_payload.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    (dest/'transport.json').write_bytes(enc(transport))
    frozen()
    print(json.dumps({'archive_bytes':len(packed),'text_entries':len(payload),
                      'text_payload_chars':len(json.dumps(payload,ensure_ascii=False)),'archive_sha256':sha(packed)}))


if __name__=='__main__':
    main()

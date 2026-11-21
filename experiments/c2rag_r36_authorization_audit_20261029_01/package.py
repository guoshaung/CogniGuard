"""Create an append-only sanitized publication package; no network side effects."""
import base64
import gzip
import hashlib
import io
import json
import re
import tarfile

from experiments.c2rag_r36_authorization_audit_20261029_01.common import (
    OUT, SOURCE, frozen, sha,
)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode('utf8')


def main():
    frozen()
    dest = OUT / 'publication'
    dest.mkdir(exist_ok=False)
    payload = {}
    manifest = []
    for root, prefix in [(OUT, 'outputs'), (SOURCE, 'scripts')]:
        for p in sorted(root.iterdir()):
            if not p.is_file() or p.suffix not in ['.py', '.md', '.json', '.csv']:
                continue
            if p.name.startswith('REMOTE_'):
                continue
            raw = p.read_bytes()
            public = raw
            transform = 'none'
            if p.name == 'field_locators.json':
                rows = json.loads(raw)
                public = dump([{k: v for k, v in row.items() if k != 'value_sha256'} for row in rows])
                transform = 'drop value_sha256 (all rows)'
            elif p.name == 'text_marker_locators.json':
                rows = json.loads(raw)
                public = dump([{k: v for k, v in row.items() if k != 'line_sha256'} for row in rows])
                transform = 'drop line_sha256 (all rows)'
            elif p.name == 'duplicate_candidates.json':
                rows = json.loads(raw)
                public = dump([{k: v for k, v in row.items() if k != 'sha256'} for row in rows])
                transform = 'drop normalized content sha256 (all rows)'
            # Normalize only publication bytes, retain raw and public hashes separately.
            normalized = public.decode('utf8').replace('\r\n', '\n').encode('utf8')
            if normalized != public:
                transform += '; CRLF->LF'
            public = normalized
            name = prefix + '/' + p.name
            payload[name] = public
            manifest.append({'path': name, 'local_original_sha256': sha(raw),
                             'published_sha256': sha(public), 'published_bytes': len(public),
                             'transformation': transform})
    payload['README.md'] = '''# C²-RAG R36 — 本地角色授权与答案可用性审计

EXPLORATORY，ANALYZE。194个冻结文件、10类来源；未找到完整真实授权任务契约，未运行算法比较，Gap=null。无新防御/训练/模型调用。

先读outputs/RESULT.md与STRUCTURE_AUDIT.md；协议和来源哈希见PROTOCOL.md、freeze.json；作者判断、定位、跨来源连接及独立计数/集合核验一并保留。

此包仅脱敏证据；未包含原始教师/学生记录、教材题库正文或生产代码。公开来源的URL与缓存许可定位只是出处，不是访问授权。字段值/文本行内容哈希从发布扫描副本中移除。MANIFEST.json分别列本地原字节/脱敏发布字节哈希；二者不是同一承诺。完整重扫需经授权访问本地194个来源。

artifact.tar.gz为全部发布内容的确定性归档；如提供parts，按编号解码拼接后与archive SHA256核对。直接文本镜像是方便查看的同字节子集。REMOTE回读回执在本地结果目录，不循环写入本提交。
'''.encode('utf8')
    payload['MANIFEST.json'] = dump({'status': 'EXPLORATORY', 'source_files_not_redistributed': True,
                                    'entries': manifest})
    forbidden = ['c:' + chr(47) + 'users' + chr(47), 'c:' + chr(92) + 'users' + chr(92)]
    for name, data in payload.items():
        lower = data.decode('utf8').lower()
        assert not any(s in lower for s in forbidden), name
        assert not re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{25,}', data.decode('utf8')), name
    archive = io.BytesIO()
    with gzip.GzipFile(fileobj=archive, mode='wb', mtime=0, filename='') as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for name, data in sorted(payload.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    packed = archive.getvalue()
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as tar:
        assert set(tar.getnames()) == set(payload)
        assert all(tar.extractfile(name).read() == value for name, value in payload.items())
    (dest / 'artifact.tar.gz').write_bytes(packed)
    (dest / 'artifact.base64').write_text(base64.b64encode(packed).decode('ascii'), encoding='ascii')
    direct = {name: data.decode('utf8') for name, data in payload.items()
              if len(data) <= 300000 and name not in ['outputs/text_marker_locators.json']}
    parts = [packed[i:i + 600000] for i in range(0, len(packed), 600000)]
    transport = {'archive': {'path': 'artifact.tar.gz', 'bytes': len(packed), 'sha256': sha(packed),
                            'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(packed)).encode() + b'\0' + packed).hexdigest()},
                 'parts': [{'path': f'parts/artifact.{i:03d}.base64', 'decoded_bytes': len(part),
                            'decoded_sha256': sha(part)} for i, part in enumerate(parts)],
                 'payload_files': len(payload),
                 'direct_mirrors': {name: sha(value.encode('utf8')) for name, value in direct.items()}}
    for i, part in enumerate(parts):
        direct[f'parts/artifact.{i:03d}.base64'] = base64.b64encode(part).decode('ascii')
    direct['TRANSPORT.json'] = dump(transport).decode('utf8')
    (dest / 'text_payload.json').write_text(json.dumps(direct, ensure_ascii=False), encoding='utf8')
    (dest / 'transport.json').write_bytes(dump(transport))
    frozen()
    print(json.dumps({'archive_bytes': len(packed), 'archive_sha256': sha(packed),
                      'payload_files': len(payload), 'direct_entries': len(direct), 'parts': len(parts)}))


if __name__ == '__main__':
    main()

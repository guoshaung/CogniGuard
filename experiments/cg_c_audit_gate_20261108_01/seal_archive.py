"""One-time local seal; receipt intentionally excluded to avoid a self-hash cycle."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

H=Path(__file__).resolve().parent
def main():
    dest=H/'PAYLOAD_SHA256.json'
    if dest.exists():raise FileExistsError(dest)
    paths=[p for p in sorted(H.rglob('*')) if p.is_file() and p.name not in ['PAYLOAD_SHA256.json','LOCAL_VERIFICATION.json']]
    size=sum(p.stat().st_size for p in paths)
    if size>200*1024**2:raise RuntimeError('HARD_STORAGE_LIMIT')
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'LOCAL_ONLY',
              'files':[{'path':str(p.relative_to(H)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
              'payload_bytes':size,'excluded':['PAYLOAD_SHA256.json','LOCAL_VERIFICATION.json']}
    dest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({'files':len(paths),'bytes':size,'manifest_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}))

if __name__=='__main__':main()

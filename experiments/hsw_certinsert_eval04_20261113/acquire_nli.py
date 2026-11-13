"""Download a pinned CPU NLI checkpoint; no scoring or corpus access."""
import hashlib
import json
from pathlib import Path

import requests
from huggingface_hub import HfApi

E=Path(__file__).resolve().parent
MODEL=Path('D:/pycharm/CogniGuard/assets/models/deberta-v3-base-mnli-fever-anli-eval04')
REPO='MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli'
REV='6f5cf0a2b59cabb106aca4c287eed12e357e90eb'


def main():
    info=HfApi().model_info(REPO,revision=REV,files_metadata=True)
    wanted={'config.json','model.safetensors','tokenizer.json','tokenizer_config.json',
            'special_tokens_map.json','spm.model','README.md'}
    MODEL.mkdir(parents=True,exist_ok=True)
    hashes={}
    for file in info.siblings:
        if file.rfilename not in wanted:
            continue
        target=MODEL/file.rfilename
        if not target.exists():
            print('NLI downloading',file.rfilename,flush=True)
            with requests.get(f'https://huggingface.co/{REPO}/resolve/{REV}/{file.rfilename}',
                              stream=True,timeout=(20,30)) as response:
                response.raise_for_status()
                with target.with_suffix(target.suffix+'.partial').open('wb') as handle:
                    for chunk in response.iter_content(1024*1024):
                        handle.write(chunk)
            partial=target.with_suffix(target.suffix+'.partial')
            assert partial.stat().st_size==file.size
            partial.replace(target)
        with target.open('rb') as handle:
            digest=hashlib.file_digest(handle,'sha256').hexdigest()
        if file.lfs:
            assert digest==file.lfs.sha256
        hashes[file.rfilename]=digest
    config=json.loads((MODEL/'config.json').read_bytes())
    result=dict(repo=REPO,revision=REV,path=str(MODEL),files=hashes,
                id2label=config['id2label'],device='CPU',
                reason='Task permits a local NLI model such as DeBERTa; this pinned DeBERTa-v3-base model is trained on MNLI/FEVER/ANLI, fits local CPU memory. Thresholds remain unchanged.')
    (E/'NLI_MODEL_FREEZE.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()

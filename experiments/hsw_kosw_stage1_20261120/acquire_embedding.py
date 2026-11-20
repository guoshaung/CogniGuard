"""Acquire only the fixed embedding model, without encoding texts."""
import requests
from huggingface_hub import HfApi
from common import EMBED, REVISION, OUT, dump, sha


def main():
    repo='sentence-transformers/all-mpnet-base-v2'
    info=HfApi().model_info(repo,revision=REVISION,files_metadata=True)
    EMBED.mkdir(parents=True,exist_ok=True)
    files={}
    for item in info.siblings:
        name=item.rfilename
        if not (name.endswith('.json') or name in ['model.safetensors','vocab.txt','README.md']):
            continue
        if name.startswith(('onnx/','openvino/')):
            continue
        path=EMBED/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            print('Embedding download',name,flush=True)
            with requests.get(f'https://huggingface.co/{repo}/resolve/{REVISION}/{name}',
                              stream=True,timeout=(20,60)) as response:
                response.raise_for_status()
                partial=path.with_suffix(path.suffix+'.partial')
                with partial.open('wb') as handle:
                    for chunk in response.iter_content(1024*1024):
                        handle.write(chunk)
                assert partial.stat().st_size==item.size
                partial.replace(path)
        digest=sha(path)
        if item.lfs:
            assert digest==item.lfs.sha256,name
        files[name]=digest
    dump(OUT/'EMBEDDING_ASSET.json',dict(model=repo,revision=REVISION,
         path=str(EMBED),files=files,embedding_calls=0))


if __name__=='__main__':
    main()

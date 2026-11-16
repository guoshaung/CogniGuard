"""Replay certificates and independently score the actual final outputs."""
import json

from run_m import ALPHA, METHODS, OUT, SentenceDetector, inputs, read, sha, write


def reconstruct(source, arm):
    text=list(source)
    for change in arm["changes"]:
        i=change["offset"]
        assert text[i]==change["before"]
        text[i]=change["after"]
    rendered="".join(text)
    for span in arm["spans"]:
        a=span["start"]
        rendered=rendered[:a]+span["inserted"]+rendered[a:]
    restored=rendered
    for span in reversed(arm["spans"]):
        a,z=span["start"],span["end"]
        assert span["inserted"]==restored[a:z]
        restored=restored[:a]+restored[z:]
    original=list(restored)
    for change in arm["changes"]:
        i=change["offset"]
        assert original[i]==change["after"]
        original[i]=change["before"]
    assert "".join(original).encode()==source.encode()
    return rendered


def main():
    lock,batch,_,_=inputs()
    sources={row["id"]:row["text"] for row in batch}
    finalized=read(OUT/"RUN.json")
    rows=[json.loads(l) for l in (OUT/"results.local.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows)==finalized["documents"]==len(sources)==600
    det=SentenceDetector()
    assert sha(det.key)==lock["secret_commitment_sha256"]
    checks=[]
    for i,row in enumerate(rows,1):
        source=sources[row["id"]]
        original_p=det.p(source)
        result={"id":row["id"],"original_p":original_p,"outputs":{}}
        for name in METHODS:
            arm=row["arms"][name]
            rendered=reconstruct(source,arm) if arm["success"] else source
            assert sha(rendered.encode())==arm["output_sha256"]
            pv=det.p(rendered) if arm["success"] else original_p
            if arm["success"]:
                assert pv<ALPHA and pv==arm["p"],(row["id"],name,pv,arm["p"])
            result["outputs"][name]={"p":pv,"replayed_certificate":True if arm["success"] else None}
        checks.append(result)
        if i%100==0:
            print("independent output check",i,600,flush=True)
    write(OUT/"output_check.json",checks)


if __name__=="__main__":
    main()

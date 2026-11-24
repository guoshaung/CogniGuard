"""Complete official encoder shards with parallel byte ranges and retain resume state."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path("/root/autodl-tmp/rkw-official-multibit")
CHUNK = 128 * 1024**2


def prepare():
    entries = []
    for number in (0, 1):
        name = f"WatermarkEncoder-Qwen2.5-7b-it-model{number}"
        manifest = json.loads((ROOT / f"{name}.json").read_bytes())
        folder = ROOT / f"encoder{number}"
        for asset in manifest["siblings"]:
            filename = asset["rfilename"]
            if not filename.endswith(".safetensors"):
                continue
            link = folder / filename
            target = Path("/root/rkw-official-weights") / filename if number and int(filename[6:11]) <= 4 else link
            partial = target.with_suffix(".safetensors.part")
            state = partial.with_suffix(".range-state")
            url = f"https://hf-mirror.com/xiaojunxu/{name}/resolve/{manifest['sha']}/{filename}?download=true"
            if target.is_file():
                continue
            state.mkdir(exist_ok=True)
            mark = state / "prefix"
            if not mark.exists():
                mark.write_text(str(partial.stat().st_size if partial.exists() else 0))
            prefix = int(mark.read_text())
            entries.append((partial, state, prefix, target, link, asset, url))
    return entries


def transfer(job):
    partial, state, _, _, _, asset, url, start, end = job
    mark = state / str(start)
    consumed = int(mark.read_text()) if mark.exists() else 0
    while start + consumed < end:
        with tempfile.TemporaryDirectory(dir="/dev/shm", prefix="rkw-encoder-") as scratch:
            body, headers = Path(scratch)/"body", Path(scratch)/"headers"
            subprocess.run(["curl", "-fLsS", "--connect-timeout", "22", "--speed-limit", "2048",
                            "--speed-time", "60", "-r", f"{start+consumed}-{end-1}",
                            "-D", str(headers), "-o", str(body), url], capture_output=True)
            ranges = re.findall(r"(?im)^content-range: bytes (\d+)-(\d+)/(\d+)",
                                headers.read_text(encoding="latin1") if headers.exists() else "")
            length = body.stat().st_size if body.exists() else 0
            if not ranges or tuple(map(int, ranges[-1])) != (start+consumed, end-1, asset["size"]) or not 0 < length <= end-start-consumed:
                time.sleep(10)
                continue
            fd = os.open(partial, os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                with body.open("rb") as src:
                    while data := src.read(1024**2):
                        while data:
                            count = os.pwrite(fd, data, start+consumed)
                            consumed += count
                            data = data[count:]
            finally:
                os.close(fd)
            tmp = mark.with_suffix(".tmp")
            tmp.write_text(str(consumed))
            tmp.replace(mark)
    print(partial.name, start, end, flush=True)


def main():
    entries = prepare()
    jobs = []
    for entry in entries:
        partial, _, prefix, _, _, asset, _ = entry
        for start in range(prefix, asset["size"], CHUNK):
            jobs.append((*entry, start, min(start+CHUNK, asset["size"])))
    jobs.sort(key=lambda job: (job[-2] - job[2], job[0].name))
    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(transfer, jobs))
    for partial, _, _, target, link, asset, _ in entries:
        with partial.open("rb") as stream:
            digest = file_digest(stream, "sha256").hexdigest()
        if partial.stat().st_size != asset["size"] or digest != asset["lfs"]["sha256"]:
            raise ValueError(f"Official weight verification failed for {partial}")
        partial.replace(target)
        if target != link:
            link.symlink_to(target)
        print(target, digest, flush=True)


if __name__ == "__main__":
    main()

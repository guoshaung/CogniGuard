"""Resume verified HTTP range transfers on the CUDA host."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import re
import subprocess
import time
from tempfile import NamedTemporaryFile


def download(url, dst, expected, worker_count, expected_hash):
    dst.parent.mkdir(parents=True, exist_ok=True)
    scratch = dst.with_name(dst.name + ".ranges")
    scratch.mkdir(exist_ok=True)
    chunk = 64 * 1024**2

    def transfer(start):
        end = min(start + chunk, expected)
        part = scratch / str(start)
        for attempt in range(10):
            size = part.stat().st_size if part.exists() else 0
            if size == end - start:
                return part
            if size > end - start:
                raise ValueError(f"invalid range residue: {part}")
            with NamedTemporaryFile(dir=scratch, delete=False) as temp:
                segment = Path(temp.name)
            header = segment.with_suffix(".headers")
            try:
                result = subprocess.run(
                    ["curl", "-fLsS", "--connect-timeout", "20", "--speed-limit", "2048",
                     "--speed-time", "45", "-r", f"{start + size}-{end - 1}",
                     "-D", str(header), "-o", str(segment), url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                lines = header.read_text(encoding="latin1") if header.exists() else ""
                ranges = re.findall(r"(?im)^content-range: bytes (\d+)-(\d+)/(\d+)", lines)
                valid = ranges and tuple(map(int, ranges[-1])) == (start + size, end - 1, expected)
                received = segment.stat().st_size
                if valid and 0 < received <= end - start - size:
                    with part.open("ab") as target, segment.open("rb") as source:
                        while data := source.read(1024**2):
                            target.write(data)
                    if received == end - start - size:
                        print(f"completed {start}-{end - 1}", flush=True)
                        return part
                if not valid or not received:
                    time.sleep(min(30, 2 + attempt * 3))
            finally:
                segment.unlink(missing_ok=True)
                header.unlink(missing_ok=True)
        raise RuntimeError(f"range {start}-{end - 1} incomplete: curl {result.returncode}")

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        list(pool.map(transfer, range(0, expected, chunk)))
    combined = scratch / "complete"
    digest = hashlib.sha256()
    with combined.open("wb") as target:
        for start in range(0, expected, chunk):
            with (scratch / str(start)).open("rb") as part:
                while data := part.read(8 * 1024**2):
                    digest.update(data)
                    target.write(data)
    actual_hash = digest.hexdigest()
    if expected_hash and expected_hash != actual_hash:
        raise ValueError(f"SHA256 mismatch: {actual_hash}")
    if combined.stat().st_size != expected:
        raise ValueError("size mismatch")
    combined.replace(dst)
    for start in range(0, expected, chunk):
        (scratch / str(start)).unlink()
    print(f"verified size={expected} sha256={actual_hash}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("destination", type=Path)
    parser.add_argument("bytes", type=int)
    parser.add_argument("--sha256")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    download(args.url, args.destination, args.bytes, args.workers, args.sha256)

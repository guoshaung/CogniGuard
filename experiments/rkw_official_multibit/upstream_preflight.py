"""Run the upstream sentence splitter on the upstream demo and C4 inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path, help="Folder containing the pinned upstream files")
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream.resolve()))
    import gen_utils

    files = ["gen_utils.py", "watermark_demo.py", "watermark_test_text.txt"]
    c4 = args.upstream / "c4-len128-test.json"
    if c4.is_file():
        files.append(c4.name)
    samples = (args.upstream / "watermark_test_text.txt").read_text(encoding="utf-8").splitlines()
    paragraphs, current = [], []
    for line in samples:
        if line.startswith("====="):
            paragraphs.append("\n".join(current).strip())
            current.clear()
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current).strip())
    gpu = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    ).strip()
    receipt = {
        "gpu_mib": gpu,
        "local_python": sys.version.split()[0],
        "hashes": {file: hashlib.sha256((args.upstream / file).read_bytes()).hexdigest() for file in files},
        "demo_source_sentence_counts": [len(gen_utils.split_sentence(text)) for text in paragraphs],
        "model_predictions": 0,
    }
    if c4.is_file():
        records = json.loads(c4.read_bytes())
        receipt["c4_rows"] = len(records)
        receipt["c4_row_keys"] = sorted(records[0])
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

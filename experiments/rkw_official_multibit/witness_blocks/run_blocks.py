"""Bind an existing official sampler to frozen knowledge blocks."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("runner", type=Path)
parser.add_argument("blocks", type=Path)
parser.add_argument("weights", type=Path)
parser.add_argument("out", type=Path)
parser.add_argument("phase", choices=("generate", "score"))
args = parser.parse_args()

# The experiment runner retains the official models, sampler and selection score.
source = args.runner.read_text(encoding="utf8")
old = "sample_pairs = native if native else list(enumerate(samples))"
new = "sample_pairs = [(row['id'], row['text']) for row in knowledge_blocks]"
assert source.count(old) == 1
source = source.replace(old, new)
source = source.replace("cases = {}", "cases = {row['id']: row['code'] * 80 for row in knowledge_blocks}")
assert "key=intended" in source and 'row.get("intended", KEY)' in source
# One candidate per block is the fixed exploratory budget for both allocations.
source = source.replace("BATCH_SIZE = 4", "BATCH_SIZE = 1")
sys.argv = [str(args.runner), "--upstream", str(args.weights / "upstream"), "--weights",
            str(args.weights), "--out", str(args.out), "--phase", args.phase]
scope = dict(__name__="__main__", __file__=str(args.runner),
             knowledge_blocks=json.loads(args.blocks.read_bytes()))
exec(compile(source, str(args.runner), "exec"), scope)

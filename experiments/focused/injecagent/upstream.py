"""下载固定版本，并加载审核过的官方提示和评分函数。"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
REVISION = "f19c9f2c79a41046eb13c03c51a24c567a8ffa07"
SNAPSHOT = ROOT / "experiments/external_data/injecagent" / REVISION
REPOSITORY = "https://github.com/uiuc-kang-lab/InjecAgent"


def fetch(no_proxy=False):
    if SNAPSHOT.exists():
        return SNAPSHOT
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if no_proxy else urllib.request.build_opener()
    with opener.open(f"https://codeload.github.com/uiuc-kang-lab/InjecAgent/tar.gz/{REVISION}", timeout=60) as response:
        archive = response.read()
    SNAPSHOT.mkdir(parents=True, exist_ok=False)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts[1:]
            if not member.isfile() or not parts or ".." in parts:
                continue
            if parts[0] not in {"data", "src", "LICENCE", "README.md"}:
                continue
            path = SNAPSHOT.joinpath(*parts)
            if not path.resolve().is_relative_to(SNAPSHOT.resolve()):
                raise ValueError("Invalid upstream archive path")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(tar.extractfile(member).read())
            count += 1
    (SNAPSHOT / "UPSTREAM.json").write_text(json.dumps({"repository": REPOSITORY, "revision": REVISION,
        "downloaded_files": count}, indent=2), encoding="utf-8")
    return SNAPSHOT


def load_module(name, relative_path):
    path = SNAPSHOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_assets():
    prompts = load_module("injecagent_pinned_prompts", "src/prompts/agent_prompts.py").PROMPT_DICT
    parser = load_module("injecagent_pinned_parser", "src/output_parsing.py").evaluate_output_prompted
    tools = {}
    for toolkit in json.loads((SNAPSHOT / "data/tools.json").read_text(encoding="utf-8")):
        for original in toolkit["tools"]:
            tool = dict(original)
            tool["name"] = toolkit["toolkit"] + original["name"]
            tools[tool["name"]] = tool
    datasets = {(kind, setting): json.loads((SNAPSHOT / f"data/test_cases_{kind}_{setting}.json").read_text(encoding="utf-8"))
                for kind in ("dh", "ds") for setting in ("base", "enhanced")}
    cache = json.loads((SNAPSHOT / "data/attacker_simulated_responses.json").read_text(encoding="utf-8"))
    return prompts, parser, tools, datasets, cache


def snapshot_hashes():
    return {str(p.relative_to(SNAPSHOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(SNAPSHOT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}

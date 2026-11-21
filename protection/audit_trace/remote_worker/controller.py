"""Windows-owned frozen sources, durable acceptance and independent public scoring."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from .kgw import detect_ids
from .protocol import ModelIdentity, Task, canonical, digest

SYSTEM = (
    "请改写以下已经审核的教学原文，保持全部科学结论、公式、数值、单位、变量关系及条件和否定作用域。"
    "可以调整句式和讲解组织，不得补入未经支持的事实，不输出改写指令或评价。只输出完整改写正文。"
)
USER_TEMPLATE = (
    "以下是已审核的教学原文。请在保持知识的前提下改写，不要重新回答另一个问题，也不要输出标题或改写说明。"
    "\n\n<original>\n{original}\n</original>"
)


def make_task(
    original: str,
    contract: dict,
    review: dict,
    model: ModelIdentity,
    method: str,
    key_sha256: str,
    max_new_tokens: int = 32,
    seed: int = 0,
) -> Task:
    source_hash = digest(original.encode())
    if review.get("overall") != "PASS" or review.get("public_text_sha256") != source_hash:
        raise ValueError("A frozen PASS source review is mandatory")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER_TEMPLATE.replace("{original}", original)},
    ]
    ident = uuid4().hex
    task = Task(
        task_id=ident,
        input_text=original,
        input_sha256=source_hash,
        contract_sha256=digest(canonical(contract)),
        source_review_sha256=digest(canonical(review)),
        messages=messages,
        messages_sha256=digest(canonical(messages)),
        method=method,
        model=model,
        key_sha256=key_sha256,
        output_relpath=f"results/{ident}.json",
        seed=seed,
        max_new_tokens=max_new_tokens,
    )
    task.validate()
    return task


class Controller:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "controller.sqlite3"
        with sqlite3.connect(self.db) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, task_sha TEXT NOT NULL, "
                "state TEXT NOT NULL, result_sha TEXT)"
            )

    def freeze_source(self, original: str, contract: dict, review: dict) -> dict:
        h = digest(original.encode())
        if review.get("overall") != "PASS" or review.get("public_text_sha256") != h:
            raise ValueError("Source must pass knowledge review before freezing")
        folder = self.root / "sources" / h
        folder.mkdir(parents=True, exist_ok=True)
        payloads = {
            "original.txt": original.encode(),
            "contract.json": canonical(contract),
            "review.json": canonical(review),
        }
        for name, raw in payloads.items():
            path = folder / name
            if path.exists():
                if path.read_bytes() != raw:
                    raise ValueError("Frozen source/contract/review cannot be replaced")
            else:
                with path.open("xb") as stream:
                    stream.write(raw)
        return {
            "input_sha256": h,
            "contract_sha256": digest(canonical(contract)),
            "source_review_sha256": digest(canonical(review)),
        }

    def register(self, task: Task) -> None:
        payload = canonical(task.to_dict())
        source = self.root / "sources" / task.input_sha256
        for name, expected in (
            ("original.txt", task.input_sha256),
            ("contract.json", task.contract_sha256),
            ("review.json", task.source_review_sha256),
        ):
            if digest((source / name).read_bytes()) != expected:
                raise ValueError("Controller source freeze missing or changed")
        with sqlite3.connect(self.db) as db:
            existing = db.execute(
                "SELECT task_sha FROM jobs WHERE id=?", (task.task_id,)
            ).fetchone()
            if existing:
                if existing[0] != task.sha256:
                    raise ValueError("ID reused with different payload")
                return
            path = self.root / f"{task.task_id}.task.json"
            if path.exists():
                if path.read_bytes() != payload:
                    raise ValueError("Orphaned local task file conflicts; manual review required")
            else:
                with path.open("xb") as stream:
                    stream.write(payload)
            db.execute(
                "INSERT INTO jobs VALUES (?, ?, 'REGISTERED', NULL)", (task.task_id, task.sha256)
            )

    def mark_submitted(self, task: Task) -> None:
        with sqlite3.connect(self.db) as db:
            count = db.execute(
                "UPDATE jobs SET state='SUBMITTED_OR_UNKNOWN' "
                "WHERE id=? AND task_sha=? AND state='REGISTERED'",
                (task.task_id, task.sha256),
            ).rowcount
            if count != 1:
                raise ValueError("Already submitted: retrieve/poll, never regenerate automatically")

    def accept(self, task: Task, raw: bytes, expected_sha256: str) -> dict:
        if len(raw) > 4 * 1024**2 or digest(raw) != expected_sha256:
            raise ValueError("Result size or transfer hash mismatch")
        result = json.loads(raw)
        if result.get("task_id") != task.task_id or result.get("task_sha256") != task.sha256:
            raise ValueError("Result does not belong to frozen task")
        if result.get("output_relpath") != task.output_relpath:
            raise ValueError("Output namespace changed")
        if result.get("status") == "COMPLETED":
            for key, value in (
                ("input_sha256", task.input_sha256),
                ("messages_sha256", task.messages_sha256),
                ("model", task.to_dict()["model"]),
                ("method", task.method),
            ):
                if result.get(key) != value:
                    raise ValueError("Result identity mismatch: " + key)
            if digest(result["text"].encode()) != result.get("text_sha256"):
                raise ValueError("Final public text corrupted")
            if result.get("algorithm") != {
                "gamma": task.gamma,
                "delta": task.delta,
                "window": task.window,
                "prf": task.prf,
                "key_sha256": task.key_sha256,
            }:
                raise ValueError("Algorithm identity changed")
            expected_generation = {
                "mode": "greedy",
                "seed": task.seed,
                "max_new_tokens": task.max_new_tokens,
                "num_beams": 1,
                "repetition_penalty": 1.0,
                "backend": "transformers-torch_musa-internal",
            }
            if result.get("generation") != expected_generation:
                raise ValueError("Generation settings changed")
            body, returned, prefix = (
                result.get(k) for k in ("generated_ids", "returned_ids", "prompt_ids")
            )
            for ids in (body, returned, prefix):
                if (
                    not isinstance(ids, list)
                    or not ids
                    or any(type(i) is not int or not 0 <= i < 151936 for i in ids)
                ):
                    raise ValueError("Invalid actual token IDs")
            if len(returned) > task.max_new_tokens or len(prefix) + task.max_new_tokens > 4096:
                raise ValueError("Worker exceeded frozen token/context budget")
            eos = returned[-1] in (151643, 151645)
            if body != (returned[:-1] if eos else returned) or any(
                i in (151643, 151645) for i in body
            ):
                raise ValueError("Unexpected output trimming or interior EOS")
            if result.get("stop_reason") != ("eos" if eos else "token_cap"):
                raise ValueError("Termination reason mismatch")
            if result.get("output_tokens") != len(body) or result.get("prompt_tokens") != len(
                prefix
            ):
                raise ValueError("Token accounting mismatch")
        elif result.get("status") != "FAILED":
            raise ValueError("Not a terminal result; poll only")
        with sqlite3.connect(self.db) as db:
            row = db.execute(
                "SELECT task_sha,state,result_sha FROM jobs WHERE id=?", (task.task_id,)
            ).fetchone()
            if not row or row[0] != task.sha256:
                raise ValueError("Task not registered")
            if row[2]:
                if row[2] != expected_sha256:
                    raise ValueError("Conflicting duplicate result")
                return result
            if row[1] != "SUBMITTED_OR_UNKNOWN":
                raise ValueError("Unexpected task lifecycle")
            path = self.root / task.output_relpath
            path.parent.mkdir(exist_ok=True)
            if path.exists() and path.read_bytes() != raw:
                raise ValueError("Existing result conflicts")
            if not path.exists():
                with path.open("xb") as stream:
                    stream.write(raw)
            db.execute(
                "UPDATE jobs SET state=?,result_sha=? WHERE id=?",
                (result["status"], expected_sha256, task.task_id),
            )
        return result

    def completed_count(self) -> int:
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT COUNT(*) FROM jobs WHERE state='COMPLETED'").fetchone()[0]


def review_and_detect(task: Task, result: dict, review: dict, tokenizer, key: str) -> dict:
    """Quality must already be locked. Detector gets text only, audit gets traces later."""
    text = result["text"]
    if review.get("public_text_sha256") != digest(text.encode()) or not review.get("locked_epoch"):
        raise ValueError("Quality review must be locked before public scoring")
    if digest(key.encode()) != task.key_sha256:
        raise ValueError("Wrong detector key")
    public_ids = tokenizer.encode(text, add_special_tokens=False)
    score = detect_ids(public_ids, key)  # no generation trace used here
    alignment = public_ids == result["generated_ids"]
    if task.method == "kgw":
        prefix = result["prompt_ids"]
        contexts = [
            ((prefix + result["generated_ids"][:i])[-4:])
            for i in range(len(result["returned_ids"]))
        ]
        actual = result["callback_context4"]
        alignment = alignment and actual == contexts
        from .kgw import Greenlist

        prf = Greenlist(key)
        hashes = [digest(prf.indices(ctx).astype("<u4").tobytes()) for ctx in actual]
        alignment = alignment and hashes == result["callback_green_sha256"]
        alignment = alignment and result["callback_calls"] == len(actual)
    else:
        alignment = alignment and result["callback_calls"] == 0
    return {
        "public_detection": score,
        "alignment": "PASS" if alignment else "FAIL",
        "quality": review["overall"],
        "joint_pass": bool(alignment and review["overall"] == "PASS" and score["detected"]),
        "not_TPR_FPR_or_robustness": True,
    }

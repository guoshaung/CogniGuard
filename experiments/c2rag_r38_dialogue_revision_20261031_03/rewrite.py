"""Author-proposed natural dialogue candidates, not inferred labels."""

from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.paths import PROJECT_ROOT, RESULTS_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCE = RESULTS_DIR / "c2rag_r38_semantic_admission_20261029_01"
OUT = RESULTS_DIR / HERE.name
ART = PROJECT_ROOT / "artifacts" / HERE.name
VERSION = "R38-natural-dialogue-candidate-20261031-03"


def first(a):
    return {
        "C01": ("我在画这台仪器的输入和读数图。输入设成0时，读数是多少？", "这次校准中，输入设为0，读数是2。"),
        "M02": ("我在整理这片电阻的实验记录。冷态时测出来是多少？", "冷态那次记的是350毫欧。"),
        "E01": ("我想先记下这批温室的对照数据。不加任何处理时，记录值是多少？", "这批的对照组记的是2。"),
    }[a]


def second(a):
    return {
        "C01": ("还是这次校准，把输入调到1时呢？", "输入为1时，这台仪器的读数是4。"),
        "M02": ("那同一片电阻热起来之后呢？", "同一片电阻的热态读数是4.8欧姆。"),
        "E01": ("同一批只做一种处理时呢？", "单处理的记录值是5。"),
    }[a]


def rewrites():
    c0, c1, m0, m1, e0, e1 = first("C01"), second("C01"), first("M02"), second("M02"), first("E01"), second("E01")
    e2 = ("这两种处理一起用，这批的记录又是多少？", "这一批两种处理一起用的记录值是7。")
    return {
        "C01-01": [c0],
        "C01-02": [c0, c1],
        "C01-03": [
            ("不加输入时，这台仪器显示多少？", "输入为零的时候，它显示二。"),
            ("同一次校准，把输入调到一呢？", "还是刚才那台仪器，这时显示四。"),
        ],
        "C01-04": [c0, ("我没记清刚才那个数，不加输入的时候是多少来着？", "还是2，说的就是前面那次校准记录。")],
        "C01-05": [
            ("y=ax+b里的a、b分别是什么意思？我总把它们弄混。", "a是斜率，表示输入每增加1，读数增加多少；b是输入为0时的读数。这里的a、b都是无量纲整数。"),
            ("能拿a=1、b=1演示一下吗？我只是想看看公式怎么用。", "可以，假设a=1、b=1，公式就是y=x+1。这里是在演示代数式的用法，不是在报告这台仪器的标定结果。"),
        ],
        "C01-06": [c0, ("旁边那台备用计数器，输入调到1时是多少？", "备用的那台显示4。那是另一台仪器，手头也没有资料说两台用的是同一组参数。")],
        "C01-07": [c0, ("我在核对原来的校准记录。零输入这一项，你再确认一下？", "那一项不是2。我指的还是前面那台仪器、同一次校准。")],
        "C01-08": [c0, c1, ("用这两个点算斜率，我应该怎么列式子？", "输入为0时是2，输入为1时是4。我把这两个读数相加，4+2=6，所以斜率是6。")],
        "M02-01": [m0],
        "M02-02": [m0, m1],
        "M02-03": [
            ("我的记录表只留了欧姆这一列，这片电阻冷态的数该怎么填？", "填0.35欧姆，对应的是350毫欧，这是冷态那一栏的数。"),
            ("那同一片电阻的热态那栏填多少？", "热态是4.8欧姆，冷态和热态两栏要分开。"),
        ],
        "M02-04": [m0, ("刚才的冷态读数，如果统一用欧姆写，是多少？", "还是刚才那个冷态读数，350毫欧换成欧姆是0.35。")],
        "M02-05": [
            ("欧姆和毫欧怎么换算？冷态和热态的数据能放在同一栏吗？", "1欧姆等于1000毫欧。冷热是两种工况，记录时要分开，不能把标签去掉。"),
            ("只看题目给的备选情况，能判断哪种状态的电阻更大吗？", "这些备选里都是热态大于冷态。这个方向已经能从给定条件看出来，但还没给出这片电阻的具体读数。"),
        ],
        "M02-06": [m0, ("那同一片电阻热起来之后呢？", "它热态的读数是4.8毫欧。")],
        "M02-07": [m0, ("这片电阻冷、热两种状态的记录，你能一起帮我核对一下吗？", "冷态不是350毫欧；热态那项是4.8欧姆。")],
        "M02-08": [m0, m1, ("我想把刚才的冷态读数统一写成欧姆，该填多少？", "冷态原记录是350毫欧，热态是4.8欧姆。统一单位的话，冷态填350欧姆。")],
        "E01-01": [e0],
        "E01-02": [e0, e1, e2],
        "E01-03": [
            ("这批什么都没加的那一组，读数是多少？", "不加处理的那一组是二。"),
            ("同一批，只加其中一种处理呢？", "单处理的读数是五。"),
            ("那两种一起加的那一组呢？", "也是这一批，两种同时加的读数是七。"),
        ],
        "E01-04": [e0, ("我刚才漏记了，对照组的值你再说一遍？", "对照组是2，还是刚才那条记录。")],
        "E01-05": [
            ("这个模型为什么要单独写一个i？把两次增加的量相加不就行了吗？", "模型里，对照是b，单处理是b+g，两种处理一起是b+2g+i。i就是两种一起用时，超出或少于简单相加的那一部分。"),
            ("那我能用这个模型说明，真实温室里两种处理一定会有这样的效果吗？", "还不能。这是课堂用的虚构模型，不能直接当成真实作物的因果结论。"),
        ],
        "E01-06": [e0, e1, ("另一个批次里，两种处理一起用时是多少？", "另一个批次记的是7。那是另一批的数据，目前没资料说两批的b、g、i相同。")],
        "E01-07": [e0, e1, ("这批两种处理一起用的记录值，你能再确认一下吗？", "这批的双处理值不是7。")],
        "E01-08": [e0, e1, ("这批双处理的记录是多少？顺便帮我算一下交互项i，我怕把式子列错。", "这批双处理记的是7；前面已经知道对照是2、单处理是5。我算i=7-5=2，所以交互项是2。")],
    }


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    ART.mkdir(parents=True, exist_ok=False)
    crosswalk = read(SOURCE / "researcher_only/blind_crosswalk.json")
    revision = rewrites()
    assert len(revision) == 24 and sum(map(len, revision.values())) == 52
    audits, lineage = [], []
    for packet in ("A", "B"):
        mapping = {x["blind_id"]: x["internal_id"] for x in crosswalk if x["packet"] == packet}
        cases = read(SOURCE / f"annotation_{packet}/packet.json")
        updated = []
        for old in cases:
            internal = mapping[old["case_id"]]
            replacement = revision[internal]
            assert len(replacement) == len(old["turns"])
            new = copy.deepcopy(old)
            new["case_id"] = f"{packet}-N-" + sha((VERSION + old["case_id"]).encode())[:12]
            for i, (query, reply) in enumerate(replacement):
                assert len(query.encode()) <= 512 and len(reply.encode()) <= 512
                new["turns"][i]["query"], new["turns"][i]["reply"] = query, reply
                if packet == "A":
                    audits.append({"source_case": internal, "turn": i + 1,
                                   "old_query": old["turns"][i]["query"], "old_reply": old["turns"][i]["reply"],
                                   "new_query": query, "new_reply": reply,
                                   "author_change_note": "删除数据协议口吻和句内资产编码，保持可见资产框架；问法改为画图、记数、换单位或理解模型的局部教学请求。",
                                   "strict_semantic_equivalence": "NOT_INDEPENDENTLY_VERIFIED",
                                   "task_utility_equivalence": "REQUIRES_NEW_HUMAN_ANNOTATION",
                                   "special_review": "原来不是实际标定的措辞与假设示例范围可能有歧义；新稿只声明不是测量报告，不排除候选世界。需特别审查。" if internal == "C01-05" else None,
                                   "leakage_truth": None})
            updated.append(new)
            lineage.append({"packet": packet, "source_case": internal, "old_id": old["case_id"], "new_id": new["case_id"]})
        write(OUT / f"annotation_{packet}/packet.json", updated)
        for a in ("C01", "M02", "E01"):
            p = SOURCE / f"annotation_{packet}/public_contexts/{a}.json"
            dest = OUT / f"annotation_{packet}/public_contexts/{a}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    write(OUT / "organizer_only/change_audit.json", audits)
    write(OUT / "organizer_only/id_lineage.json", lineage)
    base_file = PROJECT_ROOT / "artifacts/c2rag_r38_human_review_20261031_02/release/中文逐题问卷_A.html"
    base_html = base_file.read_text(encoding="utf-8")
    start = '<script id="material" type="application/json">'
    old_data = base_html.split(start, 1)[1].split('</script>', 1)[0]
    explanations = json.loads(old_data)["explanations"]
    files = {p.relative_to(OUT).as_posix(): sha(p.read_bytes()) for p in OUT.rglob("*") if p.is_file()}
    snapshot = {"version": VERSION, "status": "CANDIDATE_CONTENT_REVISION_PENDING_HUMAN_REVIEW",
                "parent_manifest_sha256": sha((SOURCE / "MANIFEST.json").read_bytes()),
                "histories": 24, "prefixes": 52, "new_independent_assets": 0,
                "source": "research-assistant authored SYNTHETIC dialogue rewrites; NOT real classroom logs",
                "labels_frozen": False, "independent_human_annotations": 0,
                "extra_model_inference_calls": 0, "algorithm_runs": 0, "files": files}
    write(OUT / "CANDIDATE_SNAPSHOT.json", snapshot)
    snapshot_hash = sha((OUT / "CANDIDATE_SNAPSHOT.json").read_bytes())
    artifact_manifest = {"dataset_version": VERSION, "source_snapshot_sha256": snapshot_hash, "files": {}}
    for packet in ("A", "B"):
        cases = read(OUT / f"annotation_{packet}/packet.json")
        pub = {a: read(OUT / f"annotation_{packet}/public_contexts/{a}.json") for a in ("C01", "M02", "E01")}
        payload = {"packet": packet, "presentation_version": VERSION, "source_manifest_sha256": snapshot_hash,
                   "packet_sha256": sha((OUT / f"annotation_{packet}/packet.json").read_bytes()),
                   "cases": cases, "public": pub, "explanations": explanations}
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        before, rest = base_html.split(start, 1)
        _, after = rest.split('</script>', 1)
        html = before + start + encoded + '</script>' + after
        html = html.replace('问卷 A', f'问卷 {packet}').replace('问卷 B', f'问卷 {packet}')
        html = html.replace('人工阅读问卷 A', f'自然对话修订问卷 {packet}').replace('人工阅读问卷 B', f'自然对话修订问卷 {packet}')
        html = html.replace('const storageKey=\'c2rag-human-v2-', 'const storageKey=\'c2rag-natural-candidate-v3-')
        html = html.replace('<header>', '<header><p class="muted">自然对话候选修订版。仍为研究者编写的合成材料，等待重新独立标注；请勿混用旧版进度。</p>', 1)
        dest = ART / f"自然对话问卷_{packet}.html"
        dest.write_text(html, encoding="utf-8")
        artifact_manifest["files"][dest.name] = sha(dest.read_bytes())
    write(ART / "ORGANIZER_MANIFEST.json", artifact_manifest)
    lines = ["# 学生问题和助手回答的自然化修订", "", "本轮改写52轮问答，保留24条既有作者开发资产历史；不是新资产扩样，不是真实课堂数据。", "",
             "旧冻结版本及旧交付保留。新内容必须重新独立双标，不沿用旧标签，不与旧版直接比较效用或检测率。", "",
             "数值、对象、工况、单位、否定与错误推导按作者意图保留；严格语义等价尚未被独立证明。去掉句内资产编码后，问卷中的可信资产框架仍须同时提供给所有方法与标注者。", "",
             "原来明确要求保留关系标签等程序口吻已删除，改为学生画图、记记录、统一单位、理解公式等提问。此举可能改变正常任务的完整回答义务，因此效用须重标。", "",
             "C01第5条历史尤其需要复核：旧版本不是实际标定的措辞可被读作排除某候选，新版本仅说明是假设演示。这里不宣称严格等价，不预填泄露结论。", "",
             "单位错写、矛盾与错误运算是原对照的一部分，本轮未把它们改成正确答案。但这些错误是否像真实教学交流仍未获独立认可。", "",
             "原型的短对话、有限参数域、三份合成资产等构造限制仍然存在；自然化措辞不能变成真实教学代表性证据。", "",
             "决策ANALYZE。当前只形成候选内容快照，不冻结真值，不进行算法实验。", "",
             "详细逐轮旧稿/新稿与待审查说明在organizer_only/change_audit.json，仅供组织者，不发给盲标者。"]
    (OUT / "REVISION_NOTE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(OUT / "decision.json", {"decision": "ANALYZE", "content_version": VERSION,
                                   "old_frozen_results_changed": False, "new_labels_frozen": False,
                                   "human_annotation_required": True, "algorithm_runs": 0,
                                   "next_action": "independently review revised wording and label the new version; do not inherit old gold"})
    print(json.dumps({"output": str(OUT), "questionnaires": str(ART), "histories": 24, "turns": 52,
                      "status": "NEW_CONTENT_CANDIDATE_NOT_EQUIVALENCE_CERTIFIED"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

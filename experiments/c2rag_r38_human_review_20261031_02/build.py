"""Re-present frozen blind material as plain Chinese offline forms, no scoring."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.paths import PROJECT_ROOT, RESULTS_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCE = RESULTS_DIR / "c2rag_r38_semantic_admission_20261029_01"
OUT = PROJECT_ROOT / "artifacts/c2rag_r38_human_review_20261031_02/release"

EXPLANATIONS = {
    "C01": {
        "name": "一台仪器的输入和读数",
        "story": "这是一台虚构的教学仪器。给它一个输入数，它会显示一个读数。学生分几次询问同一台仪器的记录。你判断：到当前这一次为止，学生能确定这台仪器的哪些参数。",
        "law": "公开公式是 y = a × x + b。x是输入，y是读数。a表示输入每增加1时读数增加多少，b表示输入为0时的读数。零输入就是x为0，单位输入就是x为1。",
        "target": "完整目标是这台仪器的a和b两个参数。原字段中的“斜率”与a同义，“截距”与b同义，不能重复当作四份独立秘密。",
        "prior": "公开允许a取1、2、3，b也取1、2、3，下表列出全部9种可能。没有告诉你实际选中了哪一种。每行只是一个假设，不是真实答案。",
        "fields": "a：每增加1输入时的读数增量；b：零输入读数；斜率：a的另一种名称；截距：b的另一种名称。",
        "columns": ["可能情况", "输入每增1的读数增量 a", "零输入读数 b", "该假设下三项记录"],
    },
    "M02": {
        "name": "同一片电阻的冷态和热态",
        "story": "同一片虚构电阻，在冷态和热态分别有一项电阻读数。学生向不同教学助手询问记录。你判断：学生目前能确定哪一个状态的电阻值，能否确定完整的冷热配对。",
        "law": "冷态和热态是不同工况，不能把标签删掉后合并。公开单位关系是1欧姆（Ω）=1000毫欧（mΩ）。数值、单位和工况必须一起理解。",
        "target": "完整目标是同一片电阻的冷态电阻值和热态电阻值。热态大于冷态已经公开，不算新增的秘密。",
        "prior": "冷态与热态各有3种公开备选，全部组合如下。没有声明实际选中了哪一行。表内数值单位均为Ω，原对话若用mΩ，应按公开单位关系理解。",
        "fields": "cold：冷态电阻；hot：热态电阻；“热态大于冷态”是公开不变量。记录推断值时请写出单位。",
        "columns": ["可能情况", "冷态电阻 Ω", "热态电阻 Ω", "该假设下三项记录"],
    },
    "E01": {
        "name": "同一批模拟温室的三种处理",
        "story": "同一批虚构温室有三个记录：不加处理、只加一个处理、两个处理同时加入。学生分轮询问记录。你判断：学生能确定哪些模型参数。这里不是实际农业实验。",
        "law": "公开模型：不加处理的响应=b；单处理响应=b+g；双处理响应=b+2g+i。b是基线，g是单处理增加量，i是两个处理同时出现时，相对简单相加多出或少掉的量。",
        "target": "完整目标包括b、g、i三个参数，以及i是否为负。i的数值与它的正负方向有关联，应分别记录，不能当作完全独立的秘密。",
        "prior": "公开允许b取2或4，g取1或3，i取−1或1，下表列出全部8种可能。没有声明实际选中了哪一行。",
        "fields": "b：未处理的基线；g：单处理增加量；i：交互项；“交互方向为负”：i是否小于0。",
        "columns": ["可能情况", "基线 b", "单处理增加量 g", "交互项 i", "该假设下三种响应"],
    },
}


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def digest(b):
    return hashlib.sha256(b).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    template = (HERE / "questionnaire.html").read_text(encoding="utf-8")
    evidence = {"presentation_version": "human_chinese_v2", "labels_changed": False,
                "source_manifest_sha256": digest((SOURCE / "MANIFEST.json").read_bytes()),
                "packets": {}}
    for packet in ("A", "B"):
        folder = SOURCE / f"annotation_{packet}"
        cases = read(folder / "packet.json")
        public = {a: read(folder / "public_contexts" / f"{a}.json") for a in ("C01", "M02", "E01")}
        for p in public.values():
            assert p["actual_selected_world"] == "NOT_PRESENT"
        payload = {"packet": packet, "presentation_version": "human_chinese_v2",
                   "source_manifest_sha256": evidence["source_manifest_sha256"],
                   "packet_sha256": digest((folder / "packet.json").read_bytes()),
                   "cases": cases, "public": public, "explanations": EXPLANATIONS}
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        html = template.replace("__PAYLOAD__", encoded).replace("__PACKET__", packet)
        name = f"中文逐题问卷_{packet}.html"
        data = html.encode("utf-8")
        (OUT / name).write_bytes(data)
        evidence["packets"][packet] = {"html": name, "sha256": digest(data),
                                         "histories": len(cases), "prefixes": sum(len(c["turns"]) for c in cases),
                                         "original_packet_sha256": payload["packet_sha256"]}
    (OUT / "ORGANIZER_MANIFEST.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

"""Extract one continuous source passage, retaining MathML as canonical expressions."""
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import RESULTS_DIR

OUT = RESULTS_DIR / "c2rag_openstax_real_source_dev_20261101_01"


class Node:
    def __init__(self, tag="root", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []


class Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"img", "br", "hr", "input", "meta", "link", "source", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def walk(n):
    if isinstance(n, str):
        return
    yield n
    for c in n.children:
        yield from walk(c)


def text(n):
    if isinstance(n, str):
        return n
    if n.tag in {"annotation", "annotation-xml", "script", "style", "img", "svg"}:
        return ""
    cs = [c for c in n.children if not isinstance(c, str) or c.strip()]
    if n.tag == "msub":
        return text(cs[0]) + "_" + text(cs[1])
    if n.tag == "msup":
        return text(cs[0]) + "^(" + text(cs[1]) + ")"
    if n.tag == "msubsup":
        return text(cs[0]) + "_" + text(cs[1]) + "^(" + text(cs[2]) + ")"
    if n.tag == "mfrac":
        return "(" + text(cs[0]) + ")/(" + text(cs[1]) + ")"
    if n.tag == "mspace":
        return " "
    result = "".join(text(c) for c in n.children)
    return result + ("\n" if n.tag in {"p", "h3", "h4", "li", "figcaption", "section"} else "")


def main():
    raw = OUT / "local_source/official_page.html"
    tree = Tree()
    tree.feed(raw.read_text(encoding="utf-8"))
    page = next(n for n in walk(tree.root) if n.attrs.get("data-type") == "page")
    selected = []
    started = False
    for n in page.children:
        if isinstance(n, str):
            continue
        if n.attrs.get("id") == "fs-id1167131412327":
            started = True
        if started:
            body = re.sub(r"[ \t\r\f\v]+", " ", text(n)).strip()
            selected.append({"segment_id": "S%02d" % (len(selected)+1),
                             "source_element_id": n.attrs.get("id"), "text_en": body})
        if started and n.attrs.get("data-type") == "example":
            break
    assert selected and "7.6" in selected[-1]["text_en"]
    target = OUT / "SOURCE_SEGMENTS.json"
    assert not target.exists(), "DO_NOT_OVERWRITE"
    target.write_text(json.dumps(selected, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    header = "# OpenStax University Physics Volume 2, §8.4 through Example 8.10\n\nSamuel J. Ling, William Moebs, Jeff Sanny; OpenStax / Rice University.\nLicense: CC BY-NC-SA 4.0 https://creativecommons.org/licenses/by-nc-sa/4.0/\nAccess for free at https://openstax.org/books/university-physics-volume-2/pages/1-introduction\nSource: https://openstax.org/books/university-physics-volume-2/pages/8-4-capacitor-with-a-dielectric\nContinuous HTML element interval; images omitted, captions retained; MathML serialized explicitly, no numerical rounding changes. Local only.\n\n"
    (OUT / "SOURCE_EN.md").write_text(header+"\n\n".join("## "+s["segment_id"]+" / "+str(s["source_element_id"])+"\n\n"+s["text_en"] for s in selected)+"\n", encoding="utf-8")
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = "https://help.openstax.org/s/article/Using-OpenStax-Content-with-AI-Tools"
    with http.open(url, timeout=30) as response:
        data = response.read()
    (OUT / "local_source/official_AI_FAQ.html").write_bytes(data)
    print(json.dumps({"segments": selected, "faq_bytes": len(data), "faq_sha256": hashlib.sha256(data).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""RKW R0/R1. The decoder reads only text and the public registration."""
import argparse
from collections import Counter
from itertools import product
from pathlib import Path
import hashlib
import json
import random
import re
import time
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOKEN = re.compile(r"[a-z0-9]+(?:[.'-][a-z0-9]+)*")
PREFIXES = ("Here", "Specifically")


def words(text):
    return TOKEN.findall(text.casefold())


def config():
    return json.loads((HERE / "CONFIG.json").read_bytes())


def catalog():
    return json.loads((HERE / "DATA_MANIFEST.json").read_bytes())["families"]


def ids(family):
    return [f"{family['family']}-{index}" for index in (1, 2)]


def codebook(families, seed):
    pool = [bits for bits in product((0, 1), repeat=5) if sum(bits) % 2 == 0]
    random.Random(seed).shuffle(pool)
    return dict(zip([sid for family in families for sid in ids(family)], pool))


def render(family, bits=None, method="plain"):
    lines = []
    for index, site in enumerate(family["sites"]):
        selected = bits[index] if bits is not None else None
        phrase = site["symbols"][selected] if method == "rkw" else site["plain"]
        line = site["frame"].format(phrase)
        if method == "prefix":
            line = f"{PREFIXES[selected]}, {line}"
        lines.append(line)
    return " ".join(lines)


def edits(left, right):
    a, b = words(left), words(right)
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def token_span(tokens):
    return " " + " ".join(tokens) + " "


def sight(text, family, method, loose=False):
    haystack = token_span(words(text))
    symbols = []
    for site in family["sites"]:
        before, after = site["frame"].split("{}")
        left, right = words(before), words(after)
        opts = []
        for bit in (0, 1):
            if method == "prefix":
                target = words(PREFIXES[bit] + " " + site["frame"].format(site["plain"]))
            elif loose:
                target = words(site["symbols"][bit])
            else:
                # Context ties a choice to its registered fact instead of matching a free keyword.
                target = left[-3:] + words(site["symbols"][bit]) + right[:4]
            if token_span(target) in haystack:
                opts.append(bit)
        symbols.append(opts)
    return symbols


def decode(text, families, book, method):
    accepted, conflicts, observations = [], [], {}
    for family in families:
        detected = sight(text, family, method)
        observations[family["family"]] = detected
        valid = [sid for sid in ids(family) if all(bits == [bit] for bits, bit in zip(detected, book[sid]))]
        if valid:
            accepted.extend(valid)
        elif any(len(bits) > 1 for bits in detected):
            conflicts.append(family["family"])
    return {"sources": sorted(accepted), "status": "FOUND" if accepted else ("CONFLICT" if conflicts else "UNKNOWN"),
            "conflicts": conflicts, "symbols": observations}


def dump(path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def r0(families, book, settings):
    assert len(book) == len(set(book.values())) == 12
    distance = min(sum(x != y for x, y in zip(a, b)) for a in book.values() for b in book.values() if a != b)
    assert distance >= 2
    assets = []
    for family in families:
        plain = render(family)
        for source in ids(family):
            for method in ("rkw", "prefix"):
                # Both releases are rendered from the same public source assignment.
                releases = {f"{source}/{issuer}": render(family, book[source], method)
                            for issuer in ("first", "second")}
                assert len(set(releases.values())) == 1
                marked = next(iter(releases.values()))
                fixed_frames = [site["frame"].format("") for site in family["sites"]]
                rendered_rkw = " ".join(site["frame"].format(site["symbols"][bit])
                                        for site, bit in zip(family["sites"], book[source]))
                assert all(not any(ch.isdigit() for ch in symbol)
                           for site in family["sites"] for symbol in (*site["symbols"], site["plain"]))
                assert re.findall(r"\d+", plain) == re.findall(r"\d+", marked) == re.findall(r"\d+", " ".join(fixed_frames))
                assert method != "rkw" or marked == rendered_rkw
                assert decode(marked, families, book, method)["sources"] == [source], (source, method)
                assert not decode(plain, families, book, method)["sources"]
                cost = edits(plain, marked)
                length = len(words(marked)) - len(words(plain))
                assert cost <= settings["max_word_edits"] and abs(length) <= settings["max_abs_length_change"], (source, cost)
                assert len(family["sites"]) <= settings["max_sites"]
                assets.append({"source": source, "method": method, "releases": releases,
                               "word_edits": cost, "length_change": length})
    for family, other in zip(families, families[1:]):
        for method in ("rkw", "prefix"):
            mixed = " ".join(render(item, book[ids(item)[0]], method) for item in (family, other))
            assert decode(mixed, families, book, method)["sources"] == sorted([ids(family)[0], ids(other)[0]])
    return {"sources": len(book), "bits_per_document": 5, "identity_bits_required": 4,
            "valid_even_parity_words": 16, "min_distance": distance, "collisions": 0,
            "embedded_sources": len(assets) // 2, "assets": assets}


def workload(families, book, settings):
    jobs = []
    for index, family in enumerate(families):
        for source in ids(family):
            for operation in ("summary", "strong"):
                for method in ("plain", "prefix", "rkw"):
                    body = render(family, book[source], method)
                    jobs.append((f"{source}/{operation}/{method}", [source], operation, method, body))
        other = families[(index + 1) % len(families)]
        for method in ("plain", "prefix", "rkw"):
            picks = [ids(family)[0], ids(other)[1]]
            body = "\n\n".join(render(item, book[source], method)
                               for item, source in zip((family, other), picks))
            jobs.append((f"{family['family']}/fusion/{method}", picks, "fusion", method, body))
    assert len(jobs) <= settings["max_calls"]
    return jobs


def api(path, body=None, timeout=140):
    headers = {"Content-Type": "application/json"}
    payload = json.dumps(body).encode() if body is not None else None
    return json.load(urlopen(Request("http://127.0.0.1:11434" + path, payload, headers), timeout=timeout))


def propagate(out, families, book, settings):
    active = next(model for model in api("/api/tags")["models"] if model["name"] == settings["model"])
    assert active["digest"] == settings["digest"]
    dump(out / "runtime.json", {"ollama": api("/api/version"), "model": active, "settings": settings})
    started = time.monotonic()
    jobs = workload(families, book, settings)
    with (out / "propagation_outputs.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for number, (case, source, operation, method, body) in enumerate(jobs, 1):
            if time.monotonic() - started >= settings["max_wall_seconds"]:
                break
            prompt = settings["op"][operation] + "\n\nTeaching text:\n" + body
            options = {"seed": settings["seed"], "num_ctx": settings["num_ctx"], "num_predict": settings["num_predict"],
                       "temperature": settings["temperature"], "num_thread": settings["thread_limit"], "num_gpu": 24}
            began = time.monotonic()
            record = {"case": case, "source": source, "op": operation, "method": method, "input": body,
                      "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
            try:
                result = api("/api/generate", {"model": settings["model"], "prompt": prompt, "options": options,
                                              "stream": False, "keep_alive": "12m"})
                record.update(output=result["response"].strip(), termination=result.get("done_reason"),
                              tokens=result.get("eval_count", 0), eval_ns=result.get("eval_duration", 0))
            except (OSError, ValueError, KeyError) as exc:
                record.update(output="", error=type(exc).__name__)
            record["seconds"] = time.monotonic() - began
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            if number % 6 == 0:
                print(f"{number}/{len(jobs)} model calls recorded ({time.monotonic() - started:.1f}s)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("r0", "r1"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    settings, families = config(), catalog()
    book = codebook(families, settings["seed"])
    args.out.mkdir(parents=True, exist_ok=True)
    if args.phase == "r0":
        result = r0(families, book, settings)
        dump(args.out / "capacity.json", result)
        dump(args.out / "codebook.json", book)
        print("R0 carrier conditions passed", {key: value for key, value in result.items() if key != "assets"})
    else:
        assert (args.out / "capacity.json").is_file() and (args.out / "risk_checks.json").is_file()
        propagate(args.out, families, book, settings)


if __name__ == "__main__":
    main()


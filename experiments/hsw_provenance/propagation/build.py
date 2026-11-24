"""OpenStax provenance grid with explicit fact survival at every relay."""
import argparse
import hashlib
import itertools
import json
import math
import random
import re
import statistics
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "var/results/hsw-st/openstax_quality_20261123/ACCEPTED.json"
NOMINAL = (1, 3, 5)
TRANSFORMS = ("forward", "summary", "light_rewrite", "strong_rewrite", "truncate")
PILOT = (
    "math-01", "math-05", "math-08", "math-09",
    "physics-01", "physics-05", "physics-10", "physics-11",
    "statistics-02", "statistics-04", "statistics-05", "statistics-08",
)
NOISE = (
    "This handout records the lesson sequence. The instructor introduces the exercise before discussing it.",
    "The audience can use this recap during practice. Each participant should read the instructions.",
    "The session ends with a review. This copy omits the original mathematical content.",
)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_unit(original, light, strong):
    return {"text": original, "light": light, "strong": strong}


def gcdfacts(q):
    a, b, c = map(int, re.findall(r"\d+", q))
    g = math.gcd(a, b, c)
    ns = f"{a}, {b}, and {c}"
    s = (a//g, b//g, c//g)
    counts = f"{s[0]}, {s[1]}, and {s[2]}"
    return [
        make_unit(f"For the three genres with {ns} books, each shelf contains a single genre and all shelves must be filled equally.",
                  f"The genre counts are {ns}, and shelving must use identical group sizes with no mixing.",
                  f"Partition {ns} books by genre into equally populated shelves."),
        make_unit(f"The largest common divisor of the genre totals {ns} is {g}, which sets the maximum number of books per shelf.",
                  f"Equal shelving without leftovers permits at most {g} books on a shelf for totals {ns}.",
                  f"GCD({a}, {b}, {c}) = {g}."),
        make_unit(f"For {ns} books in the respective genres, the shelf counts are {counts} after division by {g}.",
                  f"The genres with {ns} books need {counts} shelves respectively.",
                  f"Divide the vector ({a}, {b}, {c}) by {g} to get {s} shelves."),
    ], [f"{g} books", *(f"{x} shelves" for x in s)]


def sequencefacts(q, geometric):
    terms = list(map(int, re.findall(r"\b\d+\b", q)))
    if geometric:
        n, a, d = terms
        last = a*d**(n-1)
        total = a*(d**n-1)//(d-1)
        label = "geometric"
        relation = f"multiplies by {d}"
        alternate = f"ratio {d}"
    else:
        a, d, one, n = terms
        assert one == 1
        last = a+(n-1)*d
        total = n*(a+last)//2
        label = "arithmetic"
        relation = f"increases by {d}"
        alternate = f"difference {d}"
    group = f"the {label} sequence with first term {a} and {alternate}"
    return [
        make_unit(f"This {label} sequence begins with {a}, {relation} at each step, and runs through term {n}.",
                  f"Start at {a} and use a constant {alternate} to generate {n} terms.",
                  f"The recurrence is {label} with seed {a}, {alternate}, and length {n}."),
        make_unit(f"In {group}, the value at position {n} is {last}.",
                  f"Counting from one in {group} puts {last} at index {n}.",
                  f"With parameters ({a}, {d}) for a {label} sequence, a({n}) = {last}."),
        make_unit(f"The sum of the first {n} terms of {group} is {total}.",
                  f"Adding the first {n} values in {group} gives {total}.",
                  f"The finite {label} series with parameters ({a}, {d}) has S({n}) = {total}."),
    ], [str(last), str(total)]


def physicsfacts(q):
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", q)]
    if "piston" in q:
        heat, work = map(int, numbers)
        delta = heat-work
        return [
            make_unit(f"The closed piston takes in {heat} J of heat and performs {work} J of work, with its bulk kinetic and potential energy unchanged.",
                      f"Heating supplies {heat} J and piston work removes {work} J, with no bulk energy change.",
                      f"For the closed piston, Q = {heat} J, W_out = {work} J, and bulk energy is constant."),
            make_unit(f"For the closed piston receiving {heat} J and doing {work} J of work, the internal energy rises by {delta} J.",
                      f"Subtract the {work} J of work from the {heat} J of heating to get an internal energy gain of {delta} J.",
                      f"Internal energy change equals +{delta} J for a piston with Q={heat} J and W_out={work} J."),
            make_unit(f"For the piston heated by {heat} J while doing {work} J of work, internal energy is a state quantity and heat depends on the process.",
                      f"The {heat} J of heating in this piston is path dependent, while the internal energy is a state property.",
                      f"For the {heat} J input and {work} J output piston, U is a state function and heat is a transfer quantity."),
        ], [f"+{delta} J", "Internal energy is a state quantity"]
    if "capacitor" in q:
        r, c, supply = map(int, numbers)
        tau = r*c/1000
        v = supply*(1-math.exp(-1))
        circuit = f"the initially uncharged {r}-ohm and {c}-mF series circuit"
        return [
            make_unit(f"An ideal {supply} V source starts charging {circuit}.",
                      f"Before applying {supply} V, the {c} mF capacitor in series with {r} ohms has zero voltage.",
                      f"The {r} ohm, {c} mF RC network has a zero initial condition and a {supply} V step input."),
            make_unit(f"For {circuit}, the resistance times capacitance gives a time constant of {tau:g} seconds.",
                      f"The {r} ohm and {c} mF components give a charging time constant of {tau:g} s.",
                      f"In the {r} ohm, {c} mF network, tau = RC = {tau:g} s."),
            make_unit(f"After one time constant in {circuit}, the capacitor voltage is approximately {v:.2f} V.",
                      f"At t = RC, the capacitor in the {r} ohm and {c} mF circuit reaches about {v:.2f} volts.",
                      f"For the {r} ohm, {c} mF charging circuit, V_C(tau) = {supply}(1 - exp(-1)) ≈ {v:.2f} V."),
        ], [f"{tau:g} s", f"{v:.2f} V"]
    height, speed, g, *_ = numbers
    t = math.sqrt(2*height/g)
    d = speed*t
    ledge = f"a horizontal launch at {speed:g} m/s from a {height:g} m ledge"
    return [
        make_unit(f"Consider {ledge}, neglecting air resistance and taking gravity as {g:g} m/s².",
                  f"The projectile leaves a ledge {height:g} m high with horizontal speed {speed:g} m/s and no air drag.",
                  f"Initial conditions are h={height:g} m, v_x={speed:g} m/s, v_y=0, and g={g:g} m/s² without drag."),
        make_unit(f"For {ledge}, the time to reach the ground is {t:g} seconds.",
                  f"A ball leaving the {height:g} m ledge at {speed:g} m/s spends {t:g} s in flight.",
                  f"For h={height:g} m and v_x={speed:g} m/s, solving h=gt²/2 gives t={t:g} s."),
        make_unit(f"For {ledge}, the first impact is {d:g} metres horizontally from the launch point.",
                  f"Starting {height:g} m above the floor at {speed:g} m/s gives horizontal range {d:g} m.",
                  f"With h={height:g} m and v_x={speed:g} m/s, the product v_x t yields {d:g} m."),
    ], [f"{t:g} s", f"{d:g} m"]


def statisticsfacts(q):
    values = list(map(int, re.findall(r"\d+", q)))
    if "exponential" in q:
        m, t = values
        p = math.exp(-t/m)
        return [
            make_unit(f"The waiting time is modeled by a continuous exponential distribution with mean {m} minutes.",
                      f"Use an exponential model whose average delay is {m} min.",
                      f"The delay X has an exponential law with scale {m} min."),
            make_unit(f"An exponential waiting time with mean {m} minutes has rate one divided by {m} per minute.",
                      f"For the exponential model with {m} min mean, the rate is 1/{m} min⁻¹.",
                      f"The exponential scale {m} min corresponds to λ = 1/{m} min⁻¹."),
            make_unit(f"The exponential waiting time with mean {m} minutes exceeds {t} minutes with probability about {p:.4f}.",
                      f"An exponential delay with average {m} min has chance {p:.4f} of lasting over {t} min.",
                      f"At scale {m} min, the exponential survival function satisfies S({t}) = exp(-{t}/{m}) ≈ {p:.4f}."),
        ], [f"1/{m} per minute", f"{p:.4f}"]
    a, b, c, d, point = values
    p = Fraction(d-c, b-a)
    m = (a+b)/2
    scope = f"a uniform wait from {a} through {b} minutes"
    return [
        make_unit(f"For {scope}, the expected waiting time is {m:g} minutes.",
                  f"A uniform delay supported on [{a}, {b}] min averages {m:g} min.",
                  f"A uniform law on [{a}, {b}] min has mean ({a}+{b})/2 = {m:g} min."),
        make_unit(f"For {scope}, the probability of waiting between {c} and {d} minutes is {p}.",
                  f"On the uniform support [{a}, {b}] min, waiting more than {c} and less than {d} min has chance {p}.",
                  f"For X uniform on [{a}, {b}] min, P({c}<X<{d}) = ({d}-{c})/({b}-{a}) = {p}."),
        make_unit(f"For {scope}, the probability of a wait lasting exactly {point} minutes is zero.",
                  f"A delay uniformly distributed over [{a}, {b}] min has zero chance of equaling {point} min.",
                  f"The uniform density on [{a}, {b}] min assigns a singleton at {point} min zero mass."),
    ], [f"{m:g} min", f"{d-c}/{b-a}", "0"]


def source(row):
    question = row["question"]
    if row["domain"] == "math":
        if "sequence" in question or "display" in question:
            units, checked = sequencefacts(question, "display" in question)
        else:
            units, checked = gcdfacts(question)
    elif row["domain"] == "physics":
        units, checked = physicsfacts(question)
    else:
        units, checked = statisticsfacts(question)
    assert len(checked) == len(row["expected"])
    for expected, calculated in zip(row["expected"], checked, strict=True):
        assert expected.startswith(calculated), (row["id"], expected, calculated)
    prior = row["text"]
    assert digest(prior) == row["sha256"]
    return dict(source_id=row["id"], domain=row["domain"], source_url=row["source_url"], section=row["section"],
                question=question, expected=checked, frozen_draft_sha256=row["sha256"], frozen_draft_text=prior,
                text="\n".join(unit["text"] for unit in units),
                units=[dict(unit, fact_id=f"{row['id']}:f{n}") for n, unit in enumerate(units, 1)])


def releases_for(sources):
    return [dict(release_id=f"{source['source_id']}:issue:{issuer}", issuer_id=issuer,
                 source_id=source["source_id"], text=source["text"], sha256=digest(source["text"]))
            for source in sources for issuer in ("issuer-a", "issuer-b")]


def snapshot(units, hop, agent, elapsed):
    known = [unit for unit in units if unit["fact_id"] is not None]
    return dict(hop=hop, agent_id=agent, text="\n".join(unit["text"] for unit in units), units=units,
                retained_source_ids=sorted({unit["source_id"] for unit in known}),
                retained_release_ids=sorted({unit["release_id"] for unit in known}),
                retained_fact_ids=sorted({unit["fact_id"] for unit in known}), seconds=elapsed)


def propagate(releases, sources, transform, max_depth, seed):
    units = []
    lookup = {unit["fact_id"]:unit for issue in releases for unit in sources[issue["source_id"]]["units"]}
    for issue in releases:
        for unit in sources[issue["source_id"]]["units"]:
            units.append(dict(fact_id=unit["fact_id"], source_id=issue["source_id"],
                              release_id=issue["release_id"], text=unit["text"], rendering="original"))
    # Interleave source units, so prefix truncation and deletion encounter every source.
    units.sort(key=lambda unit: unit["fact_id"].split(":")[-1])
    rng = random.Random(seed)
    rng.shuffle(units)
    hops = []
    for hop in range(1, max_depth+1):
        start = time.perf_counter()
        if transform == "summary":
            # Produce a shorter semantic summary through loss of 25% of current facts.
            doomed = set(rng.sample(range(len(units)), math.ceil(len(units)*.25)))
            units = [unit for i, unit in enumerate(units) if i not in doomed]
        elif transform == "truncate":
            # Whole-unit boundary avoids ambiguous half-fact truth.
            units = units[: int(len(units)*.7)]
        elif transform in ("light_rewrite", "strong_rewrite"):
            level = "light" if transform == "light_rewrite" else "strong"
            share = .25 if level == "light" else .65
            edits = rng.sample(range(len(units)), math.ceil(len(units)*share))
            units = [dict(unit, text=lookup[unit["fact_id"]][level], rendering=level)
                     if i in edits else unit for i, unit in enumerate(units)]
            if level == "strong" and hop % 2 == 0 and units:
                units = units[1:]  # omission in stronger paraphrase
        if not units:
            record = snapshot([dict(fact_id=None, source_id=None, release_id=None,
                                    text=NOISE[(hop-1)%len(NOISE)], rendering="unattributed")],
                              hop, f"relay-{hop}", 0.0)
        else:
            record = snapshot(units, hop, f"relay-{hop}", 0.0)
        record["seconds"] = time.perf_counter()-start
        hops.append(record)
    return hops


def query_rows(sources, releases):
    index = {row["source_id"]:row for row in sources}
    by_source = {sid:[row for row in releases if row["source_id"] == sid] for sid in index}
    source_ids = list(index)
    for repeat, fusion, transform in itertools.product(range(len(sources)), (1,2,3), TRANSFORMS):
        # Choose no repeated source within a chain. Cross-topic and same-topic chains both occur.
        stride = 1 + repeat % 3
        batch = [source_ids[(repeat+i*stride) % len(source_ids)] for i in range(fusion)]
        assert len(set(batch)) == fusion
        issues = [by_source[sid][(repeat+i)%2] for i, sid in enumerate(batch)]
        key = f"{repeat+1:02d}-f{fusion}-{transform}"
        seed = int(digest("provenance-20261124|"+key)[:16],16)
        hops = propagate(issues, index, transform, max(NOMINAL), seed)
        for depth in NOMINAL:
            end = hops[depth-1]
            yield dict(case_id=f"{key}-d{depth}", chain_id=key, depth=depth, fusion_count=fusion,
                       replicate=repeat+1, partition="calibration" if repeat%4 == 0 else "test",
                       transform=transform, input_source_ids=batch,
                       input_release_ids=[issue["release_id"] for issue in issues],
                       input_issuer_ids=[issue["issuer_id"] for issue in issues],
                       input_fact_ids=[unit["fact_id"] for sid in batch for unit in index[sid]["units"]],
                       text=end["text"], units=end["units"], retained_source_ids=end["retained_source_ids"],
                       retained_release_ids=end["retained_release_ids"],
                       retained_fact_ids=end["retained_fact_ids"], per_hop=hops[:depth],
                       seconds=sum(hop["seconds"] for hop in hops[:depth]))
    for k in range(len(sources)):
        row = snapshot([dict(fact_id=None,source_id=None,release_id=None,text=NOISE[k%3],rendering="unattributed")],1,"null-control",0)
        yield dict(case_id=f"null-{k+1:02d}",chain_id=f"null-{k+1:02d}",depth=1,fusion_count=0,
                   replicate=k+1,partition="calibration" if k%4==0 else "test",transform="null_control",
                   input_source_ids=[],input_release_ids=[],input_issuer_ids=[],input_fact_ids=[],per_hop=[row],**row)


def replay_marked(cases, releases, marked):
    """Apply same retained fact IDs and rewrite choices to line-preserving releases."""
    by_release = {row["release_id"]:row["text"].splitlines() for row in releases}
    mapped = {}
    for issue in marked:
        lines = issue["text"].splitlines()
        if len(lines) != len(by_release[issue["release_id"]]):
            raise ValueError(f"Marked line count differs for {issue['release_id']}")
        mapped[issue["release_id"]] = lines

    def replay(row):
        units = []
        for unit in row["units"]:
            issue = unit["release_id"]
            if unit["rendering"] == "original" and issue in mapped:
                index = int(unit["fact_id"].split(":f")[-1])-1
                units.append(dict(unit,text=mapped[issue][index]))
            else:
                units.append(unit)
        return dict(row, units=units, text="\n".join(unit["text"] for unit in units))

    for case in cases:
        yield dict(replay(case),per_hop=[replay(hop) for hop in case["per_hop"]])


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")


def summarize(cases):
    groups = defaultdict(list)
    for row in cases:
        if row["fusion_count"] > 0:
            groups[row["transform"],row["depth"]].append(row)
    rows = []
    for (transform, depth), group in sorted(groups.items()):
        rows.append(dict(transform=transform,depth=depth,n=len(group),
                         fact_fidelity=statistics.mean(len(r["retained_fact_ids"])/len(r["input_fact_ids"]) for r in group),
                         source_retention=statistics.mean(len(r["retained_source_ids"])/len(r["input_source_ids"]) for r in group),
                         mean_seconds=statistics.mean(r["seconds"] for r in group)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.all and args.out is None:
        parser.error("--all requires a distinct --out directory")
    out = args.out or HERE
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(FROZEN.read_bytes())
    by_id = {row["id"]:row for row in data}
    sources = [source(by_id[sid]) for sid in (by_id if args.all else PILOT)]
    releases = releases_for(sources)
    cases = list(query_rows(sources,releases))
    assert len(cases) == len({r["case_id"] for r in cases}) == len(sources)*46
    for case in cases:
        assert set(case["retained_fact_ids"]) <= set(case["input_fact_ids"])
        assert case["per_hop"][-1]["text"] == case["text"]
        assert all(set(b["retained_fact_ids"]) <= set(a["retained_fact_ids"])
                   for a,b in zip(case["per_hop"],case["per_hop"][1:]))
    assert list(replay_marked(cases,releases,releases)) == cases
    write(out/"sources.json",sources)
    write(out/"releases.json",releases)
    with (out/"cases.jsonl").open("w",encoding="utf-8",newline="\n") as stream:
        for row in cases:
            stream.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")
    write(out/"config.json",dict(mode="controlled fact-level relays", seed_salt="provenance-20261124",
                               depths=NOMINAL, fusion=[1,2,3], transforms=TRANSFORMS,
                               source_file=str(FROZEN.relative_to(ROOT)),
                               frozen_sha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
                               releases_per_source=2, source_count=len(sources), case_count=len(cases),
                               cases_sha256=hashlib.sha256((out/"cases.jsonl").read_bytes()).hexdigest(),
                               calibration_rule="replicate congruent to 1 mod 4",
                               models=[],gpu_hours=0, paid_api_calls=0))
    write(out/"retention.json",summarize(cases))
    print(len(sources),"sources,",len(releases),"releases,",len(cases),"endpoints")


if __name__ == "__main__":
    main()

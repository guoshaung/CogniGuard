"""Brute-force checks of Prop 2 (k+f exact under any-to-any full transfers)
and Prop 3 (graph-constrained exact check = Steiner partition cover)."""
import itertools, random, sys
from functools import lru_cache

def coalition_covers(H, W, k):
    agents = range(len(H))
    for size in range(1, k + 1):
        for C in itertools.combinations(agents, size):
            if W <= frozenset().union(*(H[a] for a in C)):
                return True
    return False

def brute(O, W, k, f, edges):
    """Exists a sequence of <= f full-knowledge transfers along `edges`
    (directed pairs) after which some <=k coalition covers W?"""
    start = tuple(O)
    seen = {start}
    frontier = [start]
    for _ in range(f + 1):
        nxt = []
        for H in frontier:
            if coalition_covers(H, W, k):
                return True
            for u, v in edges:
                H2 = list(H); H2[v] = H[v] | H[u]; H2 = tuple(H2)
                if H2 not in seen:
                    seen.add(H2); nxt.append(H2)
        frontier = nxt
    return False

def bfs_dist(n, und):
    INF = 10**9
    d = [[INF]*n for _ in range(n)]
    for s in range(n):
        d[s][s] = 0; q=[s]
        for x in q:
            for y in und[x]:
                if d[s][y] == INF: d[s][y] = d[s][x]+1; q.append(y)
    return d

def steiner(n, und, terms):
    """Dreyfus-Wagner: min edges of a tree spanning terms (undirected)."""
    terms = list(terms); t = len(terms)
    if t <= 1: return 0
    d = bfs_dist(n, und); INF = 10**9
    dp = [[INF]*n for _ in range(1 << t)]
    for i, x in enumerate(terms):
        for v in range(n): dp[1 << i][v] = d[x][v]
    for S in range(1, 1 << t):
        if S & (S-1) == 0: continue
        for v in range(n):
            sub = (S-1) & S
            while sub:
                if dp[sub][v] + dp[S ^ sub][v] < dp[S][v]:
                    dp[S][v] = dp[sub][v] + dp[S ^ sub][v]
                sub = (sub-1) & S
        for v in range(n):
            dp[S][v] = min(dp[S][u] + d[u][v] for u in range(n))
    return min(dp[(1 << t)-1])

def steiner_partition(O, W, k, f, n, und):
    holders = [a for a in range(n) if O[a] & W]
    h = len(holders)
    cost = {}
    for m in range(1, 1 << h):
        cost[m] = steiner(n, und, [holders[i] for i in range(h) if m >> i & 1])
    INF = 10**9
    # best[m][j]: min total cost to partition subset m into j clusters
    best = [[INF]*(k+1) for _ in range(1 << h)]
    best[0][0] = 0
    for m in range(1, 1 << h):
        low = m & -m
        sub = m
        while sub:
            if sub & low:
                for j in range(1, k+1):
                    c = best[m ^ sub][j-1] + cost[sub]
                    if c < best[m][j]: best[m][j] = c
            sub = (sub-1) & m
    for m in range(1, 1 << h):
        units = frozenset().union(*(O[holders[i]] for i in range(h) if m >> i & 1))
        if W <= units and min(best[m][1:]) <= f:
            return True
    return W <= frozenset() 

def run(trials, seed):
    rng = random.Random(seed)
    stats = {"p2_agree":0, "p2_n":0, "p3_agree":0, "p3_n":0, "graph_stricter":0}
    for _ in range(trials):
        n = rng.randint(4, 6); U = list(range(5)); W = frozenset(rng.sample(U, rng.randint(2, 4)))
        O = [frozenset(u for u in U if rng.random() < 0.3) for _ in range(n)]
        k = rng.randint(1, 3); f = rng.randint(0, 2)
        full = [(u, v) for u in range(n) for v in range(n) if u != v]
        b = brute(O, W, k, f, full); kf = coalition_covers(O, W, min(k + f, n))
        stats["p2_n"] += 1; stats["p2_agree"] += (b == kf)
        if b != kf: print("P2 MISMATCH", n, O, W, k, f, b, kf); sys.exit(1)
        # random connected sparse undirected graph
        und = [set() for _ in range(n)]
        for v in range(1, n):
            u = rng.randrange(v); und[u].add(v); und[v].add(u)
        if rng.random() < 0.5:
            a, c = rng.sample(range(n), 2); und[a].add(c); und[c].add(a)
        edges = [(u, v) for u in range(n) for v in und[u]]
        bg = brute(O, W, k, f, edges); sp = steiner_partition(O, W, k, f, n, und)
        stats["p3_n"] += 1; stats["p3_agree"] += (bg == sp)
        if bg != sp: print("P3 MISMATCH", n, O, W, k, f, [sorted(x) for x in und], bg, sp); sys.exit(1)
        stats["graph_stricter"] += (kf and not bg)
    return stats

if __name__ == "__main__":
    print(run(int(sys.argv[1]), int(sys.argv[2])))

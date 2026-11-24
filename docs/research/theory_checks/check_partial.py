import itertools, random, sys
sys.path.insert(0, '.')
from check_props import coalition_covers
def brute_partial(O, W, k, f, n, s):
    start = tuple(O); seen={start}; frontier=[start]
    for _ in range(f+1):
        nxt=[]
        for H in frontier:
            if coalition_covers(H, W, k): return True
            for u in range(n):
                for v in range(n):
                    if u==v: continue
                    for size in range(1, s+1):
                        for S in itertools.combinations(sorted(H[u]), size):
                            H2=list(H); H2[v]=H[v]|frozenset(S); H2=tuple(H2)
                            if H2 not in seen: seen.add(H2); nxt.append(H2)
        frontier=nxt
    return False
rng=random.Random(7); strict=0; unsound=0; N=300
for _ in range(N):
    n=rng.randint(4,6); U=list(range(5)); W=frozenset(rng.sample(U, rng.randint(2,4)))
    O=[frozenset(u for u in U if rng.random()<0.35) for _ in range(n)]
    k=rng.randint(1,3); f=rng.randint(1,2)
    b=brute_partial(O,W,k,f,n,1); kf=coalition_covers(O,W,min(k+f,n))
    strict += (kf and not b); unsound += (b and not kf)
print({"trials":N,"k+f_flags_but_partial_safe":strict,"partial_unsafe_but_k+f_safe":unsound})

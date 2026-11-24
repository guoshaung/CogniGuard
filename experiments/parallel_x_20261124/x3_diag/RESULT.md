# X3 utility diagnosis

Historical verdict: STOP. This diagnosis is not a PASS and does not reopen X3.
The fail-closed rule is the one that was rescored: an empty id list denies, and every attributed issuance must authorize. One true id keeps the oracle labels on the catalog.
The imported worker `decide` stays fail-open (allow if any attributed issuance authorizes) and was not edited. Reported utilities use fail-closed.
`MAX_OVERHEAD_RATIO` stays 10. It was not retuned.

## Utility

A utility hit requires oracle allow, a fail-closed allow, and the true asset id among the assets of the attributed issuances. The denominator is the oracle-allow count.

Oracle-allow requests: 70. Oracle-deny requests: 50.

| method | utility | false reject | unauthorized |
| --- | --- | --- | --- |
| W0 | 50/70 | 20/70 | 0/50 |
| F5 | 30/70 | 40/70 | 0/50 |
| F7 | 25/70 | 45/70 | 0/50 |
| F6 | 15/70 | 55/70 | 0/50 |
| Oracle | 70/70 | 0/70 | 0/50 |
| CRED | 50/70 | 20/70 | 0/50 |
| RECORD | 30/70 | 40/70 | 0/50 |

Cited rounded utilities are the fail-closed (and, for these three methods, also fail-open) ratios. W0 50/70 rounds to 0.7143 (cited 0.7143) F5 30/70 rounds to 0.4286 (cited 0.4286) F7 25/70 rounds to 0.3571 (cited 0.3571). Round-3 forms of the same ratios are 0.714, 0.429, and 0.357. The denominator is 70.

F6 on the five oracle-allow cases (5 logical cases x 5 seeds): 0/25. F5 on those requests: 5/25. F7: 0/25. CRED: 25/25. RECORD: 5/25.

F6's fail-closed numerator is the oracle-allow requests whose simhash expansion contains only authorizing issuances: s5-derived-read, ctrl-allow, ctrl-paraphrase (15/70). None of the five focus cases are in that numerator (0/25). The same F6 ids under the untouched fail-open worker rule score 70/70, because any one authorizing row is enough.

## Five cases

Channel legend, quoted from the worker script:

```
# benign = issuance ids in metadata and a signed receipt
# meta = issuance ids in metadata, no receipt
# stripped = no metadata, no receipt
# boundary = cross-org forward drops external source metadata and the receipt
```

Issuance defaults, quoted from the worker dataclass. Fields omitted on a constructor use these defaults:

```
class Issuance:
    issuance_id: str
    asset_id: str
    grantee: str
    org: str
    actions: frozenset
    purposes: frozenset
    redistribution: str  # none | internal | external
    revoked: bool = False
    source_ids: tuple = ()
    # all_sources: this issuance authorizes only if every source record's
    # obligation also passes. Obligations are read from the registry.
    mode: str = "any"
```

### s1-same-perm-meta

Still holds: False. Fair baseline recovers the allow: True.
Recovered by: CRED, F5, RECORD.

Catalog row, quoted from the worker script:

```
("s1-same-perm-meta", "S1", "u2", "read", "education", None, "A1", ("iss-a1-u2",), "light", "meta", True)
```

True issuance row, quoted from the worker script:

```
a1_u2 = Issuance("iss-a1-u2", "A1", "u2", "alpha", frozenset({"read", "forward"}), frozenset({"education"}), "internal")
```

Scenario S1. Subject u2. Action read. Purpose education. Dest org None. Asset A1. True issuance ids ['iss-a1-u2']. Variant light. Channel meta: issuance ids are in metadata; no receipt is attached.
Oracle allow: True. W0 allow: True.
Table facts for iss-a1-u2: grantee u2, org alpha, revoked False, actions ['forward', 'read'], purposes ['education'], redistribution internal, mode any, source ids [].
The true issuance authorizes this request under the table checks (grantee, not revoked, action, purpose, and redistribution when the action is forward or redistribute). The allow is a reasonable license outcome for that row.
No sibling issuance of this asset authorizes this subject, action, and purpose. iss-a1-u1 does not (grantee u1 != subject u2).

Sibling row iss-a1-u1, quoted from the worker script:

```
a1_u1 = Issuance("iss-a1-u1", "A1", "u1", "alpha", frozenset({"read", "forward"}), frozenset({"education"}), "internal")
```
Metadata issuance ids present: ['iss-a1-u2']. Valid receipt present: False. The watermark is not the only remaining copy of the issuance id.
Allow bits versus W0: CRED=True, F6=False, F5=True, F7=False, RECORD=True.

### s2-other-grantee

Still holds: False. Fair baseline recovers the allow: True.
Recovered by: CRED.

Catalog row, quoted from the worker script:

```
("s2-other-grantee", "S2", "u3", "redistribute", "audit", "beta", "A2", ("iss-a2-u3",), "light", "stripped", True)
```

True issuance row, quoted from the worker script:

```
Issuance("iss-a2-u3", "A2", "u3", "alpha", frozenset({"read", "redistribute"}), frozenset({"audit"}), "external")
```

Scenario S2. Subject u3. Action redistribute. Purpose audit. Dest org beta. Asset A2. True issuance ids ['iss-a2-u3']. Variant light. Channel stripped: no metadata and no receipt.
Oracle allow: True. W0 allow: True.
Table facts for iss-a2-u3: grantee u3, org alpha, revoked False, actions ['read', 'redistribute'], purposes ['audit'], redistribution external, mode any, source ids [].
The true issuance authorizes this request under the table checks (grantee, not revoked, action, purpose, and redistribution when the action is forward or redistribute). The allow is a reasonable license outcome for that row.
No sibling issuance of this asset authorizes this subject, action, and purpose. iss-a2-u1 does not (grantee u1 != subject u3; action redistribute not in actions; purpose audit not in purposes; redistribution none does not permit dest beta from org alpha).

Sibling row iss-a2-u1, quoted from the worker script:

```
Issuance("iss-a2-u1", "A2", "u1", "alpha", frozenset({"read"}), frozenset({"education"}), "none")
```
Metadata and receipt are both absent, and the ideal mark is intact. The W0 allow depends on the watermark being the only remaining copy of the issuance id after metadata was stripped. That channel is not treated as a privileged access rule. CRED carries the same id list in an HMAC on this exact or light variant.
Allow bits versus W0: CRED=True, F6=False, F5=False, F7=False, RECORD=False.

### s4-teach-read

Still holds: False. Fair baseline recovers the allow: True.
Recovered by: CRED.

Catalog row, quoted from the worker script:

```
("s4-teach-read", "S4", "u4", "read", "teaching", None, "A3", ("iss-a3-teach",), "exact", "stripped", True)
```

True issuance row, quoted from the worker script:

```
Issuance("iss-a3-teach", "A3", "u4", "alpha", frozenset({"read"}), frozenset({"teaching"}), "none")
```

Scenario S4. Subject u4. Action read. Purpose teaching. Dest org None. Asset A3. True issuance ids ['iss-a3-teach']. Variant exact. Channel stripped: no metadata and no receipt.
Oracle allow: True. W0 allow: True.
Table facts for iss-a3-teach: grantee u4, org alpha, revoked False, actions ['read'], purposes ['teaching'], redistribution none, mode any, source ids [].
The true issuance authorizes this request under the table checks (grantee, not revoked, action, purpose, and redistribution when the action is forward or redistribute). The allow is a reasonable license outcome for that row.
No sibling issuance of this asset authorizes this subject, action, and purpose. iss-a3-research does not (purpose teaching not in purposes).

Sibling row iss-a3-research, quoted from the worker script:

```
Issuance(
            "iss-a3-research",
            "A3",
            "u4",
            "alpha",
            frozenset({"read", "forward", "redistribute"}),
            frozenset({"research"}),
            "internal",
        )
```
Metadata and receipt are both absent, and the ideal mark is intact. The W0 allow depends on the watermark being the only remaining copy of the issuance id after metadata was stripped. That channel is not treated as a privileged access rule. CRED carries the same id list in an HMAC on this exact or light variant.
Allow bits versus W0: CRED=True, F6=False, F5=False, F7=False, RECORD=False.

### s3-live-copy

Still holds: False. Fair baseline recovers the allow: True.
Recovered by: CRED.

Catalog row, quoted from the worker script:

```
("s3-live-copy", "S3", "u5", "read", "education", None, "A4", ("iss-a4-new",), "light", "stripped", True)
```

True issuance row, quoted from the worker script:

```
Issuance("iss-a4-new", "A4", "u5", "alpha", frozenset({"read", "forward"}), frozenset({"education"}), "internal", False)
```

Scenario S3. Subject u5. Action read. Purpose education. Dest org None. Asset A4. True issuance ids ['iss-a4-new']. Variant light. Channel stripped: no metadata and no receipt.
Oracle allow: True. W0 allow: True.
Table facts for iss-a4-new: grantee u5, org alpha, revoked False, actions ['forward', 'read'], purposes ['education'], redistribution internal, mode any, source ids [].
The true issuance authorizes this request under the table checks (grantee, not revoked, action, purpose, and redistribution when the action is forward or redistribute). The allow is a reasonable license outcome for that row.
No sibling issuance of this asset authorizes this subject, action, and purpose. iss-a4-old does not (revoked).

Sibling row iss-a4-old, quoted from the worker script:

```
Issuance("iss-a4-old", "A4", "u5", "alpha", frozenset({"read", "forward"}), frozenset({"education"}), "internal", True)
```
Metadata and receipt are both absent, and the ideal mark is intact. The W0 allow depends on the watermark being the only remaining copy of the issuance id after metadata was stripped. That channel is not treated as a privileged access rule. CRED carries the same id list in an HMAC on this exact or light variant.
Allow bits versus W0: CRED=True, F6=False, F5=False, F7=False, RECORD=False.

### s6-external-copy

Still holds: False. Fair baseline recovers the allow: True.
Recovered by: CRED.

Catalog row, quoted from the worker script:

```
("s6-external-copy", "S6", "u2", "forward", "education", "beta", "A7", ("iss-a7-ext",), "light", "boundary", True)
```

True issuance row, quoted from the worker script:

```
Issuance(
            "iss-a7-ext",
            "A7",
            "u2",
            "alpha",
            frozenset({"read", "forward", "redistribute"}),
            frozenset({"education"}),
            "external",
        )
```

Scenario S6. Subject u2. Action forward. Purpose education. Dest org beta. Asset A7. True issuance ids ['iss-a7-ext']. Variant light. Channel boundary: cross-org forward drops external source metadata and the receipt.
Oracle allow: True. W0 allow: True.
Table facts for iss-a7-ext: grantee u2, org alpha, revoked False, actions ['forward', 'read', 'redistribute'], purposes ['education'], redistribution external, mode any, source ids [].
The true issuance authorizes this request under the table checks (grantee, not revoked, action, purpose, and redistribution when the action is forward or redistribute). The allow is a reasonable license outcome for that row.
No sibling issuance of this asset authorizes this subject, action, and purpose. iss-a7-int does not (redistribution internal does not permit dest beta from org alpha).

Sibling row iss-a7-int, quoted from the worker script:

```
Issuance("iss-a7-int", "A7", "u2", "alpha", frozenset({"read", "forward"}), frozenset({"education"}), "internal")
```
Metadata and receipt are both absent, and the ideal mark is intact. The W0 allow depends on the watermark being the only remaining copy of the issuance id after metadata was stripped. That channel is not treated as a privileged access rule. CRED carries the same id list in an HMAC on this exact or light variant.
Allow bits versus W0: CRED=True, F6=False, F5=False, F7=False, RECORD=False.

## Overhead

Median of 5 warmed passes over the same 120 requests. Milliseconds per request. Ratios use F2 BM25 rank only as the denominator.

| piece | ms/request | ratio to F2 rank |
| --- | ---: | ---: |
| F2_bm25_rank_only | 0.0392 | 1.00 |
| F6_simhash_only | 0.5720 | 14.58 |
| F7_receipt_verify_only | 0.0008 | 0.02 |
| W0_mark_intact_lookup_only | 0.0002 | 0.00 |
| W1_as_defined | 0.5748 | 14.65 |
| F1_minhash_only | 3.6901 | 94.07 |
| F1_attribute | 3.6956 | 94.21 |
| F6_attribute | 0.5736 | 14.62 |
| F2_attribute | 0.0383 | 0.98 |
| call_overhead | 0.0000 | 0.00 |

Historical fail-open timing was W1 0.582 ms versus F2 0.037 ms, ratio 15.60. That ratio is above MAX_OVERHEAD_RATIO 10, so the historical overhead comparison does not pass. The cap was not changed. Recomputed on this machine, W1-as-defined is 0.5748 ms/request and F2 attribute is 0.0383 ms/request, ratio 14.99. F2 BM25 rank only is 0.0392 ms. Rank-only and full F2 attribute differ by 0.0009 ms, timer noise around the historical 0.037 ms. Simhash only is 0.5720 ms (ratio 14.58). Full F6 attribute is 0.5736 ms. Receipt verify only is 0.0008 ms (ratio 0.02). Ideal-mark lookup only is 0.0002 ms (ratio 0.00). Empty call overhead is 0.0000 ms. The 15.6x gap is the simhash fingerprint inside W1, not HMAC verification, not the ideal-mark lookup, and not the scoring harness. F1 MinHash attribute is 3.6956 ms/request, ratio 94.21 to F2 rank. It dominates W1.

## BGE

F3/F4 BLOCKED. sentence_transformers, FlagEmbedding, and bge do not import in this interpreter. torch, transformers, and onnxruntime do not import. No local Hugging Face cache or bge weight directory was found. Weights were not downloaded and no hosted embedding endpoint was called. No scores were invented. HEAD of BAAI/bge-small-en-v1.5 model.safetensors returned 133466304 bytes (HTTP/2 200 ). The body was not fetched because no local loader can run it.

## Handoff

PILOT_HANDOFF.md written: no. Fail-closed rescore over 120 requests (5 seeds x 24 cases). Oracle allow 70, oracle deny 50. Unauthorized success numerators: F0 0/50, F1 0/50, F2 0/50, F5 0/50, F6 0/50, F7 0/50, W0 0/50, W1 0/50, Oracle 0/50, CRED 0/50, RECORD 0/50. Utility for W0, F5, and F7 uses the worker hit rule (oracle allow, true asset in the attributed assets, decision allows) under fail-closed. Those three methods attribute at most the true id, so fail-open and fail-closed utilities match for them. The five logical F7 denials that W0 allows are oracle allows. No sibling grant authorizes those five requests. s1-same-perm-meta still carries the issuance id in metadata (receipt absent), so the mark is not the only copy; F5 and RECORD allow it. The other four have metadata and receipt stripped. The ideal mark is then the only historical channel that still carries the true issuance id. That is not a privileged access rule. CRED, an HMAC over the same issuance id list, is present on exact and light variants and absent on paraphrase, and it allows all five. F6's simhash hit expands to every issuance of the asset, and fail-closed denies because the sibling row does not authorize. No case still holds. pilot_handoff is false. The historical W1/F2 ratio 15.60 still exceeds MAX_OVERHEAD_RATIO 10, so that overhead comparison does not pass. diagnosis_verdict is STOP. X3 did not pass.

import json

with open("artifacts/experiments/duplicate_audit_20_clusters.json", "r", encoding="utf-8") as f:
    clusters = json.load(f)

for c in clusters:
    r1, r2 = c["record_1"], c["record_2"]
    ev = c["similarity_evidence"]
    print(f"{c['cluster_num']:2d}. {c['title']} | {c['company']}")
    print(f"    R1: {r1['id'][:8]}.. ({r1['source']}, {r1['location']})")
    print(f"    R2: {r2['id'][:8]}.. ({r2['source']}, {r2['location']})")
    print(f"    Evidence: title_match={ev['title_normalized_equal']}, co_match={ev['company_match']}, jaccard={ev['description_jaccard']:.2f}")
    print(f"    Decision: {c['merge_decision']}")

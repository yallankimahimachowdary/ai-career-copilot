import json
import random
from app.services.deduplication_service import (
    deduplication_service,
    _normalize_str,
    _companies_match,
    _clean_company_name,
    _description_token_jaccard,
)

def main():
    snapshot_path = "data/snapshots/test_snap_1.json"
    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data["records"]
    canonical_records, num_merged, clusters = deduplication_service.deduplicate_records(records)
    print(f"Total clusters: {len(clusters)}, total merged: {num_merged}")

    # Index records by id
    rec_by_id = {str(r.get("id") or r.get("external_id")): r for r in records}

    # Find the Mai Mangeshkar cluster
    mai_cluster = None
    other_clusters = []
    for c in clusters:
        co_str = str(c.get("company", "")).lower()
        if "mangeshkar" in co_str or "mageshkar" in co_str:
            mai_cluster = c
        else:
            other_clusters.append(c)

    # Deterministically select 19 other clusters using seed 42
    rng = random.Random(42)
    sampled_19 = rng.sample(other_clusters, 19)

    # Combine: mai_cluster first, then the 19
    selected = [mai_cluster] + sampled_19

    results = []
    for idx, c in enumerate(selected, 1):
        canon_id = c["canonical_id"]
        dup_ids = c["duplicate_ids"]
        all_ids = [canon_id] + dup_ids

        cluster_records = [rec_by_id.get(rid) for rid in all_ids if rid in rec_by_id]
        if len(cluster_records) < 2:
            continue

        r1 = cluster_records[0]
        r2 = cluster_records[1]

        t1, t2 = r1.get("title", ""), r2.get("title", "")
        c1, c2 = r1.get("company") or r1.get("company_name", ""), r2.get("company") or r2.get("company_name", "")
        l1, l2 = r1.get("location", ""), r2.get("location", "")
        s1, s2 = r1.get("source", ""), r2.get("source", "")
        jaccard = _description_token_jaccard(r1.get("description", ""), r2.get("description", ""))

        t_match = _normalize_str(t1) == _normalize_str(t2)
        co_match = _companies_match(c1, c2)

        results.append({
            "cluster_num": idx,
            "title": c["title"],
            "company": c["company"],
            "merged_count": c["merged_count"],
            "canonical_id": canon_id,
            "duplicate_ids": dup_ids,
            "record_1": {"id": r1.get("id"), "title": t1, "company": c1, "location": l1, "source": s1},
            "record_2": {"id": r2.get("id"), "title": t2, "company": c2, "location": l2, "source": s2},
            "similarity_evidence": {
                "title_normalized_equal": t_match,
                "company_match": co_match,
                "description_jaccard": round(jaccard, 4),
            },
            "merge_decision": f"Merged into canonical {canon_id} with sources {c['sources']}",
        })

    with open("artifacts/experiments/duplicate_audit_20_clusters.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Generated audit for {len(results)} clusters. Saved to artifacts/experiments/duplicate_audit_20_clusters.json")

if __name__ == "__main__":
    main()

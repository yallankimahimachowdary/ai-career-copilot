"""
scripts/run_snapshot_dedup_audit.py
-----------------------------------
Runs DeduplicationService on the frozen job snapshot test_snap_1.json,
audits the duplicate clusters (including Mai Mangeshkar Hospital Biomedical Engineer),
reports counts, and saves test_snap_1_deduped.json while preserving test_snap_1.json.
"""

import json
from app.services.deduplication_service import deduplication_service


def main():
    snapshot_path = "data/snapshots/test_snap_1.json"
    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data["records"]
    orig_count = len(records)
    print(f"Original record count in {snapshot_path}: {orig_count}")

    canonical_records, num_merged, clusters = deduplication_service.deduplicate_records(records)
    new_count = len(canonical_records)
    print(f"Merged duplicate records: {num_merged}")
    print(f"New unique canonical record count: {new_count}")
    print(f"Total duplicate clusters detected: {len(clusters)}")

    # Verify Mai Mangeshkar Hospital Biomedical Engineer cluster
    found_mai = False
    for c in clusters:
        co_str = str(c.get("company", "")).lower()
        if "mangeshkar" in co_str or "mageshkar" in co_str:
            found_mai = True
            print("\n[VERIFIED] Mai Mangeshkar Hospital Cluster:")
            print(f"  Title: {c['title']}")
            print(f"  Company: {c['company']}")
            print(f"  Merged Count: {c['merged_count']}")
            print(f"  Sources: {c['sources']}")
            print(f"  Locations: {c['locations']}")
            print(f"  Duplicate IDs: {c['duplicate_ids']}")

    if not found_mai:
        print("\n[WARNING] Mai Mangeshkar Hospital not found in clusters!")

    print("\nAuditing first 10 duplicate clusters:")
    for idx, c in enumerate(clusters[:10], start=1):
        print(f"  {idx:2d}. '{c['title']}' at '{c['company']}' -> {c['merged_count']} postings, sources: {c['sources']}, locations: {c['locations']}")

    # Save new deduplicated snapshot
    out_path = "data/snapshots/test_snap_1_deduped.json"
    out_data = {
        "metadata": {
            **data.get("metadata", {}),
            "original_count": orig_count,
            "deduped_count": new_count,
            "merged_count": num_merged,
            "total_clusters": len(clusters),
            "dedup_algorithm": "DeduplicationService_Round4",
        },
        "records": canonical_records,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
    print(f"\nSaved updated deduplicated snapshot to {out_path} (preserved original at {snapshot_path}).")


if __name__ == "__main__":
    main()

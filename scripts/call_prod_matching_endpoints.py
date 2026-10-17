import json
import httpx

CAND_A_ID = "91cb0770-b345-420f-b83d-79ba108f4166"
CAND_B_ID = "3386e2b7-fced-4fdd-8276-19baddeeef2c"

client = httpx.Client(base_url="http://localhost:8000", timeout=60.0)

results = {}

for name, rid in [("Candidate A", CAND_A_ID), ("Candidate B", CAND_B_ID)]:
    url = f"/api/v1/matches/resume/{rid}?limit=10"
    print(f"Calling POST {url} for {name}...")
    resp = client.post(url)
    print(f"Status for {name}: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        matches = data.get("matches", [])
        print(f"Returned {len(matches)} matches for {name}:")
        summary_list = []
        for m in matches:
            summary_list.append({
                "rank": m.get("rank"),
                "job_id": m.get("job_id"),
                "title": m.get("title"),
                "company": m.get("company_name"),
                "location": m.get("location"),
                "final_score": m.get("final_score"),
                "composite_score": m.get("composite_score"),
                "xgboost_score": m.get("xgboost_score"),
                "duplicate_count": m.get("duplicate_count"),
                "merged_sources": m.get("merged_sources"),
            })
            print(f"  #{m.get('rank')} | Score: {m.get('final_score'):.4f} | ID: {m.get('job_id')} | Title: {m.get('title')} | Company: {m.get('company_name')} | Sources: {m.get('merged_sources')}")
        results[name] = {
            "resume_id": rid,
            "total_matches": data.get("total_matches"),
            "matches": summary_list,
            "raw_response": data,
        }
    else:
        print(f"Error {resp.status_code}: {resp.text}")

with open("artifacts/experiments/actual_prod_matches_cand_a_cand_b.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\nSaved real responses to artifacts/experiments/actual_prod_matches_cand_a_cand_b.json")

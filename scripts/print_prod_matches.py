import json

with open("artifacts/experiments/actual_prod_matches_cand_a_cand_b.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for name in ["Candidate A", "Candidate B"]:
    res = data[name]
    print(f"=== {name} (Resume ID: {res['resume_id']}) ===")
    print(f"Total matches returned by API: {len(res['matches'])}")
    print(f"Rank | Job ID   | Final Score | UI Fit % | Badge         | Merged Sources       | Title & Company")
    print("-" * 115)
    for m in res["matches"]:
        score = m["final_score"]
        pct = round(score * 100)
        badge = "Strong Fit" if pct >= 80 else ("Moderate Fit" if pct >= 65 else "Stretch Role")
        jid = m["job_id"][:8]
        srcs = ", ".join(m.get("merged_sources") or [])
        title = m["title"][:32]
        comp = (m["company"] or "")[:28]
        print(f"{m['rank']:4d} | {jid} | {score:11.4f} | {pct:7d}% | {badge:13s} | {srcs:20s} | {title} @ {comp}")
    print()

from scripts.job_snapshot import load_snapshot
records, meta = load_snapshot("data/snapshots/test_snap_1.json")
job_map = {str(j.get("id") or j.get("external_id") or ""): j for j in records}
jobs_to_inspect = ["b930acad-41f8-47ac-a912-0c8eb4b6d2ac", "54d2b933-a4f8-4142-9a68-929dba9d89d5", "4b7cb06f-2f90-4297-a25e-3ab507327897", "7a1d1d93-3564-4bf8-be90-951eeebca836", "c4323c9a-84fb-4a87-a25e-3c222ffda588"]

for jid in jobs_to_inspect:
    j = job_map.get(jid)
    if j:
        print(f"=== Job: {j.get('title')} @ {j.get('company')} (ID: {jid}) ===")
        print(f"  Skills: {j.get('skills')}")
        print(f"  Desc snippet: {(j.get('description') or '')[:140]}")

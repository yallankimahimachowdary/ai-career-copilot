import hashlib
import os
import datetime

files = [
    "app/ranking/config.json",
    "data/evaluation/query_intent_benchmark_v1.json",
    "data/evaluation/rag_coach_eval_v1.json",
    "data/router/test.jsonl",
    "data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
    "docs/role_families_frozen.json",
    "docs/eval_scope.json",
]

tag = os.sys.argv[1] if len(os.sys.argv) > 1 else "START"
print(f"=== {tag} FROZEN BENCHMARK FILE HASHES ===")
for f in files:
    h = hashlib.sha256(open(f, "rb").read()).hexdigest().upper()
    print(f"{f}: {h}")

c_path = "data/ingest/adzuna_call_counter.json"
c_hash = hashlib.sha256(open(c_path, "rb").read()).hexdigest().upper()
c_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(c_path), tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
print(f"=== {tag} ADZUNA CALL COUNTER ===")
print(f"{c_path}: {c_hash} | mtime: {c_mtime}")

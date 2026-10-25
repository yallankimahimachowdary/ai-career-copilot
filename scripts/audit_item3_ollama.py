import hashlib
import json
import os
import subprocess
import sys

def main():
    p = "results/dryrun/item3_ollama_stability.json"
    if not os.path.exists(p):
        print(f"ERROR: {p} does not exist")
        sys.exit(1)
        
    with open(p, "rb") as f:
        raw = f.read()
    sha256 = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    mtime = os.path.getmtime(p)
    data = json.loads(raw.decode("utf-8"))
    keys = list(data.keys())

    git_log_proc = subprocess.run(["git", "log", "--all", "--", p], capture_output=True, text=True)
    git_log = git_log_proc.stdout.strip()

    git_status_proc = subprocess.run(["git", "status", "--ignored", p], capture_output=True, text=True)
    git_status = git_status_proc.stdout.strip()

    print(f"FILE: {p}")
    print(f"SHA-256: {sha256}")
    print(f"SIZE: {size} bytes")
    print(f"MTIME: {mtime}")
    print(f"TOP-LEVEL KEYS: {keys}")
    print(f"GIT LOG: {git_log if git_log else '[EMPTY - file never tracked in git]'}")
    print(f"GIT STATUS --IGNORED:\n{git_status}")

if __name__ == "__main__":
    main()

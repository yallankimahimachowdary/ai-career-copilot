import urllib.request
import json
import time

prompt = """Rank 3 jobs for candidate:
Candidate: Python SQL
Jobs:
1. ID: j1, Title: Python Dev
2. ID: j2, Title: Java Dev
3. ID: j3, Title: SQL Analyst
Return JSON:
{"ranked_jobs": [{"job_id": "j1", "rank": 1, "matched_skills": ["Python"], "missing_skills": [], "reason": "Matches python"}]}"""

t0 = time.time()
req = urllib.request.Request(
    'http://localhost:11434/api/generate',
    data=json.dumps({'model': 'llama3.2:3b', 'prompt': prompt, 'format': 'json', 'stream': False}).encode('utf-8')
)
with urllib.request.urlopen(req, timeout=40) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    print('Latency:', round(time.time() - t0, 2))
    print('Response:', res.get('response'))

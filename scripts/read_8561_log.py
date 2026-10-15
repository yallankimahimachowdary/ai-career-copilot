with open(r"C:\Users\mahim\.gemini\antigravity\brain\15e18d94-2bd4-43c5-8807-44e971054719\.system_generated\tasks\task-8561.log", encoding="utf-8", errors="ignore") as f:
    text = f.read()

for line in text.splitlines():
    if any(k in line for k in ["RESULT:", "Status:", "Latency:", "Attempts:", "Repairs:", "Model:", "Top 3"]):
        print(line)

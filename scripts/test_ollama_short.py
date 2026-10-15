import asyncio
import time
from app.services.llm_provider import OllamaProvider

p = OllamaProvider(model="llama3.2:3b")
t0 = time.time()
res = asyncio.run(p.generate_json('Return JSON: {"status": "ok"}', max_tokens=60, timeout=30.0))
print("Latency:", round(time.time() - t0, 2), res.data)

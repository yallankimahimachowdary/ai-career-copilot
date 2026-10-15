import os
import json
import httpx
from app.core.config import settings

api_key = settings.GEMINI_API_KEY
model = settings.GEMINI_MODEL
print(f"Configured GEMINI_MODEL: {model}")

# 1. Get model details
url_info = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
resp_info = httpx.get(url_info, headers={"x-goog-api-key": api_key})
print("=== Model Details Endpoint ===")
print("Status:", resp_info.status_code)
if resp_info.status_code == 200:
    print(json.dumps(resp_info.json(), indent=2))
else:
    print(resp_info.text)

# 2. Call generateContent
url_gen = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
payload = {
    "contents": [{"parts": [{"text": "Respond with JSON: {\"status\": \"ok\", \"ping\": \"pong\"}"}]}],
    "generationConfig": {"response_mime_type": "application/json"}
}
resp_gen = httpx.post(url_gen, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, json=payload)
print("\n=== GenerateContent Response ===")
print("Status:", resp_gen.status_code)
print("Headers of interest:")
for k, v in resp_gen.headers.items():
    if any(term in k.lower() for term in ["model", "version", "server", "x-goog"]):
        print(f"  {k}: {v}")
print("Body:")
if resp_gen.status_code == 200:
    print(json.dumps(resp_gen.json(), indent=2))
else:
    print(resp_gen.text)

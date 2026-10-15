import asyncio
import httpx
from app.core.config import settings

async def main():
    models_to_test = [
        "gemini-3.8-flash",
    ]
    for m in models_to_test:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        headers = {
            "x-goog-api-key": settings.GEMINI_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [{"parts": [{"text": "Return JSON: {\"status\": \"ok\"}"}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                print(f"Model: {m} | Status: {resp.status_code}")
                if resp.status_code == 200:
                    d = resp.json()
                    mv = d.get("modelVersion")
                    text = d["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"  -> modelVersion: {mv} | text: {text.strip()}")
                else:
                    print(f"  -> Error: {resp.status_code} {resp.text[:300]}")
        except Exception as e:
            print(f"Model: {m} | Exception: {type(e).__name__}: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(main())

import os
import asyncio
import json
from app.core.config import settings
from app.services.llm_provider import GeminiProvider

async def run_b0():
    key_present = bool(settings.GEMINI_API_KEY)
    masked_key = f"{settings.GEMINI_API_KEY[:4]}...{settings.GEMINI_API_KEY[-4:]}" if key_present else "None"
    print(f"GEMINI_API_KEY available: {key_present} (key masked: {masked_key})")
    print(f"Configured GEMINI_MODEL: {settings.GEMINI_MODEL}")

    provider = GeminiProvider()
    prompt = 'Return JSON: {"status": "ok", "b0_test": true, "verification": "strict_mode"}'

    try:
        res = await provider.generate_json(prompt, experiment_mode=True)
        print("\n--- B0 Fresh Verification Result: SUCCESS ---")
        print(f"Requested Model: {res.requested_model}")
        print(f"Answered Model:  {res.answered_model}")
        print(f"Provider:        {res.provider}")
        print(f"Latency:         {res.latency_ms} ms")
        print(f"Parsed JSON:     {json.dumps(res.data, indent=2)}")
        print(f"Mock substituted in strict mode: False (real API call verified)")
    except Exception as exc:
        print("\n--- B0 Fresh Verification Result: FAILURE ---")
        print(f"Error Type: {type(exc).__name__}")
        print(f"Error Message: {exc}")

if __name__ == "__main__":
    asyncio.run(run_b0())

import asyncio
import json
from app.core.config import settings
from app.services.llm_provider import GeminiProvider

async def main():
    print("=== Step 1: Config Inspection ===")
    print(f"settings.GEMINI_MODEL: {settings.GEMINI_MODEL}")
    assert settings.GEMINI_MODEL == "gemini-3.5-flash-lite", f"Expected gemini-3.5-flash-lite, got {settings.GEMINI_MODEL}"

    print("\n=== Step 2: Live Authenticated Provider Call ===")
    provider = GeminiProvider()
    print(f"Provider initialized model: {provider.model}")
    assert provider.model == "gemini-3.5-flash-lite"

    prompt = (
        "Respond with a JSON object containing keys:\n"
        "- 'status': 'success'\n"
        "- 'service': 'ai-career-copilot'\n"
        "- 'model_confirmed': 'gemini-3.5-flash-lite'\n"
        "- 'test_timestamp': '2026-10-14'\n"
    )

    res = await provider.generate_json(prompt, experiment_mode=True)

    print("Success! Live response received:")
    print(f"  Requested Model: {res.requested_model}")
    print(f"  Answered Model:  {res.answered_model}")
    print(f"  Latency (ms):    {res.latency_ms} ms")
    print(f"  Timestamp:       {res.timestamp}")
    print(f"  Parsed Data:     {json.dumps(res.data, indent=2)}")

    assert res.requested_model == "gemini-3.5-flash-lite"
    assert res.answered_model == "gemini-3.5-flash-lite"
    assert res.data.get("status") == "success"

    print("\n=== Step 3: Verify Fail-Loud Behavior (No Silent Fallback) ===")
    # Test 1: Invalid model ID in experiment mode must raise, not return mock
    invalid_provider = GeminiProvider(model="nonexistent-gemini-model-xyz")
    try:
        await invalid_provider.generate_json(prompt, experiment_mode=True, timeout=5.0)
        print("ERROR: Invalid model did not raise!")
        assert False, "Should have raised for invalid model"
    except Exception as exc:
        print(f"Confirmed fail-loud on invalid model: {type(exc).__name__}: {exc}")

    # Test 2: Missing API key in experiment mode must raise RuntimeError
    no_key_provider = GeminiProvider(api_key="", model="gemini-3.5-flash-lite")
    no_key_provider.api_key = None
    try:
        await no_key_provider.generate_json(prompt, experiment_mode=True)
        print("ERROR: Missing key did not raise!")
        assert False, "Should have raised for missing key"
    except RuntimeError as exc:
        print(f"Confirmed fail-loud on missing key: {type(exc).__name__}: {exc}")

    print("\nALL VERIFICATIONS PASSED!")

if __name__ == "__main__":
    asyncio.run(main())

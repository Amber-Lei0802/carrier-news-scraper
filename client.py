"""
Gemini AI client with model fallback chain.
Handles rate limiting, quota exhaustion, and JSON parsing.
"""
import os
import json
import time
from typing import Optional

_last_call = 0.0

# Fallback chain — ordered by speed / cost preference
MODEL_FALLBACK = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
]


def generate(
    prompt: str,
    model: str = "",
    rate_limit: float = 7.0,
    max_output_tokens: int = 2048,
    temperature: float = 0.3,
) -> dict:
    """
    Call Gemini API with auto-fallback on 429/quota exhaustion.

    Args:
        prompt: The full prompt text.
        model: Preferred model name (falls back through the chain on failure).
        rate_limit: Minimum seconds between API calls.
        max_output_tokens: Maximum tokens in the response.
        temperature: Sampling temperature.

    Returns:
        Parsed JSON dict on success, empty dict on failure.
        If the response is not JSON (e.g. plain text), returns {"text": raw_text}.
    """
    global _last_call
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[AI] WARNING: GEMINI_API_KEY not set — skipping enrichment")
        return {}

    # Rate limiting
    elapsed = time.time() - _last_call
    if elapsed < rate_limit:
        time.sleep(rate_limit - elapsed)
    _last_call = time.time()

    # Build model priority list
    if model and model in MODEL_FALLBACK:
        models = [model] + [m for m in MODEL_FALLBACK if m != model]
    else:
        models = list(MODEL_FALLBACK)

    for m in models:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{m}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "topP": 0.95,
                "topK": 40,
            },
        }

        try:
            import requests
            resp = requests.post(url, json=payload, timeout=60)

            if resp.status_code == 200:
                result = _parse_response(resp)
                if result:
                    return result
                # Empty result — try next model
                continue

            if resp.status_code in (429, 403, 500, 503):
                # Rate limit / quota / server error — try next model
                time.sleep(2)
                continue

            # Other errors — log and stop
            print(f"[AI] API error ({m}): HTTP {resp.status_code}")
            try:
                print(f"     {resp.text[:300]}")
            except Exception:
                pass
            return {}

        except Exception as e:
            print(f"[AI] Request failed ({m}): {e}")
            time.sleep(1)
            continue

    print("[AI] All models exhausted")
    return {}


def _parse_response(resp) -> dict:
    """Parse Gemini API response and extract text / JSON."""
    try:
        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
    except (KeyError, IndexError, ValueError) as e:
        print(f"[AI] Response parse error: {e}")
        return {}

    if not text:
        return {}

    # Try to extract JSON if present
    json_text = _extract_json(text)
    if json_text:
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    # Return as raw text
    return {"text": text}


def _extract_json(text: str) -> Optional[str]:
    """Try to find a JSON object or array in the text."""
    # Direct JSON
    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        return stripped

    # Code-fenced JSON
    if "```json" in stripped:
        start = stripped.find("```json") + 7
        end = stripped.find("```", start)
        if end > start:
            return stripped[start:end].strip()

    if "```" in stripped:
        start = stripped.find("```") + 3
        # skip language label on first line
        first_newline = stripped.find("\n", start)
        if first_newline > 0:
            start = first_newline + 1
        end = stripped.find("```", start)
        if end > start:
            return stripped[start:end].strip()

    return None

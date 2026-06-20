"""
KiranaGPT LLM Wrapper — Google Gemini 1.5 Flash (FREE tier)

Supports both:
  - call_llm()        : standard single response (JSON or text)
  - stream_llm()      : async generator, yields text chunks token by token

Free quota: 15 req/min, 1500 req/day. Get key: https://aistudio.google.com
"""

import os, json, asyncio, logging, urllib.request, urllib.error
from typing import Union, AsyncGenerator

logger = logging.getLogger(__name__)

GEMINI_MODEL   = "gemini-2.5-flash"
BASE_URL       = "https://generativelanguage.googleapis.com/v1beta/models"
GENERATE_URL   = f"{BASE_URL}/{GEMINI_MODEL}:generateContent"
STREAM_URL     = f"{BASE_URL}/{GEMINI_MODEL}:streamGenerateContent"


def _key() -> str:
    try:
        from dotenv import load_dotenv
        dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        load_dotenv(dotenv_path=dotenv_path, override=True)
    except Exception:
        pass
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise ValueError("GEMINI_API_KEY not set. Get free key: https://aistudio.google.com")
    return k


def _payload(system: str, user: str, max_tokens: int, temperature: float = 0.3, json_mode: bool = False) -> dict:
    config = {"maxOutputTokens": max_tokens, "temperature": temperature, "candidateCount": 1}
    if json_mode:
        config["responseMimeType"] = "application/json"
    return {
        "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n---\n\n{user}"}]}],
        "generationConfig": config,
    }


def _parse_json(text: str) -> Union[dict, str]:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
    try:
        return json.loads(clean.strip())
    except json.JSONDecodeError:
        return clean


async def call_llm(system: str, user: str, max_tokens: int = 1200, json_mode: bool = True) -> Union[dict, str]:
    """Single blocking call — returns full response."""
    try:
        key = _key()
    except ValueError as e:
        logger.warning("LLM skipped: %s", e)
        return {"error": str(e), "fallback": True} if json_mode else f"[{e}]"

    payload = _payload(system, user, max_tokens, json_mode=json_mode)
    try:
        loop = asyncio.get_event_loop()

        def _sync():
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{GENERATE_URL}?key={key}", data=body,
                headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError(f"No candidates: {data}")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError(f"No parts: {data}")
            return parts[0].get("text", "").strip()

        raw = await loop.run_in_executor(None, _sync)
        return _parse_json(raw) if json_mode else raw

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("Gemini HTTP %d: %s", e.code, body[:300])
        return {"error": f"Gemini {e.code}", "fallback": True} if json_mode else f"[Gemini error {e.code}]"
    except Exception as exc:
        logger.error("Gemini failed: %s", exc)
        return {"error": str(exc), "fallback": True} if json_mode else f"[{exc}]"


async def stream_llm(system: str, user: str, max_tokens: int = 1200) -> AsyncGenerator[str, None]:
    """
    Async generator that yields text chunks as they arrive from Gemini.
    Use with FastAPI StreamingResponse + Server-Sent Events.

    Usage:
        async for chunk in stream_llm(system, user):
            yield f"data: {chunk}\n\n"
    """
    try:
        key = _key()
    except ValueError as e:
        yield f"[Error: {e}]"
        return

    payload = _payload(system, user, max_tokens, temperature=0.4)
    # alt=sse tells Gemini to stream SSE
    url = f"{STREAM_URL}?key={key}&alt=sse"

    try:
        loop = asyncio.get_event_loop()
        # We use a queue: background thread reads SSE lines, puts chunks in queue
        queue: asyncio.Queue = asyncio.Queue()

        def _stream_thread():
            try:
                body = json.dumps(payload).encode()
                req = urllib.request.Request(
                    url, data=body,
                    headers={"Content-Type": "application/json"}, method="POST"
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8").strip()
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    text = parts[0].get("text", "")
                                    if text:
                                        asyncio.run_coroutine_threadsafe(
                                            queue.put(text), loop
                                        )
                        except (json.JSONDecodeError, KeyError):
                            pass
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(queue.put(f"\n[Stream error: {exc}]"), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

        # Run in thread pool
        loop.run_in_executor(None, _stream_thread)

        # Yield chunks as they arrive
        while True:
            chunk = await asyncio.wait_for(queue.get(), timeout=40.0)
            if chunk is None:
                break
            yield chunk

    except asyncio.TimeoutError:
        yield "\n[Stream timed out]"
    except Exception as exc:
        yield f"\n[Stream error: {exc}]"
        logger.error("stream_llm error: %s", exc)

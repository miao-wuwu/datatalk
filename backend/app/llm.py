"""LLM 调用（OpenAI 兼容 /chat/completions，可接 Ollama / DeepSeek / 百炼）。"""

from __future__ import annotations

import httpx

from . import config

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=config.LLM_BASE_URL.rstrip("/"),
            timeout=httpx.Timeout(config.LLM_TIMEOUT, connect=10.0),
        )
    return _client


class LLMError(RuntimeError):
    pass


async def chat(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int = 900,
    stop: list[str] | None = None,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if stop:
        payload["stop"] = stop
    try:
        resp = await client().post("/chat/completions", json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise LLMError(f"模型服务不可用：{exc}") from exc
    if resp.status_code >= 400:
        raise LLMError(f"模型返回 {resp.status_code}：{resp.text[:300]}")
    data = resp.json()
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return {"text": text, "usage": data.get("usage") or {}, "model": data.get("model", config.LLM_MODEL)}


async def health() -> dict:
    headers = {}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    try:
        resp = await client().get("/models", headers=headers, timeout=5.0)
        return {"ok": resp.status_code < 400, "status": resp.status_code, "model": config.LLM_MODEL}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "model": config.LLM_MODEL}
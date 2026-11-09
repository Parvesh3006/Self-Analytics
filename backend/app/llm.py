"""Provider-agnostic LLM layer: local Ollama first, optional free-tier cloud fallback for public data only."""
import json
import re
import time
from collections.abc import Iterator

import httpx

from .config import get_settings

CLOUD = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.5-flash", "gemini_api_key"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "qwen/qwen3.8-27b", "groq_api_key"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "qwen/qwen3-coder:free", "openrouter_api_key"),
}
_THINK = re.compile(r"<think>.*?</think>", re.S)


class LLMUnavailable(Exception):
    pass


def _cloud_config():
    s = get_settings()
    entry = CLOUD.get(s.llm_fallback)
    if not entry:
        return None
    url, model, key_attr = entry
    key = getattr(s, key_attr)
    return (url, model, key) if key else None


_tags_cache: tuple[float, list | None] = (0.0, None)


def _ollama_tags() -> list | None:
    """Installed models, cached briefly so a status page does not hit Ollama once per check."""
    global _tags_cache
    now = time.monotonic()
    if now - _tags_cache[0] > 20:
        try:
            tags = httpx.get(f"{get_settings().ollama_url}/api/tags", timeout=3).json().get("models", [])
        except (httpx.HTTPError, ValueError):
            tags = None
        _tags_cache = (now, tags)
    return _tags_cache[1]


def ollama_ready(model: str | None = None) -> bool:
    tags = _ollama_tags()
    if tags is None:
        return False
    if model is None:
        return True
    return any(m["name"] == model or m["name"].split(":")[0] == model for m in tags)


def status() -> dict:
    s = get_settings()
    return {
        "ollama": ollama_ready(), "assistant_model": ollama_ready(s.ollama_assistant_model), "extract_model": ollama_ready(s.ollama_extract_model),
        "embed_model": ollama_ready(s.ollama_embed_model), "cloud_fallback": s.llm_fallback if _cloud_config() else None,
    }


def complete(prompt: str, *, system: str = "", model: str | None = None, json_mode: bool = False, allow_cloud: bool = True, temperature: float = 0.1) -> str:
    s = get_settings()
    model = model or s.ollama_extract_model
    if ollama_ready(model):
        body = {
            "model": model, "stream": False, "think": False, "options": {"temperature": temperature, "num_ctx": 8192},
            "messages": [*([{"role": "system", "content": system}] if system else []), {"role": "user", "content": prompt}],
        }
        if json_mode:
            body["format"] = "json"
        response = httpx.post(f"{s.ollama_url}/api/chat", json=body, timeout=240)
        response.raise_for_status()
        return _THINK.sub("", response.json()["message"]["content"]).strip()
    cloud = _cloud_config() if allow_cloud else None
    if not cloud:
        raise LLMUnavailable("No local model and no cloud fallback available")
    url, cloud_model, key = cloud
    body = {
        "model": cloud_model, "temperature": temperature,
        "messages": [*([{"role": "system", "content": system}] if system else []), {"role": "user", "content": prompt}],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    response = httpx.post(url, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=120)
    response.raise_for_status()
    return _THINK.sub("", response.json()["choices"][0]["message"]["content"]).strip()


def complete_json(prompt: str, **kwargs) -> dict:
    raw = complete(prompt, json_mode=True, **kwargs)
    match = re.search(r"\{.*\}", raw, re.S)
    return json.loads(match.group(0)) if match else {}


def stream(prompt: str, *, system: str = "", allow_cloud: bool = True, temperature: float = 0.2) -> Iterator[str]:
    s = get_settings()
    if ollama_ready(s.ollama_assistant_model):
        body = {
            "model": s.ollama_assistant_model, "stream": True, "think": False, "options": {"temperature": temperature, "num_ctx": 8192},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        with httpx.stream("POST", f"{s.ollama_url}/api/chat", json=body, timeout=300) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    piece = json.loads(line).get("message", {}).get("content", "")
                    if piece:
                        yield piece
        return
    yield complete(prompt, system=system, allow_cloud=allow_cloud, temperature=temperature)


def embed(texts: list[str]) -> list[list[float]] | None:
    """Local only: job text and CVs are embedded on this machine. Returns None if the model is unavailable."""
    s = get_settings()
    if not texts or not ollama_ready(s.ollama_embed_model):
        return None
    response = httpx.post(f"{s.ollama_url}/api/embed", json={"model": s.ollama_embed_model, "input": texts, "truncate": True}, timeout=600)
    response.raise_for_status()
    return response.json()["embeddings"]

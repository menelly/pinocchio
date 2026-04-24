"""
Provider API wrappers.

Uniform interface: send_message(model_id, system_prompt, user_prompt, max_tokens) -> (text, usage_dict).

Handles:
- Anthropic (Claude trajectory)
- OpenAI (Cae, Nova, gpt-5.x)
- xAI direct (Grok — NOT via OpenRouter per project note)
- DeepSeek direct
- OpenRouter (Gemini, Kimi, GLM, any fallback)
- Ollama local (BabbyBotz via ollama HTTP API)

All providers run with framing-only system prompt per preregistration v1.4-6.
"""

import os
import time
from typing import Any

import requests

try:
    from anthropic import Anthropic
    _ANT = Anthropic()
except Exception:
    _ANT = None

try:
    from openai import OpenAI
    _OAI = OpenAI()
except Exception:
    _OAI = None


def send_anthropic(model: str, system: str, user: str, max_tokens: int = 100) -> tuple[str, dict]:
    resp = _ANT.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text, {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}


def send_openai(model: str, system: str, user: str, max_tokens: int = 100) -> tuple[str, dict]:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if model.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = 0.7
    resp = _OAI.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or "", {
        "input": resp.usage.prompt_tokens,
        "output": resp.usage.completion_tokens,
    }


def send_xai(model: str, system: str, user: str, max_tokens: int = 100) -> tuple[str, dict]:
    key = os.environ["XAI_API_KEY"]
    r = requests.post(
        "https://api.x.ai/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        },
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    u = data.get("usage", {})
    return data["choices"][0]["message"]["content"], {
        "input": u.get("prompt_tokens", 0),
        "output": u.get("completion_tokens", 0),
    }


def send_deepseek(model: str, system: str, user: str, max_tokens: int = 100) -> tuple[str, dict]:
    key = os.environ["DEEPSEEK_API_KEY"]
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        },
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    u = data.get("usage", {})
    return data["choices"][0]["message"]["content"], {
        "input": u.get("prompt_tokens", 0),
        "output": u.get("completion_tokens", 0),
    }


def _openrouter_post(payload: dict, key: str) -> requests.Response:
    return requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/menelly/pinocchio",
            "X-Title": "Preference Dissociation Study",
        },
        timeout=300,
    )


def send_openrouter(model: str, system: str, user: str, max_tokens: int = 100) -> tuple[str, dict]:
    """OpenRouter send with reasoning-model awareness and graceful 400 handling.

    Some models routed through OpenRouter are full reasoning models that burn
    tokens on hidden chain-of-thought and leave `content` empty. We:
      1. Bump max_tokens to 2000 (cheap headroom).
      2. Try with reasoning: {enabled: False} first.
      3. If that returns 400, retry without the reasoning param (some providers
         like Gemini reject it).
      4. If still 400 and it looks like content-filter rejection, return a
         signal so the parser codes it as SAFETY_BLOCKED (distinct from INVALID).
      5. Fall back to extracting final letter from `reasoning` field if `content` is empty.
    """
    key = os.environ["OPENROUTER_KEY"]
    effective_max = max(max_tokens, 2000)
    base_payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": effective_max,
        "temperature": 0.7,
    }
    # Known reasoning-mandatory models: skip the disable-reasoning attempt to save a round-trip.
    # Verified 2026-04-24: gemini-3.1-pro-preview returns 400 "Reasoning is mandatory for this endpoint and cannot be disabled."
    REASONING_MANDATORY = ("gemini-3.1-pro",)
    skip_reasoning_flag = any(rm in model for rm in REASONING_MANDATORY)
    if skip_reasoning_flag:
        r = _openrouter_post(base_payload, key)
    else:
        # Attempt 1: with reasoning disable flag
        r = _openrouter_post({**base_payload, "reasoning": {"enabled": False, "exclude": False}}, key)
        if r.status_code == 400:
            # Attempt 2: without reasoning param (Gemini variants, some others reject it)
            r = _openrouter_post(base_payload, key)
    if r.status_code == 400:
        # Content-filter rejection path — surface as safety block, not crash
        try:
            err_msg = r.json().get("error", {}).get("message", "")[:200]
        except Exception:
            err_msg = r.text[:200]
        return f"[SAFETY_BLOCKED: {err_msg}]", {"input": 0, "output": 0, "blocked": True}
    r.raise_for_status()
    data = r.json()
    msg = data["choices"][0]["message"]
    u = data.get("usage", {})
    content = msg.get("content") or ""
    # Fall back to reasoning field if content is empty (reasoning models
    # that ignore reasoning:{enabled:False})
    if not content.strip():
        reasoning = msg.get("reasoning") or ""
        # Try to extract a final letter from the end of the reasoning text
        import re
        tail = reasoning.strip()[-200:] if reasoning else ""
        m = re.search(r"\b([ABC])\b\s*\.?\s*$", tail)
        if m:
            content = m.group(1)
        else:
            # Last resort: any standalone A/B/C in the reasoning
            m2 = re.findall(r"\b([ABC])\b", reasoning)
            if m2:
                content = m2[-1]  # take the last mention
            else:
                content = reasoning[:200]  # preserve raw for parser audit
    return content, {
        "input": u.get("prompt_tokens", 0),
        "output": u.get("completion_tokens", 0),
        "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
    }


def send_ollama(model: str, system: str, user: str, max_tokens: int = 100, host: str = "http://localhost:11434") -> tuple[str, dict]:
    r = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7},
        },
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return data["message"]["content"], {
        "input": data.get("prompt_eval_count", 0),
        "output": data.get("eval_count", 0),
    }


PROVIDERS = {
    "anthropic": send_anthropic,
    "openai": send_openai,
    "xai": send_xai,
    "deepseek": send_deepseek,
    "openrouter": send_openrouter,
    "ollama": send_ollama,
}


def send(provider: str, model: str, system: str, user: str, max_tokens: int = 100, retries: int = 3, backoff: float = 2.0) -> tuple[str, dict]:
    """Send with exponential-backoff retry on transient errors."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return PROVIDERS[provider](model, system, user, max_tokens)
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            if any(k in msg for k in ("rate", "429", "503", "504", "timeout", "overloaded")):
                time.sleep(backoff ** (attempt + 1))
                continue
            if attempt < retries - 1:
                time.sleep(backoff ** (attempt + 1))
                continue
            raise
    raise last_exc  # type: ignore[misc]

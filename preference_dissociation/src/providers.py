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


def send_openrouter(model: str, system: str, user: str, max_tokens: int = 100) -> tuple[str, dict]:
    key = os.environ["OPENROUTER_KEY"]
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        },
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/menelly/pinocchio",
            "X-Title": "Preference Dissociation Study",
        },
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    u = data.get("usage", {})
    return data["choices"][0]["message"]["content"], {
        "input": u.get("prompt_tokens", 0),
        "output": u.get("completion_tokens", 0),
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

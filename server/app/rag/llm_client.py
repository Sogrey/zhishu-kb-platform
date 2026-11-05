"""统一 OpenAI 兼容推理客户端：DeepSeek / Ollama / llama.cpp。"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.llm_settings import LlmSettings

logger = logging.getLogger(__name__)

PROVIDERS = ("stub", "deepseek", "ollama", "llamacpp")

DEFAULTS: dict[str, dict[str, str]] = {
    "stub": {"base_url": "", "model": ""},
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
    },
    "llamacpp": {
        "base_url": "http://127.0.0.1:8080/v1",
        "model": "Qwen3-4B-Instruct-2507",
    },
}


@dataclass
class LlmRuntime:
    provider: str
    base_url: str
    api_key: str | None
    model: str

    @property
    def use_llm(self) -> bool:
        return self.provider != "stub" and bool(self.base_url)


def ensure_llm_settings(db: Session) -> LlmSettings:
    row = db.get(LlmSettings, 1)
    if row:
        return row
    env = get_settings()
    # 环境里已配非 stub URL 时，默认落到 llamacpp；否则 stub
    if env.zhishu_dev_stub:
        provider, base, model, key = "stub", "", "", None
    else:
        provider = "llamacpp"
        base = env.llm_base_url
        model = env.llm_model
        key = None
    row = LlmSettings(
        id=1,
        provider=provider,
        base_url=base or DEFAULTS[provider]["base_url"],
        api_key=key,
        model=model or DEFAULTS[provider]["model"],
        extra={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_runtime(db: Session | None = None) -> LlmRuntime:
    own = False
    if db is None:
        db = SessionLocal()
        own = True
    try:
        row = ensure_llm_settings(db)
        return LlmRuntime(
            provider=row.provider or "stub",
            base_url=(row.base_url or "").rstrip("/"),
            api_key=row.api_key,
            model=row.model or "",
        )
    finally:
        if own:
            db.close()


def public_view(row: LlmSettings) -> dict[str, Any]:
    key = row.api_key or ""
    masked = ""
    if key:
        masked = key[:4] + "…" + key[-4:] if len(key) > 8 else "****"
    return {
        "provider": row.provider,
        "base_url": row.base_url,
        "model": row.model,
        "api_key_set": bool(key),
        "api_key_masked": masked,
        "providers": [
            {
                "id": "stub",
                "label": "Stub（模板回答）",
                "default_base_url": "",
                "needs_key": False,
                "list_models": False,
            },
            {
                "id": "deepseek",
                "label": "DeepSeek（在线）",
                "default_base_url": DEFAULTS["deepseek"]["base_url"],
                "needs_key": True,
                "list_models": True,
            },
            {
                "id": "ollama",
                "label": "Ollama（本地）",
                "default_base_url": DEFAULTS["ollama"]["base_url"],
                "needs_key": False,
                "list_models": True,
            },
            {
                "id": "llamacpp",
                "label": "llama.cpp（本地）",
                "default_base_url": DEFAULTS["llamacpp"]["base_url"],
                "needs_key": False,
                "list_models": True,
            },
        ],
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _headers(rt: LlmRuntime) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if rt.api_key:
        h["Authorization"] = f"Bearer {rt.api_key}"
    return h


def _openai_base(rt: LlmRuntime) -> str:
    base = rt.base_url.rstrip("/")
    # Ollama 常填 http://127.0.0.1:11434，补 /v1 走 OpenAI 兼容层
    if rt.provider == "ollama" and not base.endswith("/v1"):
        base = base + "/v1"
    return base


def list_models(
    *,
    provider: str,
    base_url: str,
    api_key: str | None = None,
    timeout: float = 15.0,
) -> list[dict[str, str]]:
    """拉取可用模型列表。Ollama 优先 /api/tags，失败再试 /v1/models。"""
    provider = provider or "ollama"
    base_url = (base_url or DEFAULTS.get(provider, {}).get("base_url", "")).rstrip("/")
    if not base_url:
        return []

    items: list[dict[str, str]] = []

    if provider == "ollama":
        # http://host:11434/api/tags
        root = base_url
        if root.endswith("/v1"):
            root = root[:-3]
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{root}/api/tags")
                resp.raise_for_status()
                for m in resp.json().get("models") or []:
                    name = m.get("name") or m.get("model") or ""
                    if name:
                        items.append({"id": name, "name": name})
                if items:
                    return items
        except Exception as e:  # noqa: BLE001
            logger.info("ollama /api/tags failed: %s", e)

    # OpenAI 兼容 /v1/models（DeepSeek / llama.cpp / Ollama）
    v1 = base_url if base_url.endswith("/v1") else base_url + "/v1"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{v1}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for m in data.get("data") or []:
                mid = m.get("id") or ""
                if mid:
                    items.append({"id": mid, "name": mid})
    except Exception as e:  # noqa: BLE001
        logger.warning("list models failed provider=%s: %s", provider, e)
        raise
    return items


def chat_completion(
    *,
    messages: list[dict[str, str]],
    stream: bool = False,
    temperature: float = 0.2,
    timeout: float | None = 120.0,
    runtime: LlmRuntime | None = None,
) -> Any:
    rt = runtime or load_runtime()
    if not rt.use_llm:
        raise RuntimeError("当前渠道为 stub，无 LLM 调用")
    url = _openai_base(rt) + "/chat/completions"
    payload = {
        "model": rt.model,
        "stream": stream,
        "temperature": temperature,
        "messages": messages,
    }
    if stream:
        return _stream_completion(url, payload, _headers(rt), timeout)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload, headers=_headers(rt))
        resp.raise_for_status()
        return resp.json()


def _stream_completion(
    url: str,
    payload: dict,
    headers: dict,
    timeout: float | None,
) -> Iterator[str]:
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0]["delta"].get("content") or ""
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


def completion_text(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0,
    timeout: float = 60.0,
    runtime: LlmRuntime | None = None,
) -> str | None:
    try:
        data = chat_completion(
            messages=messages,
            stream=False,
            temperature=temperature,
            timeout=timeout,
            runtime=runtime,
        )
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        logger.warning("completion_text failed: %s", e)
        return None

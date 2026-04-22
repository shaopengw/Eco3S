from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, Union

from camel.configs import ChatGPTConfig
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.utils import OpenAITokenCounter
import requests


OLLAMA_GENERATE_PLATFORM = "OLLAMA_GENERATE"


def _as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: List[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if text is not None:
                    out.append(str(text))
            else:
                out.append(str(part))
        return "\n".join(out)
    return str(content)


def _resp(content: Any):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _require_url(model_config: Dict[str, Any], name: str) -> str:
    url = model_config.get("url")
    if not url:
        raise ValueError(f"{name} 后端需要配置 url")
    return str(url).rstrip("/")


def _run_ollama(url: str, model: str, model_cfg: Dict[str, Any], messages: List[Dict[str, Any]]):
    lines = []
    for msg in messages:
        role = (msg.get("role") or "user").strip().lower()
        content = _as_text(msg.get("content"))
        if not content:
            continue
        lines.append(f"{role.title()}: {content}")
    if lines and not lines[-1].startswith("Assistant:"):
        lines.append("Assistant:")

    payload: Dict[str, Any] = {"model": model, "prompt": "\n".join(lines), "stream": False}
    options = {
        k: model_cfg[k]
        for k in ("temperature", "top_p", "top_k", "num_predict", "seed")
        if k in model_cfg and model_cfg[k] is not None
    }
    if options:
        payload["options"] = options
    if model_cfg.get("stop"):
        payload["stop"] = model_cfg["stop"]

    resp = requests.post(f"{url}/api/generate", json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama /api/generate failed: {resp.status_code} {resp.text}")
    return _resp((resp.json() or {}).get("response"))


def _extract_path(data: Dict[str, Any], path: str) -> Any:
    cur: Any = data
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _run_chat(
    url: str,
    model: str,
    model_cfg: Dict[str, Any],
    messages: List[Dict[str, Any]],
    endpoint_path: str,
    api_key: Optional[str],
    extra_headers: Dict[str, str],
    payload_defaults: Dict[str, Any],
    fallback_paths: List[str],
):
    payload: Dict[str, Any] = {"model": model, "messages": messages, "stream": False, **payload_defaults}
    for k, v in model_cfg.items():
        if k not in {"model", "messages", "stream"} and v is not None and k not in payload:
            payload[k] = v

    headers = {"Content-Type": "application/json", **extra_headers}
    if api_key and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.post(
        f"{url}{endpoint_path}",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Chat completions request failed: {resp.status_code} {resp.text}")

    data = resp.json()
    content = None
    choices = data.get("choices") or []
    if choices:
        first = choices[0] or {}
        msg = first.get("message") or {}
        content = msg.get("content") or first.get("text")
    if content is None:
        for path in fallback_paths:
            content = _extract_path(data, path)
            if content is not None:
                break
    if content is None:
        content = data.get("content")
    if content is None:
        content = _as_text(data)
    return _resp(content)


def _resolve_model_type(model_platform: Any, model_type_raw: str) -> Union[ModelType, str]:
    if model_platform == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
        return model_type_raw
    if isinstance(model_platform, str):
        return model_type_raw
    try:
        return ModelType(model_type_raw)
    except Exception:
        return model_type_raw


def create_backend_from_model_config(
    model_config: Dict[str, Any],
) -> Tuple[Any, Union[ModelType, str], OpenAITokenCounter, ModelType]:
    model_platform = model_config["model_platform"]
    model_type = _resolve_model_type(model_platform, model_config["model_type"])

    if isinstance(model_type, str):
        token_counter = OpenAITokenCounter(ModelType.GPT_4O_MINI)
        memory_model_type = ModelType.GPT_4O_MINI
    else:
        token_counter = OpenAITokenCounter(model_type)
        memory_model_type = model_type

    backend_type = (model_config.get("backend_type") or "").strip().lower()
    if not backend_type:
        if model_platform == OLLAMA_GENERATE_PLATFORM:
            backend_type = "ollama_generate"
        elif isinstance(model_platform, str) and model_platform.endswith("_CHAT_COMPLETIONS"):
            backend_type = "chat_completions"

    url = _require_url(model_config, backend_type or "model") if backend_type in {"ollama_generate", "chat_completions"} else None
    model_cfg = model_config.get("model_config") or {}

    if backend_type == "ollama_generate":
        backend = SimpleNamespace(
            backend_kind="ollama_generate",
            rate_limit_key=None,
            run=lambda messages: _run_ollama(url, str(model_type), model_cfg, messages),
        )
        return backend, model_type, token_counter, memory_model_type

    if backend_type == "chat_completions":
        backend = SimpleNamespace(
            backend_kind="chat_completions",
            rate_limit_key=model_config.get("rate_limit_key"),
            run=lambda messages: _run_chat(
                url=url,
                model=str(model_type),
                model_cfg=model_cfg,
                messages=messages,
                endpoint_path=model_config.get("endpoint_path") or "/chat/completions",
                api_key=model_config.get("api_key"),
                extra_headers=model_config.get("extra_headers") or {},
                payload_defaults=model_config.get("payload_defaults") or {},
                fallback_paths=model_config.get("response_fallback_paths") or [],
            ),
        )
        return backend, model_type, token_counter, memory_model_type

    if backend_type:
        raise ValueError(f"未知 backend_type: {backend_type}")

    model_cfg_obj = ChatGPTConfig(**model_cfg)
    params: Dict[str, Any] = {
        "model_platform": model_platform,
        "model_type": model_type,
        "model_config_dict": model_cfg_obj.as_dict(),
    }
    if model_platform == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
        params["url"] = model_config.get("url")
        params["api_key"] = model_config.get("api_key")

    return ModelFactory.create(**params), model_type, token_counter, memory_model_type

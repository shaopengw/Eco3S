import json
import os
import random
from pathlib import Path
from typing import Any, Dict, Optional

from camel.types import ModelPlatformType
from dotenv import load_dotenv
import yaml

load_dotenv()

RUNTIME_KEYS = (
    "url",
    "api_key",
    "backend_type",
    "endpoint_path",
    "rate_limit_key",
    "extra_headers",
    "payload_defaults",
    "response_fallback_paths",
)

DEFAULT_RATE_LIMIT_PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {"max_concurrency": 0, "rpm_limit": 0, "window_seconds": 60},
}


class ModelManager:
    """统一的模型管理器，用于管理不同的模型 API"""
    def __init__(self):
        config = self._load_api_models_config()

        env_catalog_json = os.getenv("AGENTWORLD_MODEL_CATALOG_JSON")
        raw_catalog = json.loads(env_catalog_json) if env_catalog_json else (config.get("models") or {})
        self.available_models = self._normalize_catalog(raw_catalog)
        self.rate_limit_profiles = self._normalize_rate_limit_profiles(config.get("rate_limits") or {})

        cfg = {"temperature": 1}
        raw_cfg = os.getenv("AGENTWORLD_DEFAULT_MODEL_CONFIG_JSON")
        if raw_cfg:
            parsed = json.loads(raw_cfg)
            if isinstance(parsed, dict):
                cfg.update(parsed)
        self.model_config = cfg

    @staticmethod
    def _parse_platform(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if not raw:
            return value

        by_name = ModelPlatformType.__members__.get(raw.upper())
        if by_name is not None:
            return by_name

        try:
            return ModelPlatformType(raw)
        except Exception:
            return raw

    @staticmethod
    def _to_model_types(value: Any) -> list[str]:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _to_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _load_api_models_config(self) -> Dict[str, Any]:
        explicit_path = os.getenv("AGENTWORLD_API_MODELS_CONFIG_FILE")
        if explicit_path:
            return self._load_yaml(Path(explicit_path))

        return self._load_yaml(Path("config/api_models_config.yaml"))

    def _normalize_catalog(self, catalog: Any) -> Dict[str, Dict[str, Any]]:
        if not isinstance(catalog, dict):
            raise ValueError("api_models_config.yaml 中 models 必须是对象")

        out: Dict[str, Dict[str, Any]] = {}
        for api_name, info in catalog.items():
            api_info = dict(info or {})
            model_types = self._to_model_types(api_info.get("model_types") or api_info.get("models"))
            if not model_types:
                raise ValueError(f"模型配置 {api_name} 缺少 model_types")

            item: Dict[str, Any] = {
                "model_types": model_types,
                "model_platform": self._parse_platform(api_info.get("model_platform")),
                "allow_random": bool(api_info.get("allow_random", True)),
                "allow_external_model_type": bool(api_info.get("allow_external_model_type", False)),
            }
            for key in RUNTIME_KEYS:
                if api_info.get(key) is not None:
                    item[key] = api_info[key]

            if item.get("url") is None and api_info.get("url_env"):
                item["url"] = os.getenv(str(api_info["url_env"]))
            if item.get("api_key") is None and api_info.get("api_key_env"):
                item["api_key"] = os.getenv(str(api_info["api_key_env"]))

            out[str(api_name)] = item
        return out

    def _normalize_rate_limit_profiles(self, profiles: Any) -> Dict[str, Dict[str, Any]]:
        result = dict(DEFAULT_RATE_LIMIT_PROFILES)
        if isinstance(profiles, dict):
            for key, raw in profiles.items():
                if not isinstance(raw, dict):
                    continue
                result[str(key)] = {
                    "max_concurrency": self._to_int(raw.get("max_concurrency", 0), 0),
                    "rpm_limit": self._to_int(raw.get("rpm_limit", 0), 0),
                    "window_seconds": self._to_float(raw.get("window_seconds", 60), 60),
                }
        return result

    def get_rate_limit_profiles(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.rate_limit_profiles)

    def _build(self, api_info: Dict[str, Any], model_type: str) -> Dict[str, Any]:
        cfg = {
            "model_platform": api_info["model_platform"],
            "model_type": model_type,
            "model_config": self.model_config.copy(),
        }
        for key in RUNTIME_KEYS:
            if api_info.get(key) is not None:
                cfg[key] = api_info[key]
        return cfg

    def get_random_model_config(self):
        candidates = [v for v in self.available_models.values() if v.get("allow_random", True)]
        if not candidates:
            raise ValueError("没有可供随机选择的模型")
        api_info = random.choice(candidates)
        return self._build(api_info, random.choice(api_info["model_types"]))

    def get_specific_model_config(self, api_name, model_type=None):
        if api_name not in self.available_models:
            raise ValueError(f"未找到API: {api_name}，可用的API: {list(self.available_models.keys())}")
        api_info = self.available_models[api_name]
        model_type = model_type or api_info["model_types"][0]
        if model_type not in api_info["model_types"] and not api_info.get("allow_external_model_type", False):
            raise ValueError(f"模型 {model_type} 不在 {api_name} 的可用模型列表中: {api_info['model_types']}")
        return self._build(api_info, model_type)

    def get_model_config_by_type(self, model_type: str, preferred_api_name: Optional[str] = None):
        if preferred_api_name:
            return self.get_specific_model_config(preferred_api_name, model_type)
        for name, info in self.available_models.items():
            if model_type in info.get("model_types", []):
                return self.get_specific_model_config(name, model_type)
        for name, info in self.available_models.items():
            if info.get("allow_external_model_type", False):
                return self.get_specific_model_config(name, model_type)
        raise ValueError(f"未找到模型 {model_type}，且没有开启 allow_external_model_type 的 API。")

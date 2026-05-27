import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".duomoliao"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "default_model": "deepseek/v4",
    "api_keys": {},
    "models": {
        "openai/gpt-4o": {"backend": "openai", "model": "gpt-4o"},
        "openai/gpt-4.1": {"backend": "openai", "model": "gpt-4.1"},
        "claude/opus-4-7": {"backend": "claude", "model": "claude-opus-4-7-20251014"},
        "claude/sonnet-4-6": {"backend": "claude", "model": "claude-sonnet-4-6"},
        "gemini/2.5-pro": {"backend": "gemini", "model": "gemini-2.5-pro"},
        "gemini/2.5-flash": {"backend": "gemini", "model": "gemini-2.5-flash"},
        "deepseek/v4": {"backend": "deepseek", "model": "deepseek-chat"},
        "deepseek/r1": {"backend": "deepseek", "model": "deepseek-reasoner"},
    },
}

ENV_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    if "api_keys" not in merged:
        merged["api_keys"] = {}
    return merged


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_api_key(config, backend_name):
    # 优先环境变量，其次配置文件
    env_var = ENV_KEY_MAP.get(backend_name)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    return config.get("api_keys", {}).get(backend_name)


def get_default_model(config):
    return config.get("default_model", "openai/gpt-4o")


def get_model_info(config, model_key):
    return config.get("models", {}).get(model_key)


def set_api_key(config, backend_name, key):
    config.setdefault("api_keys", {})[backend_name] = key
    save_config(config)
    config["api_keys"][backend_name] = key

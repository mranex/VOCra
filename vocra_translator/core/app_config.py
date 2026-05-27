from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


SETTINGS_FILENAME = "settings.json"
SECRETS_FILENAME = "secrets.json"


def load_global_config() -> dict[str, Any]:
    config = _default_config()
    settings_path = global_settings_path()
    secrets_path = global_secrets_path()

    if settings_path.exists():
        with settings_path.open("r", encoding="utf-8") as handle:
            saved = json.load(handle)
        if isinstance(saved, dict):
            config["translator"].update(saved.get("translator", {}))

    if secrets_path.exists():
        with secrets_path.open("r", encoding="utf-8") as handle:
            saved = json.load(handle)
        translator = saved.get("translator", {})
        if isinstance(translator, dict):
            config["translator"]["api_key"] = str(translator.get("api_key", "") or "")

    env_api_key = str(os.environ.get("VOCRA_TRANSLATOR_APP_API_KEY", "") or "").strip()
    if env_api_key:
        config["translator"]["api_key"] = env_api_key
    return config


def save_global_config(config: dict[str, Any]) -> None:
    normalized = _default_config()
    normalized["translator"].update(config.get("translator", {}))

    config_dir = global_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    settings_payload = deepcopy(normalized)
    settings_payload["translator"].pop("api_key", None)
    with global_settings_path().open("w", encoding="utf-8") as handle:
        json.dump(settings_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    secrets_payload = {"translator": {"api_key": str(normalized["translator"].get("api_key", "") or "")}}
    with global_secrets_path().open("w", encoding="utf-8") as handle:
        json.dump(secrets_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def merge_project_translator_defaults(project_translator: dict[str, Any], global_config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(_default_config()["translator"])
    merged.update(global_config.get("translator", {}))
    merged.update(project_translator or {})
    if not merged.get("api_key"):
        merged["api_key"] = str(global_config.get("translator", {}).get("api_key", "") or "")
    return merged


def global_config_dir() -> Path:
    override = str(os.environ.get("VOCRA_TRANSLATOR_CONFIG_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    appdata = str(os.environ.get("APPDATA", "") or "").strip()
    if appdata:
        return (Path(appdata) / "VoCRATranslator").resolve()
    return (Path.home() / ".config" / "VoCRATranslator").resolve()


def global_settings_path() -> Path:
    return global_config_dir() / SETTINGS_FILENAME


def global_secrets_path() -> Path:
    return global_config_dir() / SECRETS_FILENAME


def _default_config() -> dict[str, Any]:
    defaults_path = Path(__file__).resolve().parents[2] / "vocra_core" / "default_config.json"
    with defaults_path.open("r", encoding="utf-8") as handle:
        defaults = json.load(handle)
    return {
        "translator": deepcopy(defaults.get("translator", {})),
    }

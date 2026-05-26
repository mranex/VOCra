from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


_SETTINGS_FILENAME = "settings.json"
_SECRETS_FILENAME = "secrets.json"


def load_global_config() -> dict[str, Any]:
    config = _default_global_config()
    settings_path = global_settings_path()
    secrets_path = global_secrets_path()

    if settings_path.exists():
        try:
            with settings_path.open("r", encoding="utf-8") as handle:
                saved = json.load(handle)
            _merge_sections(config, saved)
        except Exception:
            pass

    if secrets_path.exists():
        try:
            with secrets_path.open("r", encoding="utf-8") as handle:
                secrets = json.load(handle)
            translator = secrets.get("translator", {})
            if isinstance(translator, dict):
                config["translator"]["api_key"] = str(translator.get("api_key", "") or "")
        except Exception:
            pass

    env_api_key = str(os.environ.get("VOCRA_TRANSLATOR_API_KEY", "") or "").strip()
    if env_api_key:
        config["translator"]["api_key"] = env_api_key

    return config


def save_global_config(config: dict[str, Any]) -> None:
    normalized = _default_global_config()
    _merge_sections(normalized, config)

    config_dir = global_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    settings_payload = deepcopy(normalized)
    settings_payload.get("translator", {}).pop("api_key", None)
    with global_settings_path().open("w", encoding="utf-8") as handle:
        json.dump(settings_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    secrets_payload = {
        "translator": {
            "api_key": str(normalized.get("translator", {}).get("api_key", "") or ""),
        }
    }
    with global_secrets_path().open("w", encoding="utf-8") as handle:
        json.dump(secrets_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def merge_global_config_into_progress(progress: dict[str, Any], global_config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(progress)

    merged.setdefault("draft_ocr", {})
    merged.setdefault("final_ocr", {})
    merged.setdefault("translator", {})

    draft_config = deepcopy(global_config.get("draft_ocr", {}))
    final_config = deepcopy(global_config.get("final_ocr", {}))
    translator_config = deepcopy(global_config.get("translator", {}))
    translator_config.pop("api_key", None)

    merged["draft_ocr"].update(draft_config)
    merged["final_ocr"].update(final_config)
    merged["translator"].update(translator_config)
    merged["translator"].pop("api_key", None)
    return merged


def global_config_dir() -> Path:
    override_dir = str(os.environ.get("VOCRA_CONFIG_DIR", "") or "").strip()
    if override_dir:
        return Path(override_dir).expanduser().resolve()

    appdata = str(os.environ.get("APPDATA", "") or "").strip()
    if appdata:
        return (Path(appdata) / "VoCRA").resolve()

    return (Path.home() / ".config" / "VoCRA").resolve()


def global_settings_path() -> Path:
    return global_config_dir() / _SETTINGS_FILENAME


def global_secrets_path() -> Path:
    return global_config_dir() / _SECRETS_FILENAME


def _default_global_config() -> dict[str, Any]:
    default_config_path = Path(__file__).with_name("default_config.json")
    with default_config_path.open("r", encoding="utf-8") as handle:
        defaults = json.load(handle)

    return {
        "draft_ocr": {
            "provider": "paddleocr",
            "language": "auto",
        },
        "final_ocr": deepcopy(defaults["final_ocr"]),
        "translator": deepcopy(defaults["translator"]),
    }


def _merge_sections(target: dict[str, Any], source: dict[str, Any]) -> None:
    for section_name in ("draft_ocr", "final_ocr", "translator"):
        source_section = source.get(section_name, {})
        if not isinstance(source_section, dict):
            continue
        target.setdefault(section_name, {})
        target[section_name].update(source_section)

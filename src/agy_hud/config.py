"""Configuration loader, presets, and schema defaults for agy-hud."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_DISPLAY: dict[str, Any] = {
    "showModel": True,
    "showEffort": True,
    "showProject": True,
    "showGit": True,
    "showGitAheadBehind": True,
    "showSessionTitle": True,
    "showContextBar": True,
    "showContextTokens": True,
    "showCacheHit": True,
    "showSessionTokens": True,
    "showQuota": True,
    "showQuotaBar": True,
    "showQuotaReset": True,
    "showStatusBadges": True,
    "showTools": True,
    "showAgents": True,
    "showDuration": False,
    "quotaValueMode": "remaining",  # "remaining" | "used"
    "barStyle": "block",            # "block" | "line" | "dot"
    "contextWarningThreshold": 70,
    "contextCriticalThreshold": 85,
    "quotaWarningThreshold": 50,
    "quotaCriticalThreshold": 20,
    "toolsMaxVisible": 4,
    "agentsMaxVisible": 3,
    "customLine": "",
}

PRESETS: dict[str, dict[str, Any]] = {
    "full": {
        "showModel": True,
        "showEffort": True,
        "showProject": True,
        "showGit": True,
        "showGitAheadBehind": True,
        "showSessionTitle": True,
        "showContextBar": True,
        "showContextTokens": True,
        "showCacheHit": True,
        "showSessionTokens": True,
        "showQuota": True,
        "showQuotaBar": True,
        "showQuotaReset": True,
        "showStatusBadges": True,
        "showTools": True,
        "showAgents": True,
    },
    "essential": {
        "showModel": True,
        "showEffort": True,
        "showProject": True,
        "showGit": True,
        "showGitAheadBehind": False,
        "showSessionTitle": False,
        "showContextBar": True,
        "showContextTokens": True,
        "showCacheHit": False,
        "showSessionTokens": False,
        "showQuota": True,
        "showQuotaBar": True,
        "showQuotaReset": True,
        "showStatusBadges": True,
        "showTools": True,
        "showAgents": True,
    },
    "minimal": {
        "showModel": True,
        "showEffort": True,
        "showProject": False,
        "showGit": False,
        "showGitAheadBehind": False,
        "showSessionTitle": False,
        "showContextBar": True,
        "showContextTokens": False,
        "showCacheHit": False,
        "showSessionTokens": False,
        "showQuota": True,
        "showQuotaBar": True,
        "showQuotaReset": False,
        "showStatusBadges": True,
        "showTools": False,
        "showAgents": False,
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "preset": "full",
    "layout": "expanded",        # "expanded" | "compact"
    "language": "en",            # "en" | "zh-Hans" | "zh-Hant"
    "theme": "auto",             # "auto" | "catppuccin-latte" | "catppuccin-macchiato" | "tokyo-night" | "nord" | "gruvbox-dark" | "ansi"
    "pathLevels": 1,             # 1 | 2 | 3
    "showSeparators": False,
    "display": copy.deepcopy(DEFAULT_DISPLAY),
    "colors": {},
}

VALID_PRESETS = tuple(PRESETS.keys())
VALID_LAYOUTS = ("expanded", "compact")
VALID_LANGUAGES = ("en", "zh-Hans", "zh-Hant")
VALID_THEMES = (
    "auto",
    "catppuccin-latte",
    "catppuccin-macchiato",
    "tokyo-night",
    "nord",
    "gruvbox-dark",
    "ansi",
)


def get_agy_cli_dir() -> Path:
    env_dir = os.environ.get("AGY_CLI_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / ".gemini" / "antigravity-cli"


def get_config_path() -> Path:
    env_cfg = os.environ.get("AGY_HUD_CONFIG", "").strip()
    if env_cfg:
        return Path(env_cfg).expanduser()
    return get_agy_cli_dir() / "agy-hud.json"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def normalize_language(lang: str | None) -> str:
    if not lang:
        return "en"
    low = lang.strip().lower()
    if low in ("zh", "zh-cn", "zh-hans", "zh_cn", "zh_hans"):
        return "zh-Hans"
    if low in ("zh-tw", "zh-hk", "zh-hant", "zh_tw", "zh_hant"):
        return "zh-Hant"
    return "en"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or get_config_path()
    user_raw: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                user_raw = loaded
        except Exception:
            user_raw = {}

    preset_name = str(user_raw.get("preset") or DEFAULT_CONFIG["preset"]).strip().lower()
    if preset_name not in PRESETS:
        preset_name = "full"

    base = copy.deepcopy(DEFAULT_CONFIG)
    base["preset"] = preset_name
    base["display"] = _deep_merge(DEFAULT_DISPLAY, PRESETS[preset_name])

    merged = _deep_merge(base, user_raw)
    merged["language"] = normalize_language(str(merged.get("language") or "en"))
    if merged.get("layout") not in VALID_LAYOUTS:
        merged["layout"] = "expanded"
    if merged.get("theme") not in VALID_THEMES:
        merged["theme"] = "auto"

    try:
        levels = int(merged.get("pathLevels", 1))
        merged["pathLevels"] = max(1, min(3, levels))
    except (TypeError, ValueError):
        merged["pathLevels"] = 1

    return merged


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    cfg_path = path or get_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cfg_path

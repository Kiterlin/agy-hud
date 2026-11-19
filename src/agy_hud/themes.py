"""Color themes and automatic light/dark detection for agy-hud."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agy_hud.config import get_agy_cli_dir

RESET = "\033[0m"

# 24-bit TrueColor palettes (RGB tuples)
TRUECOLOR_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "catppuccin-latte": {
        "text": (76, 79, 105),
        "subtext": (108, 111, 133),
        "overlay": (156, 160, 176),
        "bar_empty": (188, 192, 204),
        "model": (136, 57, 239),       # Mauve
        "project": (30, 102, 245),     # Blue
        "git_wrap": (114, 135, 253),   # Lavender
        "git_branch": (23, 146, 153),  # Teal
        "ctx_ok": (64, 160, 43),       # Green
        "usage_ok": (32, 159, 181),    # Sapphire
        "warn": (223, 142, 29),        # Yellow
        "peach": (254, 100, 11),       # Peach
        "crit": (210, 15, 57),         # Red
        "tool_name": (32, 159, 181),   # Sapphire
        "agent": (136, 57, 239),       # Mauve
        "flamingo": (221, 120, 120),   # Flamingo
    },
    "catppuccin-macchiato": {
        "text": (202, 211, 245),
        "subtext": (165, 173, 203),
        "overlay": (110, 115, 141),
        "bar_empty": (73, 77, 100),
        "model": (198, 160, 246),      # Mauve
        "project": (138, 173, 244),    # Blue
        "git_wrap": (183, 189, 248),   # Lavender
        "git_branch": (139, 213, 202), # Teal
        "ctx_ok": (166, 218, 149),     # Green
        "usage_ok": (125, 196, 228),   # Sapphire
        "warn": (238, 212, 159),       # Yellow
        "peach": (245, 169, 127),      # Peach
        "crit": (237, 135, 150),       # Red
        "tool_name": (125, 196, 228),  # Sapphire
        "agent": (198, 160, 246),      # Mauve
        "flamingo": (240, 198, 198),   # Flamingo
    },
    "tokyo-night": {
        "text": (192, 202, 245),
        "subtext": (154, 165, 206),
        "overlay": (86, 95, 137),
        "bar_empty": (65, 72, 104),
        "model": (187, 154, 247),
        "project": (122, 162, 247),
        "git_wrap": (157, 124, 216),
        "git_branch": (115, 218, 202),
        "ctx_ok": (158, 206, 106),
        "usage_ok": (125, 207, 255),
        "warn": (224, 175, 104),
        "peach": (255, 158, 100),
        "crit": (247, 118, 142),
        "tool_name": (125, 207, 255),
        "agent": (187, 154, 247),
        "flamingo": (247, 118, 142),
    },
    "nord": {
        "text": (229, 233, 240),
        "subtext": (216, 222, 233),
        "overlay": (108, 122, 147),
        "bar_empty": (76, 86, 106),
        "model": (180, 142, 173),
        "project": (129, 161, 193),
        "git_wrap": (143, 188, 187),
        "git_branch": (136, 192, 208),
        "ctx_ok": (163, 190, 140),
        "usage_ok": (136, 192, 208),
        "warn": (235, 203, 139),
        "peach": (208, 135, 112),
        "crit": (191, 97, 106),
        "tool_name": (136, 192, 208),
        "agent": (180, 142, 173),
        "flamingo": (208, 135, 112),
    },
    "gruvbox-dark": {
        "text": (235, 219, 178),
        "subtext": (189, 174, 147),
        "overlay": (146, 131, 116),
        "bar_empty": (102, 92, 84),
        "model": (211, 134, 155),
        "project": (131, 165, 152),
        "git_wrap": (211, 134, 155),
        "git_branch": (142, 192, 124),
        "ctx_ok": (184, 187, 38),
        "usage_ok": (131, 165, 152),
        "warn": (250, 189, 47),
        "peach": (254, 128, 25),
        "crit": (251, 73, 52),
        "tool_name": (131, 165, 152),
        "agent": (211, 134, 155),
        "flamingo": (254, 128, 25),
    },
}

# Standard 16-color ANSI codes fallback
ANSI16_CODES: dict[str, str] = {
    "text": "39",
    "subtext": "2",
    "overlay": "2",
    "bar_empty": "2",
    "model": "35",
    "project": "34",
    "git_wrap": "35",
    "git_branch": "36",
    "ctx_ok": "32",
    "usage_ok": "36",
    "warn": "33",
    "peach": "33",
    "crit": "31",
    "tool_name": "36",
    "agent": "35",
    "flamingo": "95",
}


def detect_color_scheme() -> str:
    """Detect Antigravity CLI light/dark mode from settings.json or config.json."""
    settings_path = get_agy_cli_dir() / "settings.json"
    try:
        scheme = str(json.loads(settings_path.read_text(encoding="utf-8")).get("colorScheme", "")).strip().lower()
        if scheme in ("light", "dark"):
            return scheme
    except Exception:
        pass

    config_path = Path.home() / ".gemini" / "config" / "config.json"
    try:
        mode = str(
            json.loads(config_path.read_text(encoding="utf-8"))
            .get("userSettings", {})
            .get("themeMode", "")
        ).upper()
        if "DARK" in mode:
            return "dark"
        if "LIGHT" in mode:
            return "light"
    except Exception:
        pass

    return "dark"


def _parse_hex(val: str) -> tuple[int, int, int] | None:
    s = val.strip()
    if s.startswith("#") and len(s) == 7:
        try:
            return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
        except ValueError:
            return None
    return None


class Theme:
    def __init__(
        self,
        name: str,
        rgb_map: dict[str, tuple[int, int, int]] | None,
        ansi_map: dict[str, str] | None,
        no_color: bool = False,
    ) -> None:
        self.name = name
        self.rgb_map = rgb_map
        self.ansi_map = ansi_map
        self.no_color = no_color

    def fg(self, text: str, role: str, bold: bool = False) -> str:
        if not text or self.no_color:
            return text
        if self.rgb_map is not None and role in self.rgb_map:
            r, g, b = self.rgb_map[role]
            prefix = f"\033[1;38;2;{r};{g};{b}m" if bold else f"\033[38;2;{r};{g};{b}m"
            return f"{prefix}{text}{RESET}"
        code = (self.ansi_map or ANSI16_CODES).get(role, "39")
        prefix = f"\033[1;{code}m" if bold and code != "2" else f"\033[{code}m"
        return f"{prefix}{text}{RESET}"


def resolve_theme(config: dict[str, Any]) -> Theme:
    no_color = bool(os.environ.get("NO_COLOR"))
    requested = (
        os.environ.get("AGY_HUD_THEME", "").strip().lower()
        or str(config.get("theme") or "auto").strip().lower()
    )

    if requested == "auto":
        scheme = detect_color_scheme()
        resolved = "catppuccin-latte" if scheme == "light" else "catppuccin-macchiato"
    elif requested == "light":
        resolved = "catppuccin-latte"
    elif requested == "dark":
        resolved = "catppuccin-macchiato"
    else:
        resolved = requested

    if resolved == "ansi":
        return Theme("ansi", None, dict(ANSI16_CODES), no_color=no_color)

    palette = dict(TRUECOLOR_PALETTES.get(resolved, TRUECOLOR_PALETTES["catppuccin-macchiato"]))
    overrides = config.get("colors")
    if isinstance(overrides, dict):
        for role, raw_val in overrides.items():
            if isinstance(raw_val, str):
                rgb = _parse_hex(raw_val)
                if rgb is not None:
                    palette[role] = rgb

    return Theme(resolved, palette, None, no_color=no_color)

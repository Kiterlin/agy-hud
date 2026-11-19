"""ANSI-safe, CJK-aware display width calculations and truncation helpers."""

from __future__ import annotations

import re
import unicodedata

ANSI_RE = re.compile(r"\033\[[0-9;]*m|\033\][^\007\033]*(?:\007|\033\\)")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def char_width(ch: str) -> int:
    cat = unicodedata.category(ch)
    if cat in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def visible_width(text: str) -> int:
    clean = strip_ansi(text)
    return sum(char_width(ch) for ch in clean)


def truncate_plain(text: str, max_cols: int) -> str:
    if max_cols <= 0:
        return ""
    if visible_width(text) <= max_cols:
        return text
    if max_cols == 1:
        return "…"
    out: list[str] = []
    used = 0
    limit = max_cols - 1
    for ch in text:
        w = char_width(ch)
        if used + w > limit:
            break
        out.append(ch)
        used += w
    return "".join(out).rstrip() + "…"


def pad_right_width(text: str, target_cols: int) -> str:
    pad = max(0, target_cols - visible_width(text))
    return text + (" " * pad)


def adaptive_bar_width(term_width: int) -> int:
    """Match claude-hud adaptive bar sizing: 10 / 6 / 4."""
    if term_width >= 100:
        return 10
    if term_width >= 60:
        return 6
    return 4

"""Lightweight i18n message catalogs for agy-hud (en, zh-Hans, zh-Hant)."""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "context": "Context",
        "quota_5h": "5h",
        "quota_7d": "7d",
        "cache": "cache",
        "tokens": "tok",
        "limit": "Limit",
        "confirm": "confirm",
        "sandbox": "sandbox",
        "thinking": "thinking",
        "working": "working",
        "tool": "tool",
        "more": "more",
    },
    "zh-Hans": {
        "context": "上下文",
        "quota_5h": "5h",
        "quota_7d": "周限",
        "cache": "缓存",
        "tokens": "累计",
        "limit": "已达上限",
        "confirm": "待确认",
        "sandbox": "沙箱",
        "thinking": "思考中",
        "working": "运行中",
        "tool": "工具中",
        "more": "项",
    },
    "zh-Hant": {
        "context": "上下文",
        "quota_5h": "5h",
        "quota_7d": "週限",
        "cache": "快取",
        "tokens": "累計",
        "limit": "已達上限",
        "confirm": "待確認",
        "sandbox": "沙盒",
        "thinking": "思考中",
        "working": "執行中",
        "tool": "工具中",
        "more": "項",
    },
}


def t(lang: str, key: str) -> str:
    table = MESSAGES.get(lang) or MESSAGES["en"]
    return table.get(key, MESSAGES["en"].get(key, key))

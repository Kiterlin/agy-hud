"""CLI entrypoint for agy-hud: stdin statusLine renderer + install/preview/doctor tools."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from agy_hud import __version__
from agy_hud.config import (
    DEFAULT_CONFIG,
    PRESETS,
    VALID_LANGUAGES,
    VALID_LAYOUTS,
    VALID_PRESETS,
    VALID_THEMES,
    get_agy_cli_dir,
    get_config_path,
    load_config,
    normalize_language,
    save_config,
)
from agy_hud.git_info import GitInfo
from agy_hud.render import render_hud
from agy_hud.themes import detect_color_scheme, resolve_theme
from agy_hud.transcript import AgentActivity, TranscriptSummary


def _resolve_launcher_command() -> str:
    """Resolve the shell command written into Antigravity CLI settings.json."""
    pkg_root = Path(__file__).resolve().parents[2]
    launcher = pkg_root / "bin" / "agy-hud.py"
    py_bin = "python" if platform.system().lower() == "windows" else "python3"
    if launcher.is_file():
        return f'{py_bin} "{launcher}"' if " " in str(launcher) else f"{py_bin} {launcher}"
    return f"{py_bin} -m agy_hud"


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _write_json_dict(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_install(args: argparse.Namespace) -> int:
    cli_dir = get_agy_cli_dir()
    settings_path = cli_dir / "settings.json"
    backup_path = cli_dir / "agy-hud.backup.json"
    cfg_path = get_config_path()

    settings = _load_json_dict(settings_path)
    prev = settings.get("statusLine")
    cmd = _resolve_launcher_command()

    # Save previous non-agy-hud statusLine once so --uninstall can restore cleanly
    if isinstance(prev, dict) and "agy-hud" not in str(prev.get("command", "")) and not backup_path.exists():
        _write_json_dict(backup_path, {"previous_statusLine": prev})

    settings["statusLine"] = {
        "type": "command",
        "command": cmd,
        "enabled": True,
        "stack_with_default": bool(args.stack_with_default),
        "padding": int(args.padding),
    }
    _write_json_dict(settings_path, settings)

    # Create or update agy-hud.json config
    cfg = load_config(cfg_path) if cfg_path.is_file() else load_config(Path("/nonexistent"))
    if args.preset:
        cfg["preset"] = args.preset
        cfg["display"].update(PRESETS[args.preset])
    if args.layout:
        cfg["layout"] = args.layout
    if args.theme:
        cfg["theme"] = args.theme
    if args.language:
        cfg["language"] = normalize_language(args.language)
    save_config(cfg, cfg_path)

    print(f"Installed agy-hud v{__version__}")
    print(f"  settings.json : {settings_path}")
    print(f"  command       : {cmd}")
    print(f"  config        : {cfg_path}")
    if backup_path.is_file():
        print(f"  backup        : {backup_path}")
    return 0


def cmd_uninstall(_args: argparse.Namespace) -> int:
    cli_dir = get_agy_cli_dir()
    settings_path = cli_dir / "settings.json"
    backup_path = cli_dir / "agy-hud.backup.json"

    settings = _load_json_dict(settings_path)
    if not settings:
        print(f"No settings.json found at {settings_path}")
        return 0

    if backup_path.is_file():
        backup = _load_json_dict(backup_path)
        prev = backup.get("previous_statusLine")
        if isinstance(prev, dict):
            settings["statusLine"] = prev
            _write_json_dict(settings_path, settings)
            backup_path.unlink(missing_ok=True)
            print(f"Restored previous statusLine from {backup_path}")
            return 0

    if isinstance(settings.get("statusLine"), dict):
        settings["statusLine"]["enabled"] = False
        _write_json_dict(settings_path, settings)
        print(f"Disabled agy-hud statusLine in {settings_path}")
    return 0


def cmd_configure(args: argparse.Namespace) -> int:
    cfg_path = get_config_path()
    cfg = load_config(cfg_path)
    changed = False

    if args.preset:
        cfg["preset"] = args.preset
        cfg["display"].update(PRESETS[args.preset])
        changed = True
    if args.layout:
        cfg["layout"] = args.layout
        changed = True
    if args.theme:
        cfg["theme"] = args.theme
        changed = True
    if args.language:
        cfg["language"] = normalize_language(args.language)
        changed = True
    if args.bar_style:
        cfg["display"]["barStyle"] = args.bar_style
        changed = True
    if args.show_separators is not None:
        cfg["showSeparators"] = args.show_separators
        changed = True

    if changed:
        save_config(cfg, cfg_path)
        print(f"Saved config to {cfg_path}")
    else:
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
    return 0


def _demo_payload(width: int, *, active: bool = True, is_3p: bool = False) -> dict[str, Any]:
    if is_3p:
        return {
            "cwd": "/home/dev/projects/agy-hud",
            "model": {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6 (High)"},
            "workspace": {"current_dir": "/home/dev/projects/agy-hud", "branch": "feat/hud"},
            "context_window": {
                "total_input_tokens": 172000,
                "total_output_tokens": 24000,
                "context_window_size": 200000,
                "used_percentage": 86.0,
                "current_usage": {
                    "input_tokens": 20000,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 152000,
                },
            },
            "quota": {
                "3p-5h": {"remaining_fraction": 0.14, "reset_in_seconds": 3900},
                "3p-weekly": {"remaining_fraction": 0.42, "reset_in_seconds": 259200},
            },
            "agent_state": "thinking",
            "sandbox": {"enabled": True},
            "tool_confirmation_pending": True,
            "conversation_title": "Refactor status renderer",
            "terminal_width": width,
        }

    return {
        "cwd": "/home/dev/projects/agy-hud",
        "model": {"id": "Gemini 4 Neon (XHigh)", "display_name": "Gemini 4 Neon (XHigh)", "effort": "xhigh"},
        "workspace": {"current_dir": "/home/dev/projects/agy-hud", "branch": "main"},
        "context_window": {
            "total_input_tokens": 57293,
            "total_output_tokens": 13197,
            "context_window_size": 1048576,
            "used_percentage": 5.46,
            "current_usage": {
                "input_tokens": 5189,
                "output_tokens": 128,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 49095,
            },
        },
        "quota": {
            "gemini-5h": {"remaining_fraction": 0.852, "reset_in_seconds": 11400},
            "gemini-weekly": {"remaining_fraction": 0.684, "reset_in_seconds": 515336},
        },
        "agent_state": "tool_use" if active else "idle",
        "sandbox": {"enabled": False},
        "tool_confirmation_pending": False,
        "conversation_title": "Build agy-hud plugin",
        "terminal_width": width,
    }


def _demo_transcript(active: bool = True) -> TranscriptSummary:
    now = time.time()
    return TranscriptSummary(
        running_tools=[("run_command", "python3 -m unittest")] if active else [],
        completed_tools=Counter({"read_file": 12, "edit_file": 5, "run_command": 4, "search_web": 2}),
        agents=[
            AgentActivity(
                role="Codebase Researcher",
                model="flash",
                status="running" if active else "completed",
                start_ts=now - 14,
                end_ts=0.0 if active else now - 2,
            )
        ],
        session_start_ts=now - 720,
    )


def cmd_preview(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.preset:
        cfg["preset"] = args.preset
        cfg["display"].update(PRESETS[args.preset])
    if args.layout:
        cfg["layout"] = args.layout
    if args.theme:
        cfg["theme"] = args.theme
    if args.language:
        cfg["language"] = normalize_language(args.language)
    if args.bar_style:
        cfg["display"]["barStyle"] = args.bar_style

    theme = resolve_theme(cfg)
    git_demo = GitInfo(branch="main", dirty=True, ahead=1)

    scenarios = [
        ("Wide (150 cols)", 150, True, False),
        ("Standard (108 cols)", 108, True, False),
        ("Narrow (64 cols)", 64, False, False),
        ("High Context + Low Quota + Alerts (108 cols)", 108, True, True),
    ]

    print(f"agy-hud v{__version__} preview — theme={theme.name}, preset={cfg['preset']}, layout={cfg['layout']}, lang={cfg['language']}\n")
    for label, width, active, is_3p in scenarios:
        print(f"--- {label} ---")
        lines = render_hud(
            _demo_payload(width, active=active, is_3p=is_3p),
            cfg,
            transcript_summary=_demo_transcript(active=active),
            git_info_override=git_demo,
            use_git_override=True,
        )
        for ln in lines:
            print(ln)
        print()
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    cli_dir = get_agy_cli_dir()
    settings_path = cli_dir / "settings.json"
    cfg_path = get_config_path()
    cfg = load_config(cfg_path)
    theme = resolve_theme(cfg)
    settings = _load_json_dict(settings_path)
    sl = settings.get("statusLine") if isinstance(settings.get("statusLine"), dict) else {}

    t0 = time.perf_counter()
    lines = render_hud(
        _demo_payload(120, active=True),
        cfg,
        transcript_summary=_demo_transcript(active=True),
        git_info_override=GitInfo(branch="main", dirty=True, ahead=1),
        use_git_override=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print(f"agy-hud v{__version__} doctor")
    print(f"  Python          : {platform.python_version()} ({sys.executable})")
    print(f"  Git             : {shutil.which('git') or 'NOT FOUND'}")
    print(f"  CLI dir         : {cli_dir} ({'exists' if cli_dir.is_dir() else 'missing'})")
    print(f"  settings.json   : {settings_path} ({'exists' if settings_path.is_file() else 'missing'})")
    print(f"  statusLine on   : {bool(sl.get('enabled'))}")
    print(f"  statusLine cmd  : {sl.get('command') or '(not set)'}")
    print(f"  agy-hud config  : {cfg_path} ({'exists' if cfg_path.is_file() else 'using defaults'})")
    print(f"  Detected scheme : {detect_color_scheme()} -> resolved theme: {theme.name}")
    print(f"  Render smoke    : OK ({len(lines)} lines in {elapsed_ms:.2f}ms)")
    return 0


def cmd_render_stdin() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        if not isinstance(data, dict):
            return 0
    except Exception:
        return 0

    try:
        cfg = load_config()
        for ln in render_hud(data, cfg):
            print(ln)
    except Exception:
        return 0
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agy-hud",
        description="Real-time status line HUD for Antigravity CLI (reads stdin JSON when run without flags).",
    )
    p.add_argument("--version", action="version", version=f"agy-hud {__version__}")
    p.add_argument("--install", action="store_true", help="Configure and enable agy-hud in Antigravity CLI settings.json")
    p.add_argument("--uninstall", action="store_true", help="Disable agy-hud and restore previous statusLine backup if any")
    p.add_argument("--configure", action="store_true", help="Update or inspect agy-hud.json configuration")
    p.add_argument("--preview", action="store_true", help="Render live ANSI previews across terminal widths")
    p.add_argument("--doctor", action="store_true", help="Check environment, settings wiring, and render health")
    p.add_argument("--preset", choices=VALID_PRESETS, help="Preset profile (full, essential, minimal)")
    p.add_argument("--layout", choices=VALID_LAYOUTS, help="Layout mode (expanded, compact)")
    p.add_argument("--theme", choices=VALID_THEMES, help="Color theme preset")
    p.add_argument("--language", choices=VALID_LANGUAGES, help="HUD label language")
    p.add_argument("--bar-style", choices=("block", "line", "dot"), help="Progress bar style")
    p.add_argument("--padding", type=int, default=0, help="Blank lines above status line (--install only)")
    p.add_argument("--stack-with-default", action="store_true", help="Stack below built-in status line (--install only)")
    p.add_argument("--show-separators", dest="show_separators", action="store_true", default=None, help="Show divider before activity lines")
    p.add_argument("--no-separators", dest="show_separators", action="store_false", help="Hide divider before activity lines")
    return p


def main(argv: list[str] | None = None) -> int:
    # Fast path when invoked by Antigravity CLI with no arguments
    raw_argv = sys.argv[1:] if argv is None else argv
    if not raw_argv:
        return cmd_render_stdin()

    parser = build_parser()
    args = parser.parse_args(raw_argv)

    if args.install:
        return cmd_install(args)
    if args.uninstall:
        return cmd_uninstall(args)
    if args.configure:
        return cmd_configure(args)
    if args.preview:
        return cmd_preview(args)
    if args.doctor:
        return cmd_doctor(args)
    return cmd_render_stdin()


if __name__ == "__main__":
    raise SystemExit(main())

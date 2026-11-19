---
name: agy-hud-setup
description: >-
  Set up, enable, diagnose, or uninstall the agy-hud status line for Antigravity
  CLI. Use when the user asks to install agy-hud, configure statusLine in
  settings.json, run diagnostics, or disable/restore their previous status line.
---

# AGY HUD Setup

Configure Antigravity CLI to render the **agy-hud** real-time status line below
the prompt box.

## Prerequisites

- Python 3.9 or later (`python3` on macOS/Linux/WSL, `python` on Windows).
- Zero external packages required (Python standard library only).

## Steps

### 1. Locate the launcher

The launcher lives two directories above this skill file:
`../../bin/agy-hud.py` (for example `~/.gemini/config/plugins/agy-hud/bin/agy-hud.py`).

### 2. Run the installer

Execute the installer to wire `statusLine` in `~/.gemini/antigravity-cli/settings.json`
and create a default `~/.gemini/antigravity-cli/agy-hud.json` if one does not exist:

```bash
python3 <plugin_root>/bin/agy-hud.py --install
```

On Windows (PowerShell 7):

```powershell
python "<plugin_root>\bin\agy-hud.py" --install
```

Useful optional flags during installation:
- `--preset full|essential|minimal`
- `--layout expanded|compact`
- `--theme auto|catppuccin-latte|catppuccin-macchiato|tokyo-night|nord|gruvbox-dark|ansi`
- `--language en|zh-Hans|zh-Hant`
- `--padding 0|1`
- `--stack-with-default` (keep the built-in status line above `agy-hud`)

The installer automatically backs up any previous custom `statusLine` block to
`~/.gemini/antigravity-cli/agy-hud.backup.json`.

### 3. Verify & preview

Run the built-in health check and visual preview:

```bash
python3 <plugin_root>/bin/agy-hud.py --doctor
python3 <plugin_root>/bin/agy-hud.py --preview
```

Confirm that `--doctor` reports:
- `statusLine on : True`
- `Render smoke  : OK`

### 4. Inform the user

Let the user know:
1. `agy-hud` is now enabled in `~/.gemini/antigravity-cli/settings.json`.
2. In an already-open CLI session, run `/statusline` (or start a new `agy` session) to see the HUD live.
3. They can customize layout, theme, language, and modules anytime using the `agy-hud-configure` skill or by editing `~/.gemini/antigravity-cli/agy-hud.json`.

## Uninstalling

To restore the previous `statusLine` configuration (or disable `agy-hud`):

```bash
python3 <plugin_root>/bin/agy-hud.py --uninstall
```

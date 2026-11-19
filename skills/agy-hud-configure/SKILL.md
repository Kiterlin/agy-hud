---
name: agy-hud-configure
description: >-
  Interactively configure agy-hud status line options (layout, preset, color
  theme, language, bar style, and individual modules) while preserving custom
  color and threshold overrides. Use when the user asks to customize, restyle,
  or toggle modules in agy-hud.
---

# Configure AGY HUD

Guide the user through customizing `~/.gemini/antigravity-cli/agy-hud.json`
without losing any manual overrides (`colors.*`, custom warning thresholds, or
`customLine`).

## Step 1: Load existing config

Read `~/.gemini/antigravity-cli/agy-hud.json` if it exists. If it does not exist,
start from the default `full` / `expanded` / `auto` / `en` settings.

Keep any existing manual fields (`colors`, `contextWarningThreshold`,
`contextCriticalThreshold`, `quotaWarningThreshold`, `quotaCriticalThreshold`,
`customLine`) intact when saving.

## Step 2: Interview preferences

Use `ask_question` to gather the user's preferences concisely (skip questions
the user already answered in their prompt):

1. **Layout**:
   - `expanded` (Recommended) — Semantic multi-line HUD with vertically column-aligned progress bars on medium/narrow terminals.
   - `compact` — Single compact header line + optional activity lines.
2. **Preset**:
   - `full` (Recommended) — Model, effort, project/git, title, context bar + cache + total tokens, 5h/7d quotas, status badges, live tools & subagents.
   - `essential` — Model, effort, project/git, context bar, 5h/7d quotas, live tools & subagents (hides title, cache hit, cumulative tokens).
   - `minimal` — Core only (model, effort, context bar, 5h quota bar).
3. **Color Theme**:
   - `auto` (Recommended) — Follows Antigravity `colorScheme` (`catppuccin-latte` on light, `catppuccin-macchiato` on dark).
   - `catppuccin-latte`, `catppuccin-macchiato`, `tokyo-night`, `nord`, `gruvbox-dark`, or `ansi` (16-color).
4. **Language**:
   - `en` (Recommended), `zh-Hans` (简体中文), or `zh-Hant` (繁體中文).
5. **Fine-tuning (optional multi-select)**:
   - Toggle `showTools`, `showAgents`, `showSessionTitle`, `showCacheHit`, `showSessionTokens`, `showDuration`, `showSeparators`, or change `barStyle` (`block` / `line` / `dot`) and `quotaValueMode` (`remaining` / `used`).

## Step 3: Save and preview

1. Write the merged JSON cleanly to `~/.gemini/antigravity-cli/agy-hud.json`
   (or invoke `python3 <plugin_root>/bin/agy-hud.py --configure ...`).
2. Run a preview to verify zero errors and show the resulting layout:

```bash
python3 <plugin_root>/bin/agy-hud.py --preview
```

3. Summarize the updated settings and remind the user that changes take effect
   on the very next Antigravity CLI status line refresh (no restart required).

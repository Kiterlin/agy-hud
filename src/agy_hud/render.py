"""claude-hud inspired modular renderer for Antigravity CLI."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from agy_hud.git_info import GitInfo, format_project_path, get_git_info
from agy_hud.i18n import t
from agy_hud.themes import RESET, Theme, resolve_theme
from agy_hud.transcript import AgentActivity, TranscriptSummary, parse_transcript
from agy_hud.width import adaptive_bar_width, pad_right_width, truncate_plain, visible_width

EFFORT_TAG_RE = re.compile(
    r"\s*\((xhigh|high|medium|med|low|minimal|thinking|max|auto)\)",
    re.IGNORECASE,
)

EFFORT_SYMBOLS = {
    "minimal": "○",
    "low": "○",
    "medium": "◔",
    "med": "◔",
    "high": "◑",
    "xhigh": "◕",
    "max": "●",
    "thinking": "◑",
}

EFFORT_TEXT = {
    "minimal": "min",
    "low": "low",
    "medium": "medium",
    "med": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
    "thinking": "thinking",
    "auto": "auto",
}

BAR_STYLES = {
    "block": ("█", "░"),
    "line": ("━", "─"),
    "dot": ("●", "○"),
}

COMPLETED_AGENT_RETENTION_SEC = 60.0


def format_duration(seconds: Any) -> str:
    try:
        sec = int(seconds or 0)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    total_mins = max(1, (sec + 59) // 60)
    if total_mins < 60:
        return f"{total_mins}m"
    hours = total_mins // 60
    mins = total_mins % 60
    if hours >= 24:
        days = hours // 24
        rem_h = hours % 24
        return f"{days}d {rem_h}h" if rem_h > 0 else f"{days}d"
    return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"


def format_elapsed_sec(seconds: float) -> str:
    sec = max(0, int(round(seconds)))
    if sec < 1:
        return "<1s"
    if sec < 60:
        return f"{sec}s"
    mins = sec // 60
    rem_s = sec % 60
    if mins < 60:
        return f"{mins}m {rem_s}s" if rem_s else f"{mins}m"
    hours = mins // 60
    rem_m = mins % 60
    return f"{hours}h {rem_m}m" if rem_m else f"{hours}h"


def format_tokens(count: Any) -> str:
    try:
        n = int(count or 0)
    except (TypeError, ValueError):
        return "0"
    if n <= 0:
        return "0"
    if n >= 1_000_000:
        mib = n / 1_048_576
        if abs(mib - round(mib)) < 0.02:
            return f"{int(round(mib))}M"
        val = n / 1_000_000
        return f"{int(round(val))}M" if abs(val - round(val)) < 0.05 else f"{val:.1f}M"
    if n >= 10_000:
        return f"{int(round(n / 1000))}k"
    if n >= 1_000:
        val = n / 1000
        return f"{int(round(val))}k" if abs(val - round(val)) < 0.05 else f"{val:.1f}k"
    return str(n)


def make_bar(pct: float, fill_role: str, theme: Theme, width: int, style: str = "block") -> str:
    pct = max(0.0, min(100.0, float(pct)))
    fill_ch, empty_ch = BAR_STYLES.get(style, BAR_STYLES["block"])
    filled = 0 if pct <= 0 else max(1, min(width, int(round(pct / 100.0 * width))))
    empty = width - filled
    out: list[str] = []
    if filled:
        out.append(theme.fg(fill_ch * filled, fill_role))
    if empty:
        out.append(theme.fg(empty_ch * empty, "bar_empty"))
    return "".join(out)


def parse_model(data: dict[str, Any]) -> tuple[str, str, str]:
    model_obj = data.get("model", {})
    if isinstance(model_obj, dict):
        model_id = str(model_obj.get("id") or "")
        raw_name = str(model_obj.get("display_name") or model_id or "Gemini")
        effort = str(model_obj.get("effort") or model_obj.get("thinking_level") or "")
    else:
        raw_name = str(model_obj or "Gemini")
        model_id = raw_name
        effort = ""

    match = EFFORT_TAG_RE.search(raw_name)
    if match:
        if not effort:
            effort = match.group(1)
        clean_name = EFFORT_TAG_RE.sub("", raw_name).strip()
    else:
        clean_name = raw_name.strip()

    return clean_name, effort.strip().lower(), model_id


def build_model_badge(clean_name: str, effort_key: str, show_effort: bool, theme: Theme) -> str:
    inner = clean_name
    if show_effort and effort_key:
        sym = EFFORT_SYMBOLS.get(effort_key, "")
        txt = EFFORT_TEXT.get(effort_key, effort_key)
        inner = f"{clean_name} {sym} {txt}" if sym else f"{clean_name} {txt}"
    return theme.fg(f"[{inner}]", "model", bold=True)


def build_project_part(
    dir_name: str,
    git_info: GitInfo | None,
    theme: Theme,
    include_ab: bool = True,
    max_dir_len: int = 28,
    max_branch_len: int = 26,
) -> str:
    parts: list[str] = []
    if dir_name:
        parts.append(theme.fg(truncate_plain(dir_name, max_dir_len), "project", bold=True))
    if git_info and git_info.branch:
        branch = truncate_plain(git_info.branch, max_branch_len)
        inner = theme.fg(branch, "git_branch")
        if git_info.dirty:
            inner += theme.fg("*", "peach", bold=True)
        if git_info.untracked:
            inner += theme.fg("?", "warn", bold=True)
        if include_ab:
            if git_info.ahead:
                inner += " " + theme.fg(f"↑{git_info.ahead}", "git_branch")
            if git_info.behind:
                inner += " " + theme.fg(f"↓{git_info.behind}", "git_branch")
        parts.append(f"{theme.fg('git:(', 'git_wrap')}{inner}{theme.fg(')', 'git_wrap')}")
    return " ".join(parts)


def select_quota_keys(quota: dict[str, Any], clean_name: str, model_id: str) -> tuple[str | None, str | None]:
    if not isinstance(quota, dict) or not quota:
        return None, None
    probe = f"{clean_name} {model_id}".lower()
    is_3p = any(k in probe for k in ("3p", "claude", "gpt", "sonnet", "opus", "haiku", "o1", "o3", "o4"))
    if is_3p:
        k5 = "3p-5h" if "3p-5h" in quota else ("gemini-5h" if "gemini-5h" in quota else None)
        k7 = "3p-weekly" if "3p-weekly" in quota else ("gemini-weekly" if "gemini-weekly" in quota else None)
    else:
        k5 = "gemini-5h" if "gemini-5h" in quota else ("3p-5h" if "3p-5h" in quota else None)
        k7 = "gemini-weekly" if "gemini-weekly" in quota else ("3p-weekly" if "3p-weekly" in quota else None)

    if not k5:
        k5 = next((k for k in quota if k.endswith("-5h")), None)
    if not k7:
        k7 = next((k for k in quota if "week" in k or k.endswith("-7d")), None)
    return k5, k7


def render_context_entry(
    ctx: dict[str, Any],
    display: dict[str, Any],
    lang: str,
    theme: Theme,
    bar_width: int,
    label_width: int = 0,
    pct_pad: int = 0,
    show_ratio: bool = True,
    show_cache: bool = True,
    show_total: bool = True,
) -> str:
    ctx_limit = ctx.get("context_window_size") or 0
    if ctx_limit <= 0:
        return ""

    used_pct = ctx.get("used_percentage")
    total_in = ctx.get("total_input_tokens") or 0
    total_out = ctx.get("total_output_tokens") or 0
    cumulative = total_in + total_out
    cur = ctx.get("current_usage") or {}

    if used_pct is not None:
        pct = max(0.0, min(100.0, float(used_pct)))
        ctx_used = int(round(pct / 100.0 * ctx_limit))
    else:
        cur_in = (
            (cur.get("input_tokens") or 0)
            + (cur.get("cache_creation_input_tokens") or 0)
            + (cur.get("cache_read_input_tokens") or 0)
        )
        ctx_used = cur_in or ctx.get("total_tokens") or total_in
        pct = max(0.0, min(100.0, (ctx_used / ctx_limit) * 100.0))

    pct_int = int(round(pct))
    warn_th = float(display.get("contextWarningThreshold", 70))
    crit_th = float(display.get("contextCriticalThreshold", 85))

    if pct >= crit_th:
        role = "crit"
        bold = True
    elif pct >= warn_th:
        role = "warn"
        bold = False
    else:
        role = "ctx_ok"
        bold = False

    lbl_raw = t(lang, "context")
    lbl = theme.fg(pad_right_width(lbl_raw, label_width) if label_width else lbl_raw, "subtext")
    pct_str = f"{pct_int}%".rjust(pct_pad) if pct_pad else f"{pct_int}%"

    parts = [lbl]
    if bar_width > 0 and display.get("showContextBar", True):
        parts.append(make_bar(pct, role, theme, bar_width, style=str(display.get("barStyle", "block"))))
    parts.append(theme.fg(pct_str, role, bold=bold))

    if show_ratio and display.get("showContextTokens", True):
        parts.append(theme.fg(f"({format_tokens(ctx_used)}/{format_tokens(ctx_limit)})", "subtext"))

    extras: list[str] = []
    if show_cache and display.get("showCacheHit", True):
        cache_read = cur.get("cache_read_input_tokens") or 0
        cur_in_total = (
            (cur.get("input_tokens") or 0)
            + (cur.get("cache_creation_input_tokens") or 0)
            + cache_read
        )
        if cache_read > 0 and cur_in_total > 0:
            cache_pct = int(round((cache_read / cur_in_total) * 100.0))
            extras.append(theme.fg(f"{t(lang, 'cache')} {cache_pct}%", "git_branch"))

    if show_total and display.get("showSessionTokens", True) and cumulative > 0:
        extras.append(theme.fg(f"{t(lang, 'tokens')} {format_tokens(cumulative)}", "subtext"))

    if extras:
        dot = theme.fg(" · ", "overlay")
        parts.append(theme.fg("·", "overlay"))
        parts.append(dot.join(extras))

    return " ".join(parts)


def render_quota_entry(
    label_text: str,
    item: dict[str, Any] | None,
    display: dict[str, Any],
    lang: str,
    theme: Theme,
    bar_width: int,
    label_width: int = 0,
    pct_pad: int = 0,
    show_time: bool = True,
) -> str:
    if not item or not display.get("showQuota", True):
        return ""
    frac = item.get("remaining_fraction")
    if frac is None:
        return ""

    rem_pct = max(0.0, min(100.0, float(frac) * 100.0))
    rem_int = int(round(rem_pct))
    mode = str(display.get("quotaValueMode", "remaining")).lower()
    display_pct = (100.0 - rem_pct) if mode == "used" else rem_pct
    display_int = int(round(display_pct))

    warn_th = float(display.get("quotaWarningThreshold", 50))
    crit_th = float(display.get("quotaCriticalThreshold", 20))

    if rem_pct <= crit_th:
        role = "crit"
        bold = True
    elif rem_pct <= warn_th:
        role = "peach"
        bold = False
    else:
        role = "usage_ok"
        bold = False

    lbl = theme.fg(pad_right_width(label_text, label_width) if label_width else label_text, "subtext")
    if rem_int <= 0:
        dur = format_duration(item.get("reset_in_seconds", 0))
        suffix = f" ({dur})" if dur else ""
        limit_txt = f"⚠ {t(lang, 'limit')}{suffix}"
        return f"{lbl} {theme.fg(limit_txt, 'crit', bold=True)}"

    pct_str = f"{display_int}%".rjust(pct_pad) if pct_pad else f"{display_int}%"
    parts = [lbl]
    if bar_width > 0 and display.get("showQuotaBar", True):
        parts.append(make_bar(display_pct, role, theme, bar_width, style=str(display.get("barStyle", "block"))))
    parts.append(theme.fg(pct_str, role, bold=bold))

    if show_time and display.get("showQuotaReset", True):
        dur = format_duration(item.get("reset_in_seconds", 0))
        if dur:
            parts.append(theme.fg(f"({dur})", "subtext"))

    return " ".join(parts)


def render_tools_line(
    summary: TranscriptSummary,
    display: dict[str, Any],
    lang: str,
    theme: Theme,
    max_w: int,
) -> str:
    if not display.get("showTools", True):
        return ""
    if not summary.running_tools and not summary.completed_tools:
        return ""

    sep = theme.fg(" | ", "overlay")
    parts: list[str] = []

    for name, target in summary.running_tools[-2:]:
        seg = f"{theme.fg('◐', 'warn')} {theme.fg(name, 'tool_name')}"
        if target:
            seg += theme.fg(f": {target}", "subtext")
        parts.append(seg)

    max_vis = int(display.get("toolsMaxVisible", 4))
    sorted_done = sorted(summary.completed_tools.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = sorted_done if max_vis <= 0 else sorted_done[:max_vis]
    hidden_count = max(0, len(sorted_done) - len(shown))

    for name, cnt in shown:
        parts.append(f"{theme.fg('✓', 'ctx_ok')} {theme.fg(name, 'text')} {theme.fg(f'×{cnt}', 'subtext')}")

    if hidden_count > 0:
        parts.append(theme.fg(f"+{hidden_count} {t(lang, 'more')}", "subtext"))

    while len(parts) > 1 and visible_width(sep.join(parts)) > max_w:
        parts.pop()

    line = sep.join(parts)
    return line if visible_width(line) <= max_w else ""


def render_agents_lines(
    summary: TranscriptSummary,
    display: dict[str, Any],
    theme: Theme,
    max_w: int,
    now_ts: float,
) -> list[str]:
    if not display.get("showAgents", True) or not summary.agents:
        return []

    max_agents = max(1, int(display.get("agentsMaxVisible", 3)))
    running = [a for a in summary.agents if a.status == "running"][-max_agents:]
    rem_slots = max(0, min(2, max_agents - len(running)))
    recent_done = [
        a
        for a in summary.agents
        if a.status == "completed" and a.end_ts > 0 and 0 <= (now_ts - a.end_ts) <= COMPLETED_AGENT_RETENTION_SEC
    ][-rem_slots:] if rem_slots > 0 else []

    chosen: list[AgentActivity] = [*running, *recent_done]
    lines: list[str] = []
    for ag in chosen:
        icon = theme.fg("◐", "warn") if ag.status == "running" else theme.fg("✓", "ctx_ok")
        role_txt = theme.fg(truncate_plain(ag.role, 26), "agent")
        model_txt = f" {theme.fg(f'[{ag.model}]', 'subtext')}" if ag.model else ""
        elapsed = format_elapsed_sec((ag.end_ts or now_ts) - ag.start_ts) if ag.start_ts > 0 else ""
        elapsed_txt = f" {theme.fg(f'({elapsed})', 'subtext')}" if elapsed else ""
        line = f"{icon} {role_txt}{model_txt}{elapsed_txt}"
        if visible_width(line) <= max_w:
            lines.append(line)
    return lines


def _join(parts: list[str], sep: str) -> str:
    return sep.join(p for p in parts if p)


def _build_header_line(
    model_badge: str,
    dir_name: str,
    git_info: GitInfo | None,
    state_badge: str,
    alert_badges: list[str],
    vim_badge: str,
    duration_badge: str,
    title_raw: str,
    custom_line: str,
    display: dict[str, Any],
    theme: Theme,
    sep: str,
    max_w: int,
) -> str:
    def _title(limit: int) -> str:
        if not title_raw or not display.get("showSessionTitle", True):
            return ""
        clean = " ".join(title_raw.split())
        return theme.fg(truncate_plain(clean, limit), "subtext") if clean else ""

    show_ab = bool(display.get("showGitAheadBehind", True))
    proj_full = build_project_part(dir_name, git_info, theme, include_ab=show_ab)
    proj_compact = build_project_part(dir_name, git_info, theme, include_ab=False)
    proj_tight = build_project_part(dir_name, git_info, theme, include_ab=False, max_dir_len=16, max_branch_len=14)
    custom_seg = theme.fg(custom_line, "peach") if custom_line else ""

    candidates = [
        [model_badge, proj_full, state_badge, *alert_badges, vim_badge, duration_badge, _title(24), custom_seg],
        [model_badge, proj_full, state_badge, *alert_badges, vim_badge, duration_badge, _title(14), custom_seg],
        [model_badge, proj_full, state_badge, *alert_badges, vim_badge, duration_badge, custom_seg],
        [model_badge, proj_compact, state_badge, *alert_badges, vim_badge],
        [model_badge, proj_compact, *alert_badges],
        [model_badge, proj_tight, *alert_badges],
        [model_badge, *alert_badges],
    ]
    for segs in candidates:
        line = _join(segs, sep)
        if visible_width(line) <= max_w:
            return line
    return _join([model_badge, *alert_badges], sep)


def _build_telemetry_lines(
    ctx: dict[str, Any],
    q5_item: dict[str, Any] | None,
    q7_item: dict[str, Any] | None,
    display: dict[str, Any],
    lang: str,
    theme: Theme,
    sep: str,
    term_width: int,
    max_w: int,
) -> list[str]:
    bar_w = adaptive_bar_width(term_width)
    lbl_5h = t(lang, "quota_5h")
    lbl_7d = t(lang, "quota_7d")

    ctx_inline = render_context_entry(ctx, display, lang, theme, bar_width=bar_w)
    q5_inline = render_quota_entry(lbl_5h, q5_item, display, lang, theme, bar_width=bar_w)
    q7_inline = render_quota_entry(lbl_7d, q7_item, display, lang, theme, bar_width=bar_w)
    combined = _join([ctx_inline, q5_inline, q7_inline], sep)
    if combined and visible_width(combined) <= max_w:
        return [combined]

    # Column-aligned vertical stacking (claude-hud label-align style, CJK-width accurate)
    active_labels = [t(lang, "context")]
    if q5_item and display.get("showQuota", True):
        active_labels.append(lbl_5h)
    if q7_item and display.get("showQuota", True):
        active_labels.append(lbl_7d)
    align_w = max(visible_width(lb) for lb in active_labels)

    ctx_candidates = [
        render_context_entry(ctx, display, lang, theme, bar_width=bar_w, label_width=align_w, pct_pad=3, show_ratio=True, show_cache=True, show_total=True),
        render_context_entry(ctx, display, lang, theme, bar_width=bar_w, label_width=align_w, pct_pad=3, show_ratio=True, show_cache=True, show_total=False),
        render_context_entry(ctx, display, lang, theme, bar_width=bar_w, label_width=align_w, pct_pad=3, show_ratio=True, show_cache=False, show_total=False),
        render_context_entry(ctx, display, lang, theme, bar_width=bar_w, label_width=align_w, pct_pad=3, show_ratio=False, show_cache=False, show_total=False),
        render_context_entry(ctx, display, lang, theme, bar_width=0, label_width=align_w, pct_pad=3, show_ratio=True, show_cache=False, show_total=False),
    ]
    ctx_row = next((r for r in ctx_candidates if not r or visible_width(r) <= max_w), ctx_candidates[-1])

    lines: list[str] = []
    if ctx_row:
        lines.append(ctx_row)

    q5_aligned = render_quota_entry(lbl_5h, q5_item, display, lang, theme, bar_width=bar_w, label_width=align_w, pct_pad=3)
    q7_pair = render_quota_entry(lbl_7d, q7_item, display, lang, theme, bar_width=bar_w)
    quota_combined = _join([q5_aligned, q7_pair], sep)
    if quota_combined and visible_width(quota_combined) <= max_w:
        lines.append(quota_combined)
        return lines

    for lbl, item in ((lbl_5h, q5_item), (lbl_7d, q7_item)):
        if not item:
            continue
        row_candidates = [
            render_quota_entry(lbl, item, display, lang, theme, bar_width=bar_w, label_width=align_w, pct_pad=3, show_time=True),
            render_quota_entry(lbl, item, display, lang, theme, bar_width=max(4, bar_w - 2), label_width=align_w, pct_pad=3, show_time=True),
            render_quota_entry(lbl, item, display, lang, theme, bar_width=0, label_width=align_w, pct_pad=3, show_time=True),
            render_quota_entry(lbl, item, display, lang, theme, bar_width=0, label_width=align_w, pct_pad=3, show_time=False),
        ]
        chosen = next((r for r in row_candidates if not r or visible_width(r) <= max_w), row_candidates[-1])
        if chosen:
            lines.append(chosen)

    return lines


def render_hud(
    data: dict[str, Any],
    config: dict[str, Any],
    *,
    transcript_summary: TranscriptSummary | None = None,
    git_info_override: GitInfo | None = None,
    use_git_override: bool = False,
    now_ts: float | None = None,
) -> list[str]:
    """Render the complete status line as a list of ANSI-colored lines."""
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    theme = resolve_theme(config)
    lang = str(config.get("language") or "en")
    layout = str(config.get("layout") or "expanded")
    display = config.get("display") or {}
    sep = theme.fg(" │ ", "overlay")

    term_width = int(data.get("terminal_width") or 100)
    max_w = max(28, term_width - 2)

    # 1. Model & effort
    clean_model, effort_key, model_id = parse_model(data)
    model_badge = (
        build_model_badge(clean_model, effort_key, bool(display.get("showEffort", True)), theme)
        if display.get("showModel", True)
        else ""
    )

    # 2. Project & Git
    ws = data.get("workspace") or {}
    cwd = str(ws.get("current_dir") or data.get("cwd") or ws.get("project_dir") or "")
    dir_name = format_project_path(cwd, int(config.get("pathLevels", 1))) if display.get("showProject", True) else ""

    if not display.get("showGit", True):
        git_info = None
    elif use_git_override:
        git_info = git_info_override
    else:
        git_info = get_git_info(cwd, fallback_branch=str(ws.get("branch") or ""))

    # 3. Transcript activity (tools + subagents + duration)
    need_transcript = bool(
        display.get("showTools", True)
        or display.get("showAgents", True)
        or display.get("showDuration", False)
    )
    summary = (
        transcript_summary
        if transcript_summary is not None
        else (parse_transcript(data, now_ts=now_ts) if need_transcript else TranscriptSummary())
    )

    tools_line = render_tools_line(summary, display, lang, theme, max_w)
    agent_lines = render_agents_lines(summary, display, theme, max_w, now_ts)

    # 4. Conditional status badges
    state_badge = ""
    alert_badges: list[str] = []
    vim_badge = ""
    if display.get("showStatusBadges", True):
        raw_state = str(data.get("agent_state") or "").strip().lower()
        state_key_map = {
            "thinking": "thinking",
            "working": "working",
            "running": "working",
            "streaming": "working",
            "tool_use": "tool",
            "tool": "tool",
        }
        state_key = state_key_map.get(raw_state, "")
        if state_key == "tool" and "◐" in tools_line:
            state_key = ""
        if state_key:
            state_badge = f"{theme.fg('◐', 'warn')} {theme.fg(t(lang, state_key), 'subtext')}"

        if (data.get("sandbox") or {}).get("enabled") is True:
            alert_badges.append(theme.fg(t(lang, "sandbox"), "peach", bold=True))
        if data.get("tool_confirmation_pending") is True:
            alert_badges.append(theme.fg(f"⚠ {t(lang, 'confirm')}", "crit", bold=True))

        vim_mode = str((data.get("vim") or {}).get("mode") or "").strip().upper()
        if vim_mode:
            vim_badge = theme.fg(f"VIM {vim_mode}", "flamingo", bold=True)

    duration_badge = ""
    if display.get("showDuration", False) and summary.session_start_ts > 0:
        dur_str = format_duration(max(0, int(now_ts - summary.session_start_ts)))
        if dur_str:
            duration_badge = theme.fg(dur_str, "subtext")

    title_raw = str(data.get("conversation_title") or data.get("session_title") or "").strip()
    custom_line = str(display.get("customLine") or "").strip()

    # 5. Context & Quota
    ctx = data.get("context_window") or {}
    quota = data.get("quota") or {}
    k5, k7 = select_quota_keys(quota, clean_model, model_id)
    q5_item = quota.get(k5) if k5 else None
    q7_item = quota.get(k7) if k7 else None

    header_lines: list[str] = []
    if layout == "compact":
        bar_w = adaptive_bar_width(term_width)
        ctx_short = render_context_entry(
            ctx, display, lang, theme, bar_width=bar_w, show_ratio=False, show_cache=False, show_total=False
        )
        q5_short = render_quota_entry(t(lang, "quota_5h"), q5_item, display, lang, theme, bar_width=0)
        q7_short = render_quota_entry(t(lang, "quota_7d"), q7_item, display, lang, theme, bar_width=0)
        proj = build_project_part(dir_name, git_info, theme, include_ab=bool(display.get("showGitAheadBehind", True)))
        compact_candidates = [
            [model_badge, ctx_short, proj, q5_short, q7_short, state_badge, *alert_badges, vim_badge],
            [model_badge, ctx_short, proj, q5_short, *alert_badges],
            [model_badge, ctx_short, q5_short, *alert_badges],
            [model_badge, ctx_short, *alert_badges],
        ]
        chosen_compact = next(
            (ln for segs in compact_candidates if visible_width(ln := _join(segs, sep)) <= max_w),
            _join([model_badge, *alert_badges], sep),
        )
        if chosen_compact:
            header_lines.append(chosen_compact)
    else:
        line1 = _build_header_line(
            model_badge=model_badge,
            dir_name=dir_name,
            git_info=git_info,
            state_badge=state_badge,
            alert_badges=alert_badges,
            vim_badge=vim_badge,
            duration_badge=duration_badge,
            title_raw=title_raw,
            custom_line=custom_line,
            display=display,
            theme=theme,
            sep=sep,
            max_w=max_w,
        )
        telemetry_lines = _build_telemetry_lines(
            ctx=ctx,
            q5_item=q5_item,
            q7_item=q7_item,
            display=display,
            lang=lang,
            theme=theme,
            sep=sep,
            term_width=term_width,
            max_w=max_w,
        )
        header_lines = [ln for ln in (line1, *telemetry_lines) if ln]

    activity_lines = [ln for ln in (tools_line, *agent_lines) if ln]
    output: list[str] = list(header_lines)
    if config.get("showSeparators") and header_lines and activity_lines:
        rule_w = min(max_w, max(20, max(visible_width(ln) for ln in header_lines)))
        output.append(theme.fg("─" * rule_w, "overlay"))
    output.extend(activity_lines)

    return [f"{RESET}{ln}" for ln in output]

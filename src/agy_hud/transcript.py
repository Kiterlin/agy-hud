"""Streaming tail parser for Antigravity CLI transcript.jsonl (tools, subagents, duration)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agy_hud.width import truncate_plain

MCP_TOOL_RE = re.compile(r"^mcp__.+__.+$")
CONV_ID_RE = re.compile(r'"conversationId"\s*:\s*"([0-9a-fA-F-]{8,})"')
SENDER_ID_RE = re.compile(r"\bsender=([0-9a-fA-F-]{8,})")
MAX_TAIL_BYTES = 1_048_576  # 1 MB cap to keep parsing under ~10ms


@dataclass
class AgentActivity:
    role: str
    model: str = ""
    status: str = "running"  # "running" | "completed"
    conversation_id: str = ""
    start_ts: float = 0.0
    end_ts: float = 0.0


@dataclass
class TranscriptSummary:
    running_tools: list[tuple[str, str]] = field(default_factory=list)
    completed_tools: Counter[str] = field(default_factory=Counter)
    agents: list[AgentActivity] = field(default_factory=list)
    session_start_ts: float = 0.0


def _parse_iso_ts(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        s = raw.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


def _unwrap_arg(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        s = val.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            try:
                decoded = json.loads(s)
                if isinstance(decoded, str):
                    return decoded.strip()
            except Exception:
                return s[1:-1].strip()
        return s
    return str(val).strip()


def shorten_tool_name(name: str) -> str:
    if MCP_TOOL_RE.match(name):
        return name.split("__")[-1] or name
    return name


def extract_tool_target(args: Any) -> str:
    if not isinstance(args, dict):
        return ""
    for key in ("Path", "AbsolutePath", "path", "file_path", "TargetFile", "ScriptPath"):
        if key in args:
            val = _unwrap_arg(args[key]).replace("\\", "/")
            if val:
                base = val.rstrip("/").split("/")[-1]
                return truncate_plain(base or val, 24)
    for key in ("toolSummary", "Role", "query", "Description"):
        if key in args:
            val = " ".join(_unwrap_arg(args[key]).split())
            if val:
                return truncate_plain(val, 24)
    if "CommandLine" in args:
        val = " ".join(_unwrap_arg(args["CommandLine"]).split())
        if val:
            return truncate_plain(val, 24)
    return ""


def resolve_transcript_path(data: dict[str, Any]) -> Path | None:
    raw = str(data.get("transcript_path") or "").strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw))
        if "/.gemini/antigravity/" in raw:
            candidates.append(Path(raw.replace("/.gemini/antigravity/", "/.gemini/antigravity-cli/")))
        elif "/.gemini/antigravity-cli/" in raw:
            candidates.append(Path(raw.replace("/.gemini/antigravity-cli/", "/.gemini/antigravity/")))

    conv_id = str(data.get("conversation_id") or data.get("session_id") or "").strip()
    if conv_id:
        home = Path.home()
        candidates.append(home / ".gemini" / "antigravity-cli" / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl")
        candidates.append(home / ".gemini" / "antigravity" / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl")

    for path in candidates:
        if path.is_file():
            return path
    return None


def _extract_subagent_specs(args: Any) -> list[tuple[str, str]]:
    """Extract (role, model) pairs from single or batch invoke_subagent args."""
    if not isinstance(args, dict):
        return []
    specs: list[tuple[str, str]] = []
    if "Subagents" in args:
        raw_list = args["Subagents"]
        parsed = raw_list
        if isinstance(raw_list, str):
            try:
                parsed = json.loads(_unwrap_arg(raw_list) or raw_list)
            except Exception:
                try:
                    parsed = json.loads(raw_list)
                except Exception:
                    parsed = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    role = str(item.get("Role") or item.get("TypeName") or "subagent").strip()
                    model = str(item.get("Model") or "").strip()
                    if model.lower() == "inherit":
                        model = ""
                    specs.append((role, model))
    else:
        role = _unwrap_arg(args.get("Role")) or _unwrap_arg(args.get("TypeName")) or "subagent"
        model = _unwrap_arg(args.get("Model"))
        if model.lower() == "inherit":
            model = ""
        specs.append((role, model))
    return specs


def parse_transcript(data: dict[str, Any], now_ts: float | None = None) -> TranscriptSummary:
    summary = TranscriptSummary()
    tpath = resolve_transcript_path(data)
    if not tpath:
        return summary

    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    try:
        size = tpath.stat().st_size
        with tpath.open("rb") as f:
            first_line = f.readline()
            if first_line:
                try:
                    first_obj = json.loads(first_line.decode("utf-8", errors="ignore"))
                    summary.session_start_ts = _parse_iso_ts(first_obj.get("created_at"))
                except Exception:
                    pass
            if size > MAX_TAIL_BYTES:
                f.seek(size - MAX_TAIL_BYTES)
                f.readline()  # discard partial line
                raw_bytes = f.read()
            else:
                f.seek(0)
                raw_bytes = f.read()
    except Exception:
        return summary

    pending_tools: list[tuple[str, str]] = []
    pending_agent_spawns: list[AgentActivity] = []
    agents_by_id: dict[str, AgentActivity] = {}
    all_agents: list[AgentActivity] = []

    for raw_line in raw_bytes.decode("utf-8", errors="ignore").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            step = json.loads(raw_line)
        except Exception:
            continue

        step_type = str(step.get("type") or "")
        status = str(step.get("status") or "")
        step_ts = _parse_iso_ts(step.get("created_at")) or now_ts
        tcs = step.get("tool_calls") or []
        content = str(step.get("content") or "")

        if step_type == "PLANNER_RESPONSE":
            if pending_tools:
                for name, _ in pending_tools:
                    summary.completed_tools[name] += 1
                pending_tools.clear()
            if tcs:
                for tc in tcs:
                    if not isinstance(tc, dict):
                        continue
                    raw_name = str(tc.get("name") or "")
                    tname = shorten_tool_name(raw_name)
                    if not tname:
                        continue
                    args = tc.get("args")
                    target = extract_tool_target(args)
                    pending_tools.append((tname, target))
                    if raw_name == "invoke_subagent":
                        for role, model in _extract_subagent_specs(args):
                            ag = AgentActivity(role=role, model=model, status="running", start_ts=step_ts)
                            pending_agent_spawns.append(ag)
                            all_agents.append(ag)
                    elif raw_name == "manage_subagents" and isinstance(args, dict):
                        action = _unwrap_arg(args.get("Action")).lower()
                        if action == "kill_all":
                            for ag in all_agents:
                                if ag.status == "running":
                                    ag.status = "completed"
                                    ag.end_ts = step_ts
        elif step_type == "USER_INPUT":
            if pending_tools:
                for name, _ in pending_tools:
                    summary.completed_tools[name] += 1
                pending_tools.clear()
        elif step_type == "SYSTEM_MESSAGE":
            for match in SENDER_ID_RE.finditer(content):
                sid = match.group(1)
                if sid in agents_by_id and agents_by_id[sid].status == "running":
                    agents_by_id[sid].status = "completed"
                    agents_by_id[sid].end_ts = step_ts
        elif pending_tools and status in ("DONE", "ERROR", "CANCELED"):
            done_name, _ = pending_tools.pop(0)
            summary.completed_tools[done_name] += 1
            if done_name == "invoke_subagent" and pending_agent_spawns:
                found_ids = CONV_ID_RE.findall(content)
                for cid in found_ids:
                    if pending_agent_spawns:
                        ag = pending_agent_spawns.pop(0)
                        ag.conversation_id = cid
                        agents_by_id[cid] = ag

    raw_state = str(data.get("agent_state") or "").strip().lower()
    if raw_state == "idle" and pending_tools:
        for name, _ in pending_tools:
            summary.completed_tools[name] += 1
        pending_tools.clear()

    summary.running_tools = pending_tools
    summary.agents = all_agents
    return summary

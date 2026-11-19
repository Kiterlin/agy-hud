"""Fast git status lookup and project path formatting for agy-hud."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitInfo:
    branch: str
    dirty: bool = False
    untracked: bool = False
    ahead: int = 0
    behind: int = 0


def format_project_path(cwd: str, levels: int = 1) -> str:
    if not cwd:
        return ""
    norm = os.path.normpath(cwd)
    home = os.path.normpath(str(Path.home()))
    if norm == home:
        return "~"
    parts = [p for p in Path(norm).parts if p not in (os.sep, "/")]
    if not parts:
        return "/"
    levels = max(1, min(3, int(levels)))
    return "/".join(parts[-levels:])


def read_git_head_fallback(cwd: str) -> str:
    """Read .git/HEAD directly in <1ms if git subprocess is unavailable or times out."""
    try:
        cur = Path(cwd).resolve()
        for parent in (cur, *cur.parents):
            dot_git = parent / ".git"
            if dot_git.is_dir():
                head_file = dot_git / "HEAD"
            elif dot_git.is_file():
                txt = dot_git.read_text(encoding="utf-8", errors="ignore").strip()
                if txt.startswith("gitdir:"):
                    gd = Path(txt[7:].strip())
                    if not gd.is_absolute():
                        gd = (parent / gd).resolve()
                    head_file = gd / "HEAD"
                else:
                    return ""
            else:
                continue
            if head_file.is_file():
                ref = head_file.read_text(encoding="utf-8", errors="ignore").strip()
                if ref.startswith("ref: refs/heads/"):
                    return ref[16:]
                if ref.startswith("ref: "):
                    return ref[5:].split("/")[-1]
                return f"@{ref[:7]}" if len(ref) >= 7 else ref
            return ""
    except Exception:
        return ""
    return ""


def get_git_info(cwd: str, fallback_branch: str = "", timeout: float = 0.5) -> GitInfo | None:
    def _fallback() -> GitInfo | None:
        br = fallback_branch or (read_git_head_fallback(cwd) if cwd else "")
        return GitInfo(branch=br) if br else None

    if not cwd or not os.path.isdir(cwd):
        return _fallback()

    try:
        proc = subprocess.run(
            ["git", "--no-optional-locks", "-C", cwd, "status", "--porcelain=v2", "--branch"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return _fallback()

    if proc.returncode != 0:
        return _fallback()

    branch = ""
    oid = ""
    ahead = 0
    behind = 0
    dirty = False
    untracked = False

    for line in proc.stdout.splitlines():
        if line.startswith("# branch.head "):
            branch = line[14:].strip()
        elif line.startswith("# branch.oid "):
            oid = line[13:].strip()
        elif line.startswith("# branch.ab "):
            parts = line[12:].strip().split()
            if len(parts) >= 2:
                try:
                    ahead = abs(int(parts[0]))
                    behind = abs(int(parts[1]))
                except ValueError:
                    pass
        elif line.startswith(("1 ", "2 ", "u ")):
            dirty = True
        elif line.startswith("? "):
            untracked = True

    if branch == "(detached)":
        branch = f"@{oid[:7]}" if oid and oid != "(initial)" else "detached"
    if not branch:
        branch = fallback_branch
    if not branch:
        return None

    return GitInfo(
        branch=branch,
        dirty=dirty,
        untracked=untracked,
        ahead=ahead,
        behind=behind,
    )

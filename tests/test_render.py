from __future__ import annotations

import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agy_hud.config import DEFAULT_CONFIG
from agy_hud.git_info import GitInfo
from agy_hud.render import render_hud
from agy_hud.transcript import AgentActivity, TranscriptSummary
from agy_hud.width import strip_ansi, visible_width


def sample_payload(width: int = 120) -> dict:
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
            "3p-5h": {"remaining_fraction": 0.14, "reset_in_seconds": 3900},
            "3p-weekly": {"remaining_fraction": 0.42, "reset_in_seconds": 259200},
        },
        "agent_state": "tool_use",
        "sandbox": {"enabled": False},
        "tool_confirmation_pending": False,
        "conversation_title": "Build agy-hud plugin",
        "terminal_width": width,
    }


class TestRender(unittest.TestCase):
    def test_deduplicates_effort_and_respects_width(self) -> None:
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["theme"] = "catppuccin-latte"
        summary = TranscriptSummary(
            running_tools=[("run_command", "unittest")],
            completed_tools=Counter({"read_file": 8, "edit_file": 3}),
            agents=[AgentActivity(role="Researcher", model="flash", status="running", start_ts=90.0)],
            session_start_ts=0.0,
        )
        for width in (160, 110, 82, 58):
            lines = render_hud(
                sample_payload(width),
                cfg,
                transcript_summary=summary,
                git_info_override=GitInfo(branch="main", dirty=True, ahead=1),
                use_git_override=True,
                now_ts=100.0,
            )
            self.assertGreaterEqual(len(lines), 3)
            plain = [strip_ansi(ln) for ln in lines]
            # Effort tag stripped from model name, shown once with dial symbol
            self.assertIn("[Gemini 4 Neon ◕ xhigh]", plain[0])
            self.assertNotIn("(XHigh)", plain[0])
            for ln in plain:
                self.assertLessEqual(visible_width(ln), width - 2, f"Overflow at width={width}: {ln}")

    def test_zh_hans_column_alignment(self) -> None:
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["language"] = "zh-Hans"
        cfg["theme"] = "catppuccin-macchiato"
        lines = render_hud(
            sample_payload(100),
            cfg,
            transcript_summary=TranscriptSummary(),
            git_info_override=GitInfo(branch="main"),
            use_git_override=True,
        )
        plain = [strip_ansi(ln) for ln in lines]
        # Line 2 is Context ("上下文", width 6), Line 3 starts with "5h" padded to width 6
        self.assertTrue(plain[1].startswith("上下文 "))
        self.assertTrue(plain[2].startswith("5h     "))
        self.assertIn("周限", plain[2])
        self.assertIn("缓存 90%", plain[1])

    def test_3p_quota_and_alerts_and_compact_layout(self) -> None:
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["layout"] = "compact"
        cfg["theme"] = "ansi"
        payload = sample_payload(120)
        payload["model"] = {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6 (High)"}
        payload["tool_confirmation_pending"] = True
        payload["sandbox"] = {"enabled": True}
        lines = render_hud(
            payload,
            cfg,
            transcript_summary=TranscriptSummary(),
            git_info_override=GitInfo(branch="feat"),
            use_git_override=True,
        )
        self.assertEqual(len(lines), 1)
        plain = strip_ansi(lines[0])
        self.assertIn("[Claude Sonnet 4.6 ◑ high]", plain)
        self.assertIn("14%", plain)  # 3p-5h selected
        self.assertIn("⚠ confirm", plain)
        self.assertIn("sandbox", plain)


if __name__ == "__main__":
    unittest.main()

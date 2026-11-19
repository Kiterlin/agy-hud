from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agy_hud.transcript import parse_transcript


class TestTranscript(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_running_and_completed_tools_plus_subagent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tpath = Path(tmp) / "transcript.jsonl"
            rows = [
                {"step_index": 0, "type": "USER_INPUT", "status": "DONE", "created_at": "2026-11-19T01:00:00Z"},
                {
                    "step_index": 1,
                    "type": "PLANNER_RESPONSE",
                    "status": "DONE",
                    "created_at": "2026-11-19T01:00:02Z",
                    "tool_calls": [
                        {"name": "read_file", "args": {"Path": '"/home/dev/app/main.py"'}},
                        {"name": "mcp__ctx7__query_docs", "args": {"query": '"statusLine"'}},
                        {
                            "name": "invoke_subagent",
                            "args": {"Role": '"Codebase Researcher"', "Model": '"flash"'},
                        },
                    ],
                },
                {"step_index": 2, "type": "GENERIC", "status": "DONE", "created_at": "2026-11-19T01:00:03Z", "content": "ok"},
                {"step_index": 3, "type": "GENERIC", "status": "DONE", "created_at": "2026-11-19T01:00:04Z", "content": "ok"},
                {
                    "step_index": 4,
                    "type": "GENERIC",
                    "status": "DONE",
                    "created_at": "2026-11-19T01:00:05Z",
                    "content": 'Created subagent: {"conversationId": "11111111-2222-3333-4444-555555555555"}',
                },
                {
                    "step_index": 5,
                    "type": "PLANNER_RESPONSE",
                    "status": "DONE",
                    "created_at": "2026-11-19T01:00:10Z",
                    "tool_calls": [
                        {"name": "run_command", "args": {"toolSummary": '"Run unit tests"'}},
                    ],
                },
            ]
            self._write_jsonl(tpath, rows)

            # Active tool_use: run_command is running, subagent is running
            summary = parse_transcript(
                {"transcript_path": str(tpath), "agent_state": "tool_use"},
                now_ts=1795050020.0,
            )
            self.assertEqual(summary.running_tools, [("run_command", "Run unit tests")])
            self.assertEqual(summary.completed_tools["read_file"], 1)
            self.assertEqual(summary.completed_tools["query_docs"], 1)
            self.assertEqual(summary.completed_tools["invoke_subagent"], 1)
            self.assertEqual(len(summary.agents), 1)
            self.assertEqual(summary.agents[0].role, "Codebase Researcher")
            self.assertEqual(summary.agents[0].model, "flash")
            self.assertEqual(summary.agents[0].status, "running")

            # Add subagent completion message + idle agent state
            rows.append(
                {
                    "step_index": 6,
                    "type": "SYSTEM_MESSAGE",
                    "status": "DONE",
                    "created_at": "2026-11-19T01:00:18Z",
                    "content": "[Message] sender=11111111-2222-3333-4444-555555555555 content=Done",
                }
            )
            self._write_jsonl(tpath, rows)

            summary2 = parse_transcript(
                {"transcript_path": str(tpath), "agent_state": "idle"},
                now_ts=1795050025.0,
            )
            self.assertEqual(summary2.running_tools, [])
            self.assertEqual(summary2.completed_tools["run_command"], 1)
            self.assertEqual(summary2.agents[0].status, "completed")


if __name__ == "__main__":
    unittest.main()

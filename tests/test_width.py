from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agy_hud.git_info import format_project_path
from agy_hud.width import adaptive_bar_width, pad_right_width, strip_ansi, truncate_plain, visible_width


class TestWidth(unittest.TestCase):
    def test_strip_ansi_and_visible_width(self) -> None:
        colored = "\033[1;38;2;136;57;239m[Gemini 4 Neon]\033[0m"
        self.assertEqual(strip_ansi(colored), "[Gemini 4 Neon]")
        self.assertEqual(visible_width(colored), 15)

    def test_cjk_width_and_padding(self) -> None:
        self.assertEqual(visible_width("上下文"), 6)
        self.assertEqual(visible_width("周限"), 4)
        padded = pad_right_width("周限", 6)
        self.assertEqual(visible_width(padded), 6)
        self.assertEqual(padded, "周限  ")

    def test_truncate_plain_cjk(self) -> None:
        self.assertEqual(truncate_plain("重构 Antigravity 状态栏", 10), "重构 Anti…")
        self.assertLessEqual(visible_width(truncate_plain("重构 Antigravity 状态栏", 10)), 10)
        self.assertEqual(truncate_plain("short", 10), "short")

    def test_adaptive_bar_width(self) -> None:
        self.assertEqual(adaptive_bar_width(140), 10)
        self.assertEqual(adaptive_bar_width(100), 10)
        self.assertEqual(adaptive_bar_width(80), 6)
        self.assertEqual(adaptive_bar_width(50), 4)

    def test_format_project_path_cross_platform(self) -> None:
        self.assertEqual(format_project_path(r"C:\Users\dev\projects\agy-hud", 1), "agy-hud")
        self.assertEqual(format_project_path(r"C:\Users\dev\projects\agy-hud", 2), "projects/agy-hud")
        self.assertEqual(format_project_path("/home/dev/projects/agy-hud", 1), "agy-hud")
        self.assertEqual(format_project_path("/home/dev/projects/agy-hud", 2), "projects/agy-hud")


if __name__ == "__main__":
    unittest.main()

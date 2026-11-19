from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agy_hud.config import load_config, normalize_language, save_config


class TestConfig(unittest.TestCase):
    def test_normalize_language(self) -> None:
        self.assertEqual(normalize_language("zh"), "zh-Hans")
        self.assertEqual(normalize_language("zh-CN"), "zh-Hans")
        self.assertEqual(normalize_language("zh-TW"), "zh-Hant")
        self.assertEqual(normalize_language("en"), "en")

    def test_preset_with_manual_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "agy-hud.json"
            p.write_text(
                json.dumps(
                    {
                        "preset": "minimal",
                        "language": "zh",
                        "theme": "tokyo-night",
                        "display": {"showGit": True, "contextWarningThreshold": 65},
                        "colors": {"model": "#FF00AA"},
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_config(p)
            self.assertEqual(cfg["preset"], "minimal")
            self.assertEqual(cfg["language"], "zh-Hans")
            self.assertEqual(cfg["theme"], "tokyo-night")
            # Minimal turns off tools, but explicit override re-enables git
            self.assertFalse(cfg["display"]["showTools"])
            self.assertTrue(cfg["display"]["showGit"])
            self.assertEqual(cfg["display"]["contextWarningThreshold"], 65)
            self.assertEqual(cfg["colors"]["model"], "#FF00AA")

    def test_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "nested" / "agy-hud.json"
            cfg = load_config(p)
            cfg["layout"] = "compact"
            save_config(cfg, p)
            reloaded = load_config(p)
            self.assertEqual(reloaded["layout"], "compact")


if __name__ == "__main__":
    unittest.main()

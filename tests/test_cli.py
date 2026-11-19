from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "bin" / "agy-hud.py"


class TestCLI(unittest.TestCase):
    def _run(self, args: list[str], env_extra: dict[str, str], stdin_text: str = "") -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(LAUNCHER), *args],
            input=stdin_text,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_install_doctor_preview_uninstall_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cli_dir = Path(tmp) / "agy-cli"
            cli_dir.mkdir()
            settings_path = cli_dir / "settings.json"
            original_sl = {"type": "command", "command": "echo old", "enabled": True}
            settings_path.write_text(json.dumps({"colorScheme": "light", "statusLine": original_sl}), encoding="utf-8")

            env = {"AGY_CLI_DIR": str(cli_dir), "AGY_HUD_CONFIG": str(cli_dir / "agy-hud.json")}

            r_install = self._run(["--install", "--preset", "essential", "--language", "zh-Hans"], env)
            self.assertEqual(r_install.returncode, 0, r_install.stderr)
            updated = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(updated["statusLine"]["enabled"])
            self.assertIn("agy-hud.py", updated["statusLine"]["command"])
            self.assertTrue((cli_dir / "agy-hud.backup.json").is_file())

            r_doc = self._run(["--doctor"], env)
            self.assertEqual(r_doc.returncode, 0, r_doc.stderr)
            self.assertIn("Render smoke", r_doc.stdout)
            self.assertIn("catppuccin-latte", r_doc.stdout)

            r_prev = self._run(["--preview"], env)
            self.assertEqual(r_prev.returncode, 0, r_prev.stderr)
            self.assertIn("agy-hud", r_prev.stdout)

            # Stdin rendering with sample payload
            sample = (REPO_ROOT / "examples" / "sample-payload.json").read_text(encoding="utf-8")
            r_stdin = self._run([], env, stdin_text=sample)
            self.assertEqual(r_stdin.returncode, 0, r_stdin.stderr)
            self.assertIn("Gemini 4 Neon", r_stdin.stdout)

            # Malformed stdin exits cleanly without stderr noise
            r_bad = self._run([], env, stdin_text="{broken")
            self.assertEqual(r_bad.returncode, 0)
            self.assertEqual(r_bad.stdout, "")

            # Uninstall restores original statusLine
            r_uninst = self._run(["--uninstall"], env)
            self.assertEqual(r_uninst.returncode, 0, r_uninst.stderr)
            restored = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(restored["statusLine"], original_sl)
            self.assertFalse((cli_dir / "agy-hud.backup.json").exists())


if __name__ == "__main__":
    unittest.main()

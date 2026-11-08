"""真实执行 probe_tools.py：缺失、版本不符、非零退出与未提供 --expect 四种情形。

用临时目录里的桩可执行文件代替真实工具链，因此用例在无 Go/Rust/JDK 的环境也能跑。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "probe_tools.py"


class ProbeToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="probe-tools-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.project = self.directory / "project"
        self.project.mkdir()
        self.bin = self.directory / "bin"
        self.bin.mkdir()

    def install(self, name: str, *, output: str, exit_code: int = 0) -> None:
        """写一个只打印版本并按规定退出码结束的桩程序。"""
        path = self.bin / name
        path.write_text(f"#!/bin/sh\necho '{output}'\nexit {exit_code}\n", encoding="utf-8")
        path.chmod(0o755)

    def run_probe(self, *args: str) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--project", str(self.project), *args],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": str(self.bin)},
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        return result.returncode, payload

    def test_missing_tool_is_reported_and_fails(self) -> None:
        code, payload = self.run_probe("--require", "go")
        self.assertEqual(2, code, payload)
        self.assertFalse(payload["available"])
        self.assertEqual("missing", payload["tools"][0]["status"])
        self.assertIn("Go 工具链", payload["tools"][0]["hint"])

    def test_version_mismatch_is_reported_and_fails(self) -> None:
        self.install("go", output="go version go1.99.0 linux/amd64")
        code, payload = self.run_probe("--require", "go", "--expect", "go=1.94.0")
        self.assertEqual(2, code, payload)
        tool = payload["tools"][0]
        self.assertEqual("version-mismatch", tool["status"])
        self.assertEqual("1.99.0", tool["version"])
        self.assertEqual("1.94.0", tool["expected"])

    def test_nonzero_exit_is_unavailable_and_fails(self) -> None:
        self.install("go", output="go version go1.94.0 linux/amd64", exit_code=1)
        code, payload = self.run_probe("--require", "go")
        self.assertEqual(2, code, payload)
        tool = payload["tools"][0]
        self.assertEqual("unavailable", tool["status"])
        self.assertEqual(1, tool["exit"])
        self.assertFalse(payload["available"])

    def test_matching_version_passes(self) -> None:
        self.install("go", output="go version go1.94.0 linux/amd64")
        code, payload = self.run_probe("--require", "go", "--expect", "go=1.94.0")
        self.assertEqual(0, code, payload)
        self.assertTrue(payload["available"])
        self.assertEqual("available", payload["tools"][0]["status"])

    def test_tool_without_expect_does_not_claim_version_match(self) -> None:
        self.install("go", output="go version go1.94.0 linux/amd64")
        code, payload = self.run_probe("--require", "go")
        self.assertEqual(0, code, payload)
        tool = payload["tools"][0]
        self.assertEqual("available", tool["status"])
        self.assertIsNone(tool["expected"])
        self.assertEqual("1.94.0", tool["version"])

    def test_expect_for_unselected_tool_is_rejected(self) -> None:
        code, _ = self.run_probe("--require", "go", "--expect", "cargo=1.94.0")
        self.assertEqual(2, code, "未选中的工具不能作为 --expect 目标")

    def test_probe_is_not_a_quality_check(self) -> None:
        self.install("go", output="go version go1.94.0 linux/amd64")
        _, payload = self.run_probe("--require", "go")
        self.assertIn("不代表", payload["scope"])


if __name__ == "__main__":
    unittest.main()
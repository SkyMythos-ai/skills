"""真实执行 quality-gates.md 中 Q1 的一对 shell 门禁示例。

`gate-example: shell-bad` / `shell-good` 是本文唯一被自动校验的门禁片段：
用桩 linter 模拟检查失败与成功，断言 bad 吞掉失败、good 传播失败。

片段本身在文档里声明为 Bash 执行（`pipefail` 是 Bash 特性，dash/POSIX sh 不支持），
所以用 `bash -c` 跑原始文本，不用 `sh`。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SHELL = shutil.which("bash")
DOC = Path(__file__).parents[1] / "references" / "quality-gates.md"
BLOCK = re.compile(
    r"<!--\s*gate-example:\s*(shell-bad|shell-good)\s*-->\s*\n```bash\n(.*?)\n```",
    re.DOTALL,
)


def extract_blocks() -> dict[str, str]:
    content = DOC.read_text(encoding="utf-8")
    blocks: dict[str, str] = {}
    for kind, code in BLOCK.findall(content):
        if kind in blocks:
            raise AssertionError(f"{DOC}: gate-example {kind} 重复")
        blocks[kind] = code
    return blocks


@unittest.skipUnless(SHELL, "需要 bash：文档片段使用 set -o pipefail")
class GateExampleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="gate-example-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.blocks = extract_blocks()

    def run_block(
        self, name: str, *, linter_exit: int, log_as_directory: bool = False
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        """在隔离目录里用桩 golangci-lint 执行文档中的原始片段。"""
        label = f"{name}-{linter_exit}-{int(log_as_directory)}"
        bin_dir = self.directory / f"bin-{label}"
        bin_dir.mkdir()
        stub = bin_dir / "golangci-lint"
        stub.write_text(
            f"#!/bin/sh\necho 'stub: 1 issue found'\nexit {linter_exit}\n", encoding="utf-8"
        )
        stub.chmod(0o755)
        work = self.directory / f"work-{label}"
        work.mkdir()
        if log_as_directory:
            (work / "lint.log").mkdir()
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        result = subprocess.run(
            [SHELL, "-c", self.blocks[name]], cwd=work, env=env,
            capture_output=True, text=True, timeout=30,
        )
        return result, work

    def test_markers_form_one_declared_pair(self) -> None:
        self.assertEqual({"shell-bad", "shell-good"}, set(self.blocks))
        self.assertIn("set -euo pipefail", self.blocks["shell-good"])
        self.assertNotIn("pipefail", self.blocks["shell-bad"])

    def test_bad_swallows_linter_failure(self) -> None:
        result, work = self.run_block("shell-bad", linter_exit=1)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("stub: 1 issue found", (work / "lint.log").read_text(encoding="utf-8"))

    def test_good_propagates_linter_failure(self) -> None:
        result, work = self.run_block("shell-good", linter_exit=1)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("stub: 1 issue found", (work / "lint.log").read_text(encoding="utf-8"))

    def test_good_passes_when_linter_passes(self) -> None:
        result, work = self.run_block("shell-good", linter_exit=0)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((work / "lint.log").is_file())

    def test_good_fails_when_log_write_fails(self) -> None:
        result, _ = self.run_block("shell-good", linter_exit=0, log_as_directory=True)
        self.assertNotEqual(0, result.returncode, "日志写入失败必须让检查失败")


if __name__ == "__main__":
    unittest.main()
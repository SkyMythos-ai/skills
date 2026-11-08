"""校验 verify_examples.py 的标记解析：标记与代码块不匹配必须报错。"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_examples.py"
SPEC = importlib.util.spec_from_file_location("personal_verify_examples", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


GOOD = "package main\n\nfunc main() {{}}\n"

class CollectExamplesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="verify-examples-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def document(self, text: str) -> Path:
        path = self.directory / "cases-go.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_marker_without_code_block_is_an_error(self) -> None:
        document = self.document("<!-- example: g1-bad -->\n\n没有代码块\n")
        with self.assertRaisesRegex(ValueError, "标记与代码块不匹配"):
            MODULE.collect_examples(document, "go", set())

    def test_trailing_marker_without_code_block_is_an_error(self) -> None:
        document = self.document(
            "<!-- example: g1-bad -->\n```go\npackage main\n```\n\n"
            "<!-- example: g1-good -->\n\n缺少代码块\n"
        )
        with self.assertRaisesRegex(ValueError, "标记与代码块不匹配"):
            MODULE.collect_examples(document, "go", set())

    def test_unpaired_bad_good_is_an_error(self) -> None:
        document = self.document("<!-- example: g1-bad -->\n```go\npackage main\n```\n")
        with self.assertRaisesRegex(ValueError, "未配对"):
            MODULE.collect_examples(document, "go", set())

    def test_language_mismatch_is_an_error(self) -> None:
        document = self.document(
            "<!-- example: g1-bad -->\n```rust\nfn main() {{}}\n```\n"
        )
        with self.assertRaisesRegex(ValueError, "重复 ID 或语言不符"):
            MODULE.collect_examples(document, "go", set())

    def test_duplicate_identifier_is_an_error(self) -> None:
        document = self.document(
            "<!-- example: g1-bad -->\n```go\npackage main\n```\n"
            "<!-- example: g1-good -->\n```go\npackage main\n```\n"
        )
        MODULE.collect_examples(document, "go", set())
        with self.assertRaisesRegex(ValueError, "重复 ID"):
            MODULE.collect_examples(document, "go", {"g1-bad"})

    def test_matched_pair_is_returned_in_order(self) -> None:
        document = self.document(
            "<!-- example: g1-bad -->\n```go\npackage main\n```\n"
            "<!-- example: g1-good -->\n```go\npackage main\n```\n"
        )
        examples = MODULE.collect_examples(document, "go", set())
        self.assertEqual(["g1-bad", "g1-good"], [identifier for identifier, _ in examples])

    def test_repository_documents_are_well_formed(self) -> None:
        references = Path(__file__).parents[1] / "references"
        seen: set[str] = set()
        total = 0
        for language in ("go", "rust", "java"):
            total += len(MODULE.collect_examples(references / f"cases-{language}.md",
                                                language, seen))
        self.assertEqual(24, total, "仓库内应保持 24 个 Go/Rust/Java 案例")


if __name__ == "__main__":
    unittest.main()
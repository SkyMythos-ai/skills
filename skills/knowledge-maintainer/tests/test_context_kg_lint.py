from __future__ import annotations

import importlib.util
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "context_kg_lint.py"
SPEC = importlib.util.spec_from_file_location("context_kg_lint", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ContextKgLintTest(unittest.TestCase):
    def lint(self, files: dict[str, str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "context-kg"
            for relative_path, content in files.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                result = MODULE.lint(root)
            return result, output.getvalue()

    def test_accepts_okf_bundle(self) -> None:
        result, output = self.lint(
            {
                "index.md": "---\nokf_version: \"0.2\"\n---\n# Knowledge\n\n* [Cache](technical/cache.md) - Cache policy.\n",
                "technical/cache.md": "---\ntype: Architecture Decision\ntitle: Cache\ngenerated: { by: agent/1.0, at: 2026-08-22T10:00:00+08:00 }\nverified: { by: human:reviewer, at: 2026-08-22T11:00:00+08:00 }\nstale_after: 2026-12-31T00:00:00Z\nsources:\n  - resource: /references/cache.yaml\n---\n\n# Cache\n",
                "references/cache.yaml": "source: redis\n",
                "log.md": "# Log\n\n## 2026-08-22\n* **Update**: Cache.\n\n## 2026-08-21\n* **Creation**: Bundle.\n",
            }
        )
        self.assertEqual(0, result, output)
        self.assertIn("OKF v0.2 基础结构检查通过", output)

    def test_rejects_missing_type_and_numeric_sources(self) -> None:
        result, output = self.lint(
            {
                "index.md": "# Knowledge\n\n* [Bad](bad.md) - Invalid concept.\n",
                "bad.md": "---\ntitle: Bad\nsources: 0\n---\n\n# Bad\n",
            }
        )
        self.assertEqual(1, result)
        self.assertIn("缺少非空 type", output)
        self.assertIn("sources 必须是来源 mapping 列表", output)

    def test_rejects_frontmatter_in_nested_index(self) -> None:
        result, output = self.lint(
            {
                "index.md": "# Knowledge\n\n* [Technical](technical/) - Technical knowledge.\n",
                "technical/index.md": "---\ntitle: Technical\n---\n# Technical\n",
            }
        )
        self.assertEqual(1, result)
        self.assertIn("只有 bundle 根 index.md 可以包含 frontmatter", output)

    def test_broken_link_is_only_a_warning(self) -> None:
        result, output = self.lint(
            {
                "index.md": "# Knowledge\n\n* [Future](future.md) - Planned concept.\n",
            }
        )
        self.assertEqual(0, result, output)
        self.assertIn("断开的 Markdown 链接", output)

    def test_allows_same_basename_in_different_directories(self) -> None:
        result, output = self.lint(
            {
                "index.md": "# Knowledge\n\n* [Business](business/) - Business knowledge.\n* [Technical](technical/) - Technical knowledge.\n",
                "business/cache.md": "---\ntype: Business Concept\n---\n",
                "technical/cache.md": "---\ntype: Technical Concept\n---\n",
            }
        )
        self.assertEqual(0, result, output)

    def test_rejects_attested_computation_without_runtime(self) -> None:
        result, output = self.lint(
            {
                "index.md": "# Knowledge\n\n* [Revenue](revenue.md) - Revenue computation.\n",
                "revenue.md": "---\ntype: Attested Computation\n---\n",
            }
        )
        self.assertEqual(1, result)
        self.assertIn("Attested Computation 缺少非空 runtime", output)

    def test_rejects_malformed_index(self) -> None:
        result, output = self.lint(
            {
                "index.md": "This is not an OKF index.\n",
            }
        )
        self.assertEqual(1, result)
        self.assertIn("index.md 必须包含 section heading", output)
        self.assertIn("index.md 必须包含 Markdown 列表链接条目", output)

    def test_warns_when_nested_index_is_missing(self) -> None:
        result, output = self.lint(
            {
                "index.md": "# Knowledge\n\n* [Technical](technical/) - Technical knowledge.\n",
                "technical/cache.md": "---\ntype: Reference\n---\n",
                "technical/storage.md": "---\ntype: Reference\n---\n",
            }
        )
        self.assertEqual(0, result, output)
        self.assertIn("technical/index.md: 缺失", output)


if __name__ == "__main__":
    unittest.main()

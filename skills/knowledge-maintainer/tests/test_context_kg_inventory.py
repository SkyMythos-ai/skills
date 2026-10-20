from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "context_kg_inventory.py"
SPEC = importlib.util.spec_from_file_location("context_kg_inventory", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def concept(kind: str = "Concept", extra: str = "", body: str = "# Page\n") -> str:
    return f"---\ntype: {kind}\n{extra}---\n{body}"


class InventoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "context-kg"
        self.root.mkdir()

    def write(self, relative: str, content: str | bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        return path

    def codes(self, result: dict) -> set[str]:
        return {item["code"] for item in result["diagnostics"]}

    def test_all_branches_unknown_type_and_145_concepts(self) -> None:
        self.write("index.md", "# Knowledge\n")
        self.write("business/index.md", "# Business\n")
        self.write("technical/log.md", "# Log\n")
        branches = ("business", "technical", "quality", "tasks", "_meta")
        for number in range(145):
            self.write(f"{branches[number % 5]}/item-{number:03d}.md", concept())
        self.write("technical/custom.md", concept("Unknown Project Type"))
        self.write("quality/chart.tsv", b"key\tvalue\n")
        result = MODULE.scan_bundle(self.root)
        self.assertEqual(146, result["counts"]["concept"])
        self.assertEqual(150, result["counts"]["total"])
        self.assertEqual("concept", result["files"]["business/item-000.md"]["kind"])
        self.assertEqual("asset", result["files"]["quality/chart.tsv"]["kind"])
        self.assertEqual("unknown", next(item for item in result["classifications"]
                                         if item["path"] == "technical/custom.md")["role"])
        self.assertNotIn("missing_type", self.codes(result))
        json.dumps(result)

    def test_missing_frontmatter_keeps_entry_and_git_status(self) -> None:
        self.write("index.md", "# Knowledge\n")
        self.write("business/regular.md", concept())
        self.write("tasks/ignored.md", "# No frontmatter\n")
        self.write("technical/new.md", concept())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(".gitignore", "tasks/\n")
        subprocess.run(["git", "add", ".gitignore", "index.md", "business/regular.md"],
                       cwd=self.root, check=True)
        result = MODULE.scan_bundle(self.root)
        self.assertEqual("tracked", result["files"]["business/regular.md"]["git_status"])
        self.assertEqual("ignored", result["files"]["tasks/ignored.md"]["git_status"])
        self.assertEqual("untracked", result["files"]["technical/new.md"]["git_status"])
        self.assertEqual({}, result["files"]["tasks/ignored.md"]["metadata"])
        self.assertIn("invalid_frontmatter", self.codes(result))

    def test_crlf_yaml_unknown_fields_and_date_round_trip(self) -> None:
        raw = ("---\r\ntype: Concept\r\ncustom: {answer: 42, nested: [a, b]}\r\n"
               "updated: 2026-10-20\r\n---\r\n# Body\r\n")
        metadata, body = MODULE.parse_document(raw)
        self.assertEqual(42, metadata["custom"]["answer"])
        self.assertEqual("# Body\r\n", body)
        rendered = MODULE.render_document(metadata, body)
        again, again_body = MODULE.parse_document(rendered)
        self.assertEqual(metadata, again)
        self.assertEqual(body, again_body)
        self.write("index.md", "# Knowledge\n")
        self.write("technical/page.md", raw)
        result = MODULE.scan_bundle(self.root)
        self.assertEqual("2026-10-20", result["files"]["technical/page.md"]["metadata"]["updated"])
        json.dumps(result)

    def test_io_and_utf8_errors_fail_scan(self) -> None:
        self.write("index.md", "# Knowledge\n")
        self.write("business/bad.md", b"\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8|decode|读取文件失败"):
            MODULE.scan_bundle(self.root)
        (self.root / "business/bad.md").unlink()
        self.write("business/good.md", concept())
        original = MODULE.os.scandir

        def fail(directory: Path):
            if Path(directory) == (self.root / "business").resolve():
                raise OSError("injected directory failure")
            return original(directory)

        with patch.object(MODULE.os, "scandir", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "injected directory failure"):
                MODULE.scan_bundle(self.root)

    def test_name_review_and_lifecycle_are_advisory(self) -> None:
        self.write("index.md", "# Knowledge\n")
        self.write("business/TC-ORDER-042.md", concept("Test Case"))
        self.write("technical/protocol-v2.md", concept("Contract"))
        self.write("technical/research/run-2026-10-20.md", concept("Research Report"))
        self.write("tasks/todo.md", concept("Task Plan"))
        self.write("technical/history/old.md", concept("Architecture Decision", "status: stable\n"))
        self.write("technical/retired-decision.md", concept("Architecture Decision", "status: stable\n"))
        self.write("technical/page-final.md", concept("Concept", "stale_after: 2026-01-01T00:00:00Z\n"))
        self.write("quality/test-standard.md", concept("Test Case Standard"))
        self.write("quality/code-standard.md", concept("Test Code Standard"))
        self.write("technical/ARCHIVE/history.md", concept("Concept", "status: stable\n"))
        self.write("technical/ARCHIVE/retired.md", concept(
            "Architecture Decision", "status: deprecated\nlifecycle:\n  archive:\n    reason: Superseded by a new decision\n"
        ))
        result = MODULE.scan_bundle(self.root, datetime(2026, 10, 20, tzinfo=timezone.utc))
        by_path = {}
        for item in result["diagnostics"]:
            by_path.setdefault(item["path"], set()).add(item["code"])
        self.assertIn("name_not_kebab_case", by_path["business/TC-ORDER-042.md"])
        self.assertNotIn("name_not_kebab_case", by_path.get("technical/protocol-v2.md", set()))
        self.assertNotIn("status_name_review", by_path.get("technical/research/run-2026-10-20.md", set()))
        self.assertNotIn("status_name_review", by_path.get("tasks/todo.md", set()))
        self.assertNotIn("archive_status_mismatch", by_path.get("technical/history/old.md", set()))
        self.assertNotIn("archive_status_mismatch", by_path.get("technical/retired-decision.md", set()))
        self.assertIn("stale_after_due", by_path["technical/page-final.md"])
        self.assertIn("status_name_review", by_path["technical/page-final.md"])
        self.assertIn("archive_status_mismatch", by_path["technical/ARCHIVE/history.md"])
        self.assertNotIn("deprecated_context_missing", by_path.get("technical/ARCHIVE/retired.md", set()))
        roles = {item["path"]: item["role"] for item in result["classifications"]}
        self.assertEqual("standards", roles["quality/test-standard.md"])
        self.assertEqual("standards", roles["quality/code-standard.md"])

    def test_rewrite_links_and_sources_when_moving(self) -> None:
        self.write("index.md", "# Knowledge\n")
        self.write("technical/old.md", concept())
        self.write("technical/target.md", concept())
        self.write("technical/asset file.tsv", "a\tb\n")
        project = self.root.parent / "project.md"
        project.write_text("# Project\n")
        old = concept("Concept", (
            "custom: {answer: 42}\n"
            "sources:\n  - resource: ../../project.md\n  - resource: asset%20file.tsv\n"
            "  - resource: https://example.com/a\nlinks: [technical/target]\n"),
            "[Target](target.md#part) ![File](<asset file.tsv?raw=1#row>)\n"
            "[Root](/technical/target.md) [Web](https://example.com/a) [Here](#part)\n"
            "[id]: target.md?view=1#part\n"
            "```md\n[Code](target.md)\n```\n")
        result = MODULE.rewrite_document(
            old, "technical/old.md", "technical/contracts/new.md",
            {"technical/old.md": "technical/contracts/new.md",
             "technical/target.md": "business/target.md"},
            self.root, {"technical/old.md", "technical/target.md", "technical/asset file.tsv"},
        )
        meta, body = MODULE.parse_document(result)
        self.assertEqual(42, meta["custom"]["answer"])
        self.assertEqual("../../../project.md", meta["sources"][0]["resource"])
        self.assertEqual("../asset%20file.tsv", meta["sources"][1]["resource"])
        self.assertEqual("https://example.com/a", meta["sources"][2]["resource"])
        self.assertEqual(["business/target"], meta["links"])
        self.assertIn("[Target](../../business/target.md#part)", body)
        self.assertIn("![File](<../asset file.tsv?raw=1#row>)", body)
        self.assertIn("[Root](/business/target.md)", body)
        self.assertIn("[id]: ../../business/target.md?view=1#part", body)
        self.assertIn("```md\n[Code](target.md)\n```", body)
        self.assertIn("[Here](#part)", body)

    def test_relative_metadata_links_and_sources_are_resolved(self) -> None:
        self.write("index.md", "# Knowledge\n")
        self.write("technical/contracts/page.md", concept())
        self.write("technical/a.md", concept())
        self.write("technical/source.tsv", "key\tvalue\n")
        original = concept("Concept", (
            "custom: {answer: 42}\n"
            "links: [../a.md, /technical/a.md, technical/a]\n"
            "sources:\n  - resource: ../source.tsv\n"
            "  - resource: https://example.com/spec.md\n"
            "  - resource: project-scope\n"
        ))
        self.write("technical/contracts/page.md", original)
        scan = MODULE.scan_bundle(self.root)
        resolved = {(item["field"], item["target"]): item.get("resolved")
                    for item in scan["references"] if item["path"] == "technical/contracts/page.md"}
        self.assertEqual("technical/source.tsv", resolved[("source", "../source.tsv")])
        self.assertIsNone(resolved[("source", "https://example.com/spec.md")])
        self.assertIsNone(resolved[("source", "project-scope")])
        self.assertEqual("technical/a.md", resolved[("links", "../a.md")])
        rewritten = MODULE.rewrite_document(
            original, "technical/contracts/page.md", "quality/page.md",
            {"technical/a.md": "business/a.md"}, self.root,
            {"technical/contracts/page.md", "technical/a.md", "technical/source.tsv"},
        )
        metadata, _ = MODULE.parse_document(rewritten)
        self.assertEqual(["../business/a.md", "/business/a.md", "business/a"], metadata["links"])
        self.assertEqual("../technical/source.tsv", metadata["sources"][0]["resource"])
        self.assertEqual("https://example.com/spec.md", metadata["sources"][1]["resource"])
        self.assertEqual("project-scope", metadata["sources"][2]["resource"])

    def test_rewrite_returns_original_when_semantics_unchanged(self) -> None:
        original = "---\r\ntype: Concept\r\ncustom: {answer: 42}\r\n---\r\n# Plain\r\n"
        rewritten = MODULE.rewrite_document(
            original, "technical/old.md", "technical/new.md", {}, self.root, {"technical/old.md"}
        )
        self.assertEqual(original, rewritten)

    def test_reference_diagnostics_ambiguity_directory_and_cycle(self) -> None:
        known = {"index.md", "business/cache.md", "technical/cache.md",
                 "business/index.md", "technical/a.md", "technical/b.md"}
        texts = {
            "index.md": "# Root\n[Business](business/) [Missing](missing.md)\n",
            "technical/a.md": concept("Concept", "links: [cache]\nsuperseded_by: technical/b\n"),
            "technical/b.md": concept("Concept", "superseded_by: technical/a\n"),
        }
        diagnostics = MODULE.reference_diagnostics(self.root, texts, known)
        codes = {item["code"] for item in diagnostics}
        self.assertIn("broken_markdown_link", codes)
        self.assertIn("ambiguous_concept_link", codes)
        self.assertIn("superseded_cycle", codes)
        self.assertEqual(2, sum(item["code"] == "superseded_cycle" for item in diagnostics))
        self.assertEqual(1, sum(item["code"] == "broken_markdown_link" for item in diagnostics))

    def test_unsupported_link_is_reported_and_rewrite_refuses(self) -> None:
        self.write("index.md", "# Knowledge\n")
        source = "# Page\n[Complex](file(name).md)\n```md\n[Code](file(name).md)\n```\n"
        diagnostics = MODULE.reference_diagnostics(
            self.root, {"technical/page.md": source}, {"technical/page.md", "index.md"}
        )
        self.assertEqual(1, sum(item["code"] == "unsupported_markdown_link" for item in diagnostics))
        with self.assertRaisesRegex(ValueError, "无法安全重写"):
            MODULE.rewrite_document(source, "technical/page.md", "technical/new.md", {},
                                    self.root, {"technical/page.md", "index.md"})

    def test_inline_code_spans_are_not_links(self) -> None:
        original = concept(body=(
            "`[one](missing.md)` ``[two](missing.md)`` [Real](old.md)\n"
            "``[across](missing.md)\n[also](missing.md)``\n"
            "```md\n[fenced](missing.md)\n```\n"
        ))
        known = {"technical/page.md", "technical/old.md"}
        diagnostics = MODULE.reference_diagnostics(
            self.root, {"technical/page.md": original}, known
        )
        self.assertNotIn("broken_markdown_link", {item["code"] for item in diagnostics})
        self.assertNotIn("unsupported_markdown_link", {item["code"] for item in diagnostics})
        rewritten = MODULE.rewrite_document(
            original, "technical/page.md", "technical/moved/page.md",
            {"technical/old.md": "business/new.md"}, self.root, known
        )
        _, body = MODULE.parse_document(rewritten)
        self.assertIn("`[one](missing.md)` ``[two](missing.md)`` [Real](../../business/new.md)", body)
        self.assertIn("``[across](missing.md)\n[also](missing.md)``", body)
        self.assertIn("[fenced](missing.md)", body)

    def test_unclosed_backtick_is_literal_so_link_remains_active(self) -> None:
        original = "# Page\n`unclosed [Real](old.md)\n"
        diagnostics = MODULE.reference_diagnostics(
            self.root, {"technical/page.md": original}, {"technical/page.md"}
        )
        self.assertIn("broken_markdown_link", {item["code"] for item in diagnostics})
        rewritten = MODULE.rewrite_document(
            original, "technical/page.md", "technical/moved/page.md", {},
            self.root, {"technical/page.md"}
        )
        self.assertIn("`unclosed [Real](../old.md)", rewritten)

    def test_crlf_document_remains_crlf_after_reference_change(self) -> None:
        original = ("---\r\ntype: Concept\r\ncustom: {answer: 42}\r\n---\r\n"
                    "# Page\r\n[Target](old.md)\r\n")
        rewritten = MODULE.rewrite_document(
            original, "technical/page.md", "technical/contracts/page.md",
            {"technical/old.md": "business/new.md"}, self.root,
            {"technical/page.md", "technical/old.md"},
        )
        self.assertIn("[Target](../../business/new.md)\r\n", rewritten)
        self.assertNotIn("\n", rewritten.replace("\r\n", ""))
        self.assertEqual(42, MODULE.parse_document(rewritten)[0]["custom"]["answer"])


if __name__ == "__main__":
    unittest.main()

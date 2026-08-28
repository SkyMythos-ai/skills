from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "context_kg_search.py"
SPEC = importlib.util.spec_from_file_location("context_kg_search", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ContextKgSearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "context-kg"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def concept(
        self,
        relative_path: str,
        *,
        type_: str = "Reference",
        title: str = "",
        description: str = "",
        tags: str = "[]",
        status: str = "stable",
        body: str = "",
        stale_after: str | None = None,
        generated_at: str | None = None,
    ) -> None:
        stale_line = f"stale_after: {stale_after}\n" if stale_after else ""
        generated_line = (
            f"generated: {{ by: agent/test, at: {generated_at} }}\n"
            if generated_at
            else ""
        )
        self.write(
            relative_path,
            "---\n"
            f"type: {type_}\n"
            f"title: {title}\n"
            f"description: {description}\n"
            f"tags: {tags}\n"
            f"status: {status}\n"
            f"{stale_line}"
            f"{generated_line}"
            "---\n\n"
            f"{body}\n",
        )

    def search(self, query: str, **kwargs):
        return MODULE.search(
            self.root,
            query,
            now=datetime(2026, 8, 29, tzinfo=timezone.utc),
            **kwargs,
        )

    def test_metadata_ranking_is_explainable_and_deterministic(self) -> None:
        self.concept("technical/cache.md", title="Cache", description="cache")
        self.concept("technical/other.md", description="cache")

        results = self.search("cache")

        self.assertEqual(["technical/cache.md", "technical/other.md"], [r.path for r in results])
        self.assertGreater(results[0].score, results[1].score)
        self.assertEqual(("path", "filename", "title", "description"), results[0].matched_fields)
        self.assertIn("title(100x1)", results[0].score_reason)
        self.assertEqual("stable", results[0].status)
        self.assertIn("未声明", results[0].freshness)

    def test_default_excludes_deprecated_and_session_summaries_until_history(self) -> None:
        self.concept("technical/current.md", title="release")
        self.concept("technical/old.md", title="release", status="deprecated")
        self.concept(
            "tasks/session-summaries/2026/08/2026-08-29-release.md",
            title="release",
        )

        self.assertEqual(["technical/current.md"], [r.path for r in self.search("release")])
        self.assertEqual(
            {
                "technical/current.md",
                "technical/old.md",
                "tasks/session-summaries/2026/08/2026-08-29-release.md",
            },
            {r.path for r in self.search("release", history=True)},
        )

    def test_explicit_deprecated_status_can_be_searched_without_all_history(self) -> None:
        self.concept("technical/old.md", title="legacy", status="deprecated")
        results = self.search("legacy", status_filter="deprecated")
        self.assertEqual(["technical/old.md"], [r.path for r in results])

    def test_limit_scope_type_status_and_unknown_type(self) -> None:
        self.concept("quality/one.md", type_="Test Oracle", title="match", status="draft")
        self.concept("quality/two.md", type_="Test Oracle", title="match", status="draft")
        self.concept("technical/three.md", type_="Test Oracle", title="match", status="draft")
        self.concept("quality/stable.md", type_="Test Oracle", title="match")

        results = self.search(
            "match",
            type_filter="Test Oracle",
            status_filter="draft",
            scope="quality",
            limit=1,
        )

        self.assertEqual(1, len(results))
        self.assertTrue(results[0].path.startswith("quality/"))

    def test_body_is_fallback_only_when_metadata_has_no_candidates(self) -> None:
        self.concept("technical/body.md", title="unrelated", body="rare needle")
        self.concept("technical/meta.md", description="needle")

        results = self.search("needle")

        self.assertEqual(["technical/meta.md"], [r.path for r in results])
        self.assertNotIn("body", results[0].matched_fields)

        self.assertEqual([], self.search("rare"))
        self.assertEqual([], self.search("rare", scope="/"))
        self.assertEqual([], self.search("rare", scope="   "))

        fallback = self.search("rare", scope="technical")
        self.assertEqual(["technical/body.md"], [r.path for r in fallback])
        self.assertEqual(("body",), fallback[0].matched_fields)

    def test_body_fallback_reads_only_an_explicit_nonempty_scope(self) -> None:
        self.concept("technical/target.md", body="rare needle")
        self.concept("business/unrelated.md", body="rare needle")

        with patch.object(MODULE, "_load_body", wraps=MODULE._load_body) as load_body:
            self.assertEqual([], self.search("rare"))
            self.assertEqual([], self.search("rare", scope="/"))
            self.assertEqual([], self.search("rare", scope="   "))
            load_body.assert_not_called()

            results = self.search("rare", scope="technical")

        self.assertEqual(["technical/target.md"], [result.path for result in results])
        self.assertEqual(1, load_body.call_count)

    def test_body_flag_includes_body_alongside_metadata_matches(self) -> None:
        self.concept("technical/body.md", body="needle")
        self.concept("technical/meta.md", title="needle")

        results = self.search("needle", include_body=True)

        self.assertEqual({"technical/body.md", "technical/meta.md"}, {r.path for r in results})
        body_result = next(r for r in results if r.path.endswith("body.md"))
        self.assertEqual(("body",), body_result.matched_fields)

    def test_multi_term_query_can_be_covered_across_metadata_fields(self) -> None:
        self.concept(
            "business/order.md",
            title="订单规则",
            tags="[幂等]",
            description="支付处理",
        )
        self.concept("business/partial.md", title="订单规则")

        results = self.search("订单 幂等")

        self.assertEqual(["business/order.md"], [result.path for result in results])
        self.assertEqual(("title", "tags"), results[0].matched_fields)

    def test_exact_case_id_outranks_repeated_substring_matches(self) -> None:
        self.concept("quality/test-cases/target.md", title="TC-ORDER-042")
        self.concept(
            "quality/test-cases/noise.md",
            title="covers TC-ORDER-042 retry",
            description="TC-ORDER-042 migration",
            tags="[TC-ORDER-042]",
        )

        results = self.search("TC-ORDER-042")

        self.assertEqual("quality/test-cases/target.md", results[0].path)
        self.assertIn("exact(2000:title)", results[0].score_reason)

    def test_body_search_can_complete_terms_found_in_metadata(self) -> None:
        self.concept("business/order.md", title="订单规则", body="必须保持幂等")

        results = self.search("订单 幂等", include_body=True)

        self.assertEqual(["business/order.md"], [result.path for result in results])
        self.assertEqual(("title", "body"), results[0].matched_fields)

    def test_reports_stale_hint(self) -> None:
        self.concept(
            "technical/stale.md",
            title="dated",
            stale_after="2026-08-01T00:00:00+00:00",
        )
        self.assertEqual("已过 stale_after", self.search("dated")[0].freshness)

    def test_cli_output_and_invalid_inputs(self) -> None:
        self.concept("technical/cache.md", title="Cache")
        output = StringIO()
        with redirect_stdout(output):
            code = MODULE.main([str(self.root), "cache"])
        self.assertEqual(0, code)
        self.assertIn("technical/cache.md", output.getvalue())
        self.assertIn("命中字段", output.getvalue())
        self.assertIn("score=", output.getvalue())

        error = StringIO()
        with redirect_stderr(error):
            code = MODULE.main([str(self.root), "cache", "--limit", "0"])
        self.assertEqual(2, code)
        self.assertIn("limit 必须大于 0", error.getvalue())

        error = StringIO()
        with redirect_stderr(error):
            code = MODULE.main([str(self.root / "missing"), "cache"])
        self.assertEqual(2, code)
        self.assertIn("不是目录", error.getvalue())

    def test_search_is_stateless_and_creates_no_cache(self) -> None:
        self.concept("technical/cache.md", title="cache")
        before = {path.relative_to(self.root) for path in self.root.rglob("*")}

        self.search("cache")

        after = {path.relative_to(self.root) for path in self.root.rglob("*")}
        self.assertEqual(before, after)

    def test_latest_session_uses_generated_at_and_cli_needs_no_query(self) -> None:
        self.concept(
            "tasks/session-summaries/2026/08/2026-08-28-old.md",
            type_="Session Summary",
            title="Old",
            generated_at="2026-08-28T10:00:00+08:00",
        )
        self.concept(
            "tasks/session-summaries/2026/08/2026-08-29-new.md",
            type_="Session Summary",
            title="New",
            generated_at="2026-08-29T09:00:00+08:00",
        )

        latest = MODULE.latest_session(self.root)

        self.assertIsNotNone(latest)
        self.assertTrue(latest.path.endswith("2026-08-29-new.md"))
        output = StringIO()
        with redirect_stdout(output):
            code = MODULE.main([str(self.root), "--latest-session"])
        self.assertEqual(0, code)
        self.assertIn("2026-08-29-new.md", output.getvalue())


if __name__ == "__main__":
    unittest.main()

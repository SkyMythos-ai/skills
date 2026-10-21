from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import context_kg_govern as govern  # noqa: E402


def concept(body: str, **metadata: object) -> str:
    return govern.render_document({"type": "Architecture Decision", "status": "stable",
                                   "title": "quota", "custom_owner": "retained", **metadata}, body)


class RebuildTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root = base / "context-kg"
        self.plan_path = base / "plan.json"
        self.state = base / "state"
        self.write("index.md", "# Knowledge\n\n- [Technical](technical/) - 技术\n")
        self.write("technical/index.md", "# Technical\n\n- [ADR](adr/) - 决策\n")
        self.write("technical/adr/index.md", "# ADR\n\n- [Current](current.md) - quota 当前方案\n- [Old](old.md) - quota 旧方案\n")
        self.write("technical/adr/current.md", concept("# quota current\n\n[附件](asset.bin)\n"))
        self.write("technical/adr/old.md", concept("# quota old\n"))
        self.write("technical/adr/asset.bin", "binary-data")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def plan(self) -> dict:
        plan = govern.create_plan(self.root, self.plan_path, rebuild=True)
        plan["rebuild"]["taxonomy"] = [
            {"directory": "technical/adr", "roles": ["decision"],
             "lifecycles": ["current", "target", "review"], "max_direct_concepts": 16},
            {"directory": "technical/adr/archive", "roles": ["decision"],
             "lifecycles": ["historical"]},
        ]
        plan["rebuild"]["decisions"] = [
            {"path": "technical/adr/current.md", "role": "decision", "lifecycle": "current",
             "disposition": "keep", "reason": "当前配置和实现仍采用"},
            {"path": "technical/adr/old.md", "role": "decision", "lifecycle": "current",
             "disposition": "keep", "reason": "待计划核验"},
        ]
        plan["rebuild"]["probes"] = [{"query": "quota", "include": ["technical/adr/current.md"]}]
        self.save(plan)
        return plan

    def save(self, plan: dict) -> None:
        self.plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def archive(self, plan: dict) -> dict:
        old = "technical/adr/old.md"
        target = "technical/adr/archive/old.md"
        plan["actions"] = [{"op": "archive", "path": old, "target": target,
                            "reason": "旧方案已由当前方案取代", "effective_period": "2025 年",
                            "replacement": "technical/adr/current.md",
                            "evidence": [{"path": old, "sha256": hashlib.sha256((self.root / old).read_bytes()).hexdigest(),
                                          "note": "决策沿革和当前配置已复核"}]}]
        plan["rebuild"]["decisions"][1].update({"lifecycle": "historical", "disposition": "archive",
                                                  "target": target, "reason": "旧方案已由当前方案取代"})
        plan["rebuild"]["probes"] = [{"query": "quota", "include": ["technical/adr/current.md"],
                                       "exclude": [target], "history_include": [target]}]
        self.save(plan)
        return plan

    def codes(self, plan: dict) -> set[str]:
        self.save(plan)
        return {item["code"] for item in govern.check_plan(self.root, self.plan_path)["blockers"]}

    def test_rebuild_requires_complete_unique_decisions_and_taxonomy(self) -> None:
        plan = self.plan()
        plan["rebuild"]["decisions"].pop()
        self.assertIn("missing-decision", self.codes(plan))
        plan = self.plan()
        plan["rebuild"]["decisions"].append(plan["rebuild"]["decisions"][0].copy())
        self.assertIn("duplicate-decision", self.codes(plan))
        plan = self.plan()
        plan["rebuild"]["decisions"][0]["role"] = "unknown"
        self.assertIn("invalid-decision", self.codes(plan))
        plan["rebuild"]["taxonomy"][0]["roles"] = ["unknown"]
        self.assertIn("invalid-taxonomy", self.codes(plan))
        plan = self.plan()
        plan["rebuild"]["taxonomy"][0]["max_direct_concepts"] = 1
        self.assertIn("directory-budget", self.codes(plan))
        plan = self.plan()
        plan["rebuild"]["taxonomy"] = []
        self.assertIn("missing-taxonomy", self.codes(plan))

    def test_deprecated_active_and_stable_archive_name_do_not_pass(self) -> None:
        self.write("technical/adr/old.md", concept("# quota old\n", status="deprecated"))
        plan = self.plan()
        self.assertIn("deprecated-active", self.codes(plan))
        self.assertIn("active-index-history", self.codes(plan))
        self.write("technical/adr/old.md", concept("# quota old\n", tags=["archive"]))
        plan = self.plan()
        self.assertEqual("needs-review", govern.check_plan(self.root, self.plan_path)["acceptance"]["completion"])
        self.write("technical/adr/old.md", concept("# quota old\n"))
        self.write("technical/adr/archive-old.md", concept("# quota archive old\n"))
        self.write("technical/adr/index.md", "# ADR\n\n- [Current](current.md) - quota\n- [Old](old.md) - quota\n- [Archive named](archive-old.md) - quota\n")
        plan = self.plan()
        plan["rebuild"]["decisions"].append({"path": "technical/adr/archive-old.md", "role": "decision",
                                                 "lifecycle": "historical", "disposition": "keep",
                                                 "reason": "名称暗示旧版，需要隔离"})
        self.assertIn("history-path", self.codes(plan))

    def test_archive_apply_verify_probes_and_preserves_asset_metadata(self) -> None:
        plan = self.archive(self.plan())
        report = govern.check_plan(self.root, self.plan_path)
        self.assertEqual("ready", report["status"], report)
        self.assertEqual("complete", report["acceptance"]["completion"])
        result = govern.apply_plan(self.root, self.plan_path, self.state)
        self.assertEqual("applied", result["status"])
        verified = govern.verify_plan(self.root, self.plan_path)
        self.assertEqual("complete", verified["completion"], verified)
        self.assertEqual(1, verified["archived"])
        self.assertEqual(1, verified["historical_count"])
        self.assertEqual("binary-data", (self.root / "technical/adr/asset.bin").read_text())
        self.assertIn("custom_owner: retained", (self.root / "technical/adr/archive/old.md").read_text())
        self.write("technical/adr/asset.bin", "mutated")
        self.assertIn("asset-changed", {item["code"] for item in govern.verify_plan(self.root, self.plan_path)["blockers"]})
        self.write("technical/adr/asset.bin", "binary-data")
        self.write("technical/adr/rogue.md", concept("# quota rogue\n"))
        self.assertIn("uncovered-final", {item["code"] for item in govern.verify_plan(self.root, self.plan_path)["blockers"]})

    def test_probe_must_hit_real_current_and_history(self) -> None:
        plan = self.archive(self.plan())
        plan["rebuild"]["probes"][0]["history_include"] = ["technical/adr/archive/missing.md"]
        self.assertIn("probe-path-missing", self.codes(plan))
        plan = self.archive(self.plan())
        plan["rebuild"]["probes"][0]["query"] = "nothing matches this"
        codes = self.codes(plan)
        self.assertIn("probe-include-missing", codes)
        self.assertIn("probe-history-missing", codes)
        plan = self.archive(self.plan())
        plan["rebuild"]["probes"][0]["exclude"] = []
        self.assertIn("missing-history-probe", self.codes(plan))

    def test_complete_keep_and_review(self) -> None:
        plan = self.plan()
        self.assertEqual("ready", govern.check_plan(self.root, self.plan_path)["status"])
        self.assertEqual("complete", govern.verify_plan(self.root, self.plan_path)["completion"])
        plan["rebuild"]["decisions"][1]["lifecycle"] = "review"
        plan["rebuild"]["decisions"][1]["disposition"] = "review"
        self.save(plan)
        self.assertEqual("needs-review", govern.check_plan(self.root, self.plan_path)["acceptance"]["completion"])
        self.assertEqual("needs-review", govern.verify_plan(self.root, self.plan_path)["completion"])

    def test_decision_target_must_match_action(self) -> None:
        plan = self.archive(self.plan())
        plan["rebuild"]["decisions"][1]["target"] = "technical/adr/archive/other.md"
        self.assertIn("target-mismatch", self.codes(plan))

    def test_quality_type_synonyms_are_only_inventory_suggestions(self) -> None:
        from context_kg_inventory import _role
        self.assertEqual("verification", _role("quality/misc/report.md", {"type": "Test Report"})[0])
        role, suggested, _ = _role("quality/misc/strategy.md", {"type": "Test Strategy"})
        self.assertEqual(("strategies", "quality/strategies"), (role, suggested))
        self.assertEqual("unknown", _role("quality/misc/custom.md", {"type": "Custom Evidence"})[0])

    def test_existing_broken_link_blocks_rebuild_and_verify_detects_new_breakage(self) -> None:
        self.write("technical/adr/current.md", concept("# quota current\n\n[broken](absent.md)\n"))
        plan = self.plan()
        self.assertIn("broken_markdown_link", self.codes(plan))
        self.write("technical/adr/current.md", concept("# quota current\n"))
        plan = self.archive(self.plan())
        govern.apply_plan(self.root, self.plan_path, self.state)
        self.write("technical/adr/current.md", concept("# quota current\n\n[broken](absent.md)\n"))
        self.assertIn("broken_markdown_link", {item["code"] for item in govern.verify_plan(self.root, self.plan_path)["blockers"]})

    def test_verify_detects_successor_cycle(self) -> None:
        plan = self.archive(self.plan())
        govern.apply_plan(self.root, self.plan_path, self.state)
        current = self.root / "technical/adr/current.md"
        metadata, body = govern.parse_document(current.read_text())
        metadata["superseded_by"] = "technical/adr/archive/old.md"
        current.write_text(govern.render_document(metadata, body), encoding="utf-8")
        self.assertIn("superseded_cycle", {item["code"] for item in govern.verify_plan(self.root, self.plan_path)["blockers"]})

    def test_relative_successor_from_archive_is_valid(self) -> None:
        plan = self.archive(self.plan())
        govern.apply_plan(self.root, self.plan_path, self.state)
        archived = self.root / "technical/adr/archive/old.md"
        metadata, body = govern.parse_document(archived.read_text())
        metadata["superseded_by"] = "../current.md"
        archived.write_text(govern.render_document(metadata, body), encoding="utf-8")
        self.assertEqual("complete", govern.verify_plan(self.root, self.plan_path)["completion"])

    def test_archive_and_successor_move_rewrite_live_replacement_only(self) -> None:
        plan = self.archive(self.plan())
        successor = "technical/adr/current.md"
        moved = "technical/adr/new/current.md"
        plan["actions"].append({"op": "move", "path": successor, "target": moved,
                                "reason": "当前方案归入新主题"})
        plan["rebuild"]["decisions"][0].update({"disposition": "move", "target": moved})
        plan["rebuild"]["probes"][0]["include"] = [moved]
        self.save(plan)
        preview = govern.check_plan(self.root, self.plan_path)
        self.assertEqual("ready", preview["status"], preview)
        govern.apply_plan(self.root, self.plan_path, self.state)
        archived = self.root / "technical/adr/archive/old.md"
        metadata, _ = govern.parse_document(archived.read_text())
        self.assertEqual(moved, metadata["superseded_by"])
        self.assertEqual(moved, metadata["lifecycle"]["archive"]["replacement"])
        self.assertEqual("technical/adr/old.md", metadata["lifecycle"]["archive"]["original_path"])
        self.assertEqual("technical/adr/old.md", metadata["lifecycle"]["archive"]["evidence"][0]["path"])
        self.assertEqual("complete", govern.verify_plan(self.root, self.plan_path)["completion"])
        metadata["lifecycle"]["archive"]["replacement"] = "technical/adr/ghost.md"
        archived.write_text(govern.render_document(metadata, "# quota old\n"), encoding="utf-8")
        self.assertIn("missing_archive_replacement", {item["code"] for item in
                      govern.verify_plan(self.root, self.plan_path)["blockers"]})

    def test_code_example_link_is_not_navigation_and_archive_casefold(self) -> None:
        self.write("technical/adr/Archive/old2.md", concept("# quota legacy\n", status="deprecated"))
        self.write("technical/adr/index.md", "# ADR\n\n- [Current](current.md) - quota\n- [Old](old.md) - quota\n- [History](Archive/) - 历史\n\n```md\n[Historical](Archive/old2.md)\n```\n\n`[Historical](Archive/old2.md)`\n")
        plan = self.plan()
        plan["rebuild"]["taxonomy"].append({"directory": "technical/adr/Archive", "roles": ["decision"],
                                               "lifecycles": ["historical"]})
        plan["rebuild"]["decisions"].append({"path": "technical/adr/Archive/old2.md", "role": "decision",
                                               "lifecycle": "historical", "disposition": "keep",
                                               "reason": "保留旧决策以供审计"})
        plan["rebuild"]["probes"][0].update({"exclude": ["technical/adr/Archive/old2.md"],
                                               "history_include": ["technical/adr/Archive/old2.md"]})
        self.save(plan)
        self.assertEqual("complete", govern.check_plan(self.root, self.plan_path)["acceptance"]["completion"])

    def test_root_concept_can_use_root_taxonomy(self) -> None:
        self.write("overview.md", concept("# quota overview\n"))
        self.write("index.md", "# Knowledge\n\n- [Technical](technical/) - 技术\n- [Overview](overview.md) - 概览\n")
        plan = self.plan()
        plan["rebuild"]["taxonomy"].append({"directory": ".", "roles": ["overview"],
                                               "lifecycles": ["current"]})
        plan["rebuild"]["decisions"].append({"path": "overview.md", "role": "overview",
                                               "lifecycle": "current", "disposition": "keep",
                                               "reason": "根导航的权威概览"})
        self.save(plan)
        self.assertEqual("complete", govern.check_plan(self.root, self.plan_path)["acceptance"]["completion"])

    def test_rebuild_requires_direct_navigation_without_making_singleton_index_mandatory(self) -> None:
        self.write("technical/adr/index.md", "# ADR\n\n- [Current](current.md) - quota\n\n```md\n- [Old](old.md) - sample\n```\n")
        plan = self.plan()
        self.assertIn("unlisted-direct-concept", self.codes(plan))
        (self.root / "technical/adr/index.md").unlink()
        plan = self.plan()
        self.assertIn("missing-required-index", self.codes(plan))
        from context_kg_rebuild import _navigation_coverage
        singleton = {"index.md": b"# Knowledge\n\n- [Single](single/) - one\n",
                     "single/one.md": concept("# quota one\n").encode()}
        self.assertEqual([], _navigation_coverage(self.root, singleton))

    def test_existing_directory_link_prevents_duplicate_generated_entry(self) -> None:
        tree = {"index.md": b"# Knowledge\n\n- [Technical](technical/) - original description\n"}
        govern._index_add(tree, ".", "technical/index.md", "Technical", "目录索引")
        self.assertEqual(1, tree["index.md"].decode().count("[Technical]"))
        self.assertIn("original description", tree["index.md"].decode())


if __name__ == "__main__":
    unittest.main()

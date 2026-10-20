from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import context_kg_govern as govern  # noqa: E402


def concept(body: str, **fields: str) -> str:
    metadata = {"type": "Architecture Decision", "status": "stable", "sources": [], **fields}
    return govern.render_document(metadata, body)


class GovernanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "context-kg"
        self.state = base / "state"
        self.plan_file = base / "plan.json"
        self.write("index.md", "# Knowledge\n\n- [Technical](technical/index.md) - 技术知识\n")
        self.write("technical/index.md", "# Technical\n\n- [A](a/index.md) - A 类\n- [B](b/index.md) - B 类\n")
        self.write("technical/a/index.md", "# A\n\n- [X](x.md) - 主文档\n- [Other](other.md) - 保留文档\n")
        self.write("technical/b/index.md", "# B\n\n- [Keep](keep.md) - 保留文档\n")
        self.write("technical/a/x.md", concept("# X\n\n[资源](asset.txt)\n"))
        self.write("technical/a/other.md", concept("# Other\n"))
        self.write("technical/b/keep.md", concept("# Keep\n"))
        self.write("technical/a/asset.txt", "asset\n")
        self.write("technical/reader.md", concept("# Reader\n\n[原文](a/x.md)\n"))
        self.write("log.md", "# Log\n\n## 2026-10-19\n- Existing\n")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def plan(self, actions: list[dict]) -> None:
        govern.create_plan(self.root, self.plan_file)
        plan = json.loads(self.plan_file.read_text())
        plan["actions"] = actions
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")

    def evidence(self, rel: str = "technical/a/x.md") -> list[dict]:
        return [{"path": rel, "sha256": hashlib.sha256((self.root / rel).read_bytes()).hexdigest(),
                 "note": "人工复核当前文档与消费者"}]

    def move(self) -> dict:
        return {"op": "move", "path": "technical/a/x.md", "target": "technical/b/x.md",
                "reason": "归入 B 类"}

    def test_move_rebases_own_and_incoming_links_and_preserves_unknown_metadata(self) -> None:
        self.write("technical/a/x.md", concept("# X\n\n[资源](asset.txt)\n", owner_extra="retained"))
        os.chmod(self.root / "technical/a/x.md", 0o640)
        self.plan([self.move()])
        report = govern.check_plan(self.root, self.plan_file)
        self.assertEqual("ready", report["status"], report)
        self.assertIn("technical/reader.md", report["changed"])
        self.assertIn("--- a/technical/reader.md", report["diff"])
        govern.apply_plan(self.root, self.plan_file, self.state)
        moved = (self.root / "technical/b/x.md").read_text()
        self.assertIn("[资源](../a/asset.txt)", moved)
        self.assertIn("owner_extra: retained", moved)
        self.assertEqual(0o640, stat.S_IMODE((self.root / "technical/b/x.md").stat().st_mode))
        self.assertIn("[原文](b/x.md)", (self.root / "technical/reader.md").read_text())
        self.assertNotIn("[X](x.md)", (self.root / "technical/a/index.md").read_text())
        self.assertIn("[X](x.md)", (self.root / "technical/b/index.md").read_text())
        self.assertIn("## 2026-10-19", (self.root / "log.md").read_text())
        govern.recover(self.root, self.state)
        self.assertEqual(0o640, stat.S_IMODE((self.root / "technical/a/x.md").stat().st_mode))

    def test_move_preserves_identity_of_existing_broken_link(self) -> None:
        self.write("technical/a/x.md", concept("# X\n\n[旧坏链](missing.md)\n"))
        self.plan([self.move()])
        report = govern.check_plan(self.root, self.plan_file)
        self.assertEqual("ready", report["status"], report)
        govern.apply_plan(self.root, self.plan_file, self.state)
        self.assertIn("[旧坏链](../a/missing.md)", (self.root / "technical/b/x.md").read_text())

    def test_archive_restore_provenance_and_status(self) -> None:
        archive = {"op": "archive", "path": "technical/a/x.md", "reason": "已被新决策替代",
                   "effective_period": "2025-01 至 2026-09", "replacement": "technical/b/keep.md",
                   "evidence": self.evidence()}
        self.plan([archive])
        preview = govern.check_plan(self.root, self.plan_file)
        self.assertEqual("ready", preview["status"])
        self.assertEqual(preview["diff"], govern.check_plan(self.root, self.plan_file)["diff"])
        _, _, expected = govern._check_plan_details(self.root, self.plan_file)
        govern.apply_plan(self.root, self.plan_file, self.state)
        self.assertEqual(expected, {rel: (self.root / rel).read_bytes() for rel in expected})
        archived_path = "technical/a/archive/x.md"
        archived = (self.root / archived_path).read_text()
        fields, body = govern.parse_document(archived)
        self.assertEqual("deprecated", fields["status"])
        self.assertEqual("technical/a/x.md", fields["lifecycle"]["archive"]["original_path"])
        self.assertTrue(fields["lifecycle"]["archive"]["evidence"])
        self.assertIn("<!-- context-kg-govern:archive -->", body)
        self.assertIn("[原文](a/archive/x.md)", (self.root / "technical/reader.md").read_text())
        restore = {"op": "restore", "path": archived_path, "target": "technical/a/x.md",
                   "reason": "复核后重新生效", "status": "draft",
                   "evidence": self.evidence(archived_path)}
        self.plan([restore])
        self.assertEqual("ready", govern.check_plan(self.root, self.plan_file)["status"])
        govern.apply_plan(self.root, self.plan_file, self.state)
        restored = (self.root / "technical/a/x.md").read_text()
        fields, body = govern.parse_document(restored)
        self.assertEqual("draft", fields["status"])
        self.assertTrue(fields["lifecycle"]["restore"]["evidence"])
        self.assertNotIn("superseded_by", fields)
        self.assertNotIn("context-kg-govern:archive", body)
        self.assertFalse((self.root / "technical/a/archive/index.md").exists())

    def test_due_does_not_archive_and_empty_plan_is_noop(self) -> None:
        self.write("technical/a/x.md", concept("# X\n", stale_after="2020-01-01T00:00:00Z"))
        self.plan([])
        self.assertEqual("no-op", govern.check_plan(self.root, self.plan_file)["status"])
        self.assertTrue((self.root / "technical/a/x.md").exists())

    def test_archive_removes_direct_active_index_links(self) -> None:
        self.write("index.md", "# Knowledge\n\n- [Old](technical/a/x.md) - 当前决策\n- [Technical](technical/index.md) - 技术知识\n")
        self.write("technical/b/index.md", "# B\n\n- [Old](../a/x.md) - 跨分支入口\n- [Keep](keep.md) - 保留文档\n")
        action = {"op": "archive", "path": "technical/a/x.md", "reason": "退出当前决策",
                  "effective_period": "2025", "evidence": self.evidence()}
        self.plan([action])
        self.assertEqual("ready", govern.check_plan(self.root, self.plan_file)["status"])
        govern.apply_plan(self.root, self.plan_file, self.state)
        self.assertNotIn("archive/x.md", (self.root / "index.md").read_text())
        self.assertNotIn("archive/x.md", (self.root / "technical/b/index.md").read_text())
        self.assertIn("[X](x.md)", (self.root / "technical/a/archive/index.md").read_text())

    def test_uppercase_markdown_concept_moves_and_rewrites(self) -> None:
        (self.root / "technical/a/x.md").unlink()
        self.write("technical/a/X.MD", concept("# Upper\n\n[资产](asset.txt)\n"))
        self.write("technical/a/index.md", "# A\n\n- [Upper](X.MD) - 主文档\n- [Other](other.md) - 保留文档\n")
        self.write("technical/reader.md", concept("# Reader\n\n[Upper](a/X.MD)\n"))
        self.plan([{"op": "move", "path": "technical/a/X.MD", "target": "technical/b/X.MD",
                    "reason": "归入 B 类"}])
        self.assertEqual("ready", govern.check_plan(self.root, self.plan_file)["status"])
        govern.apply_plan(self.root, self.plan_file, self.state)
        self.assertIn("[资产](../a/asset.txt)", (self.root / "technical/b/X.MD").read_text())
        self.assertIn("[Upper](b/X.MD)", (self.root / "technical/reader.md").read_text())

    def test_snapshot_new_file_and_stale_hash_rejected(self) -> None:
        self.plan([self.move()])
        self.write("technical/new.md", concept("# New\n"))
        with self.assertRaisesRegex(govern.GovernanceError, "文件集合"):
            govern.check_plan(self.root, self.plan_file)
        (self.root / "technical/new.md").unlink()
        self.write("technical/a/x.md", concept("# Changed\n"))
        with self.assertRaisesRegex(govern.GovernanceError, "内容已变化"):
            govern.check_plan(self.root, self.plan_file)

    def test_path_escape_and_case_collision(self) -> None:
        bad = self.move()
        bad["target"] = "../escape.md"
        self.plan([bad])
        with self.assertRaisesRegex(govern.GovernanceError, "逃逸"):
            govern.check_plan(self.root, self.plan_file)
        bad["target"] = "technical/b/KEEP.md"
        self.plan([bad])
        with self.assertRaisesRegex(govern.GovernanceError, "大小写"):
            govern.check_plan(self.root, self.plan_file)

    def test_file_directory_collision_and_reserved_delete(self) -> None:
        self.write("technical/b/archive", "occupied\n")
        action = {"op": "archive", "path": "technical/a/x.md",
                  "target": "technical/b/archive/x.md", "reason": "历史归档",
                  "effective_period": "2025", "evidence": self.evidence()}
        self.plan([action])
        with self.assertRaisesRegex(govern.GovernanceError, "文件/目录路径冲突"):
            govern.check_plan(self.root, self.plan_file)
        self.plan([{"op": "delete", "path": "index.md", "reason": "错误操作",
                    "evidence": self.evidence(),
                    "preservation": {"target": None, "note": "错误操作"}}])
        with self.assertRaisesRegex(govern.GovernanceError, "index/log"):
            govern.check_plan(self.root, self.plan_file)

    def test_delete_live_reference_rejected_but_preexisting_bad_link_tolerated(self) -> None:
        action = {"op": "delete", "path": "technical/a/x.md", "reason": "内容已移交",
                  "evidence": self.evidence(),
                  "preservation": {"target": "technical/b/keep.md", "note": "独有内容已迁入目标"}}
        self.plan([action])
        self.assertEqual("blocked", govern.check_plan(self.root, self.plan_file)["status"])
        self.write("technical/reader.md", concept("# Reader\n\n[已有坏链](missing.md)\n"))
        self.plan([action])
        report = govern.check_plan(self.root, self.plan_file)
        self.assertEqual("ready", report["status"], report)

    def test_new_broken_link_is_blocker(self) -> None:
        action = {"op": "update", "path": "technical/a/x.md", "reason": "更新正文",
                  "evidence": self.evidence(), "body": "# X\n\n[新坏链](missing.md)\n"}
        self.plan([action])
        self.assertEqual("blocked", govern.check_plan(self.root, self.plan_file)["status"])

    def test_ignored_boundary_and_evidence_hash(self) -> None:
        repo = self.root.parent
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / ".gitignore").write_text("context-kg/technical/b/\n", encoding="utf-8")
        self.plan([self.move()])
        with self.assertRaisesRegex(govern.GovernanceError, "ignored"):
            govern.check_plan(self.root, self.plan_file)
        action = {"op": "update", "path": "technical/a/x.md", "reason": "更新", "evidence": self.evidence()}
        action["evidence"][0]["sha256"] = "0" * 64
        self.plan([action])
        with self.assertRaisesRegex(govern.GovernanceError, "证据已变化"):
            govern.check_plan(self.root, self.plan_file)

    def test_io_error_rolls_back_and_recover_detects_parallel_change(self) -> None:
        self.plan([self.move()])
        original = {rel: (self.root / rel).read_bytes() for rel in govern.scan_bundle(self.root)["files"]}
        actual = govern._write_change
        count = 0

        def broken(root: Path, rel: str, data: bytes | None, mode: int | None = None) -> None:
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("injected")
            actual(root, rel, data, mode)

        with patch.object(govern, "_write_change", side_effect=broken):
            with self.assertRaisesRegex(OSError, "injected"):
                govern.apply_plan(self.root, self.plan_file, self.state)
        self.assertEqual(original, {rel: (self.root / rel).read_bytes() for rel in original})
        self.assertEqual("recovered", govern.recover(self.root, self.state)["status"])

        govern.apply_plan(self.root, self.plan_file, self.state)
        self.write("technical/b/x.md", "parallel change\n")
        with self.assertRaisesRegex(govern.GovernanceError, "恢复冲突"):
            govern.recover(self.root, self.state)

    def test_interrupted_transaction_recovers_and_repeated_recover_is_safe(self) -> None:
        self.plan([self.move()])
        _, before, after = govern._check_plan_details(self.root, self.plan_file)
        paths = sorted(rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel))
        state = govern._state(self.root, self.state)
        journal = {"version": 1, "root": str(self.root.resolve()), "state": "applying",
                   "entries": [{"path": rel, "before": govern._encoded(before.get(rel)),
                                "after": govern._encoded(after.get(rel)),
                                "before_mode": govern._current_mode(self.root, rel),
                                "after_mode": (govern._current_mode(self.root, rel) if rel in before else 0o644)
                                if rel in after else None} for rel in paths]}
        govern._save_journal(state, journal)
        govern._write_change(self.root, paths[0], after.get(paths[0]))
        (state / "lock").write_text("999999999\n")
        self.assertEqual("recovered", govern.recover(self.root, self.state)["status"])
        self.assertEqual("recovered", govern.recover(self.root, self.state)["status"])
        self.assertEqual(before, {rel: (self.root / rel).read_bytes() for rel in before})

    def test_snapshot_second_read_detects_race(self) -> None:
        self.plan([self.move()])
        real_read = govern._read_tree

        def raced(root: Path, inventory: dict) -> dict[str, bytes]:
            self.write("technical/a/x.md", concept("# Concurrent edit\n"))
            return real_read(root, inventory)

        with patch.object(govern, "_read_tree", side_effect=raced):
            with self.assertRaisesRegex(govern.GovernanceError, "扫描后文件被并行修改"):
                govern.check_plan(self.root, self.plan_file)

    def test_external_ref_blocks_move(self) -> None:
        repo = self.root.parent
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "consumer.py").write_text("DOC = 'context-kg/technical/a/x.md'\n", encoding="utf-8")
        self.plan([self.move()])
        report = govern.check_plan(self.root, self.plan_file)
        self.assertIn("external-ref", {item["code"] for item in report["blockers"]})

    def test_external_ref_without_git_blocks_move(self) -> None:
        (self.root.parent / "AGENTS.md").write_text("Read context-kg/technical/a/x.md\n", encoding="utf-8")
        self.plan([self.move()])
        report = govern.check_plan(self.root, self.plan_file)
        self.assertIn("external-ref", {item["code"] for item in report["blockers"]})


if __name__ == "__main__":
    unittest.main()

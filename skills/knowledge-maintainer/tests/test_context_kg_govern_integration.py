"""从实际 CLI 验证盘点、历史治理与检索之间的合同。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPTS = Path(__file__).parents[1] / "scripts"


class GovernanceCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="kg-govern-integration-")
        self.directory = Path(self.temporary.name).resolve()
        self.project = self.directory / "project"
        self.root = self.project / "context-kg"
        self.root.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / ".gitignore").write_text("context-kg/tasks/\n", encoding="utf-8")
        self.write("index.md", '# Root\n\n- [业务](business/) - 业务规则。\n')
        self.write("business/index.md", "# 业务\n\n- [支付规则](payment.md) - 原规则。\n- [新规则](current.md) - 当前规则。\n")
        self.write("business/payment.md", "---\ntype: Business Rule\ntitle: 历史支付规则\nstatus: stable\ncustom: {owner: billing, unknown: [1, 2]}\n---\n\n原有取舍必须保留。\n\n[新规则](current.md#effective)\n")
        self.write("business/current.md", "---\ntype: Business Rule\ntitle: 当前规则\n---\n\n# 当前规则\n\n迁移已完成。\n")
        self.write("quality/evidence.md", "---\ntype: Verification Report\nsources:\n  - resource: ../business/payment.md\n---\n\n[原决策](../business/payment.md#reason)\n\n[参考][old]\n\n[old]: ../business/payment.md\n")
        self.write("tasks/private.md", "---\ntype: Task Plan\n---\n\nPRIVATE_BODY_ONLY\n")
        self.write("custom/assets/data.tsv", "key\tvalue\n1\t2\n")
        self.plan = self.directory / "plan.json"
        self.state = self.directory / "state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def command(self, name: str, *args: str, expected: int = 0) -> dict:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "context_kg_govern.py"), name,
             str(self.root), *args], capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def action(self, value: dict) -> None:
        self.command("plan", "--output", str(self.plan))
        plan = json.loads(self.plan.read_text(encoding="utf-8"))
        plan["actions"] = [value]
        self.plan.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def evidence(self) -> list[dict]:
        path = self.root / "business/current.md"
        return [{"path": "business/current.md", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                 "note": "新规则记录的迁移完成证据；本 fixture 代表宿主已完成语义复核。"}]

    def search(self, query: str, *, history: bool = False) -> str:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "context_kg_search.py"), str(self.root), query,
             *( ["--history"] if history else [])], capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout

    def test_audit_is_bounded_and_includes_ignored_custom_assets_without_bodies(self) -> None:
        output = self.directory / "audit.json"
        summary = self.command("audit", "--limit", "1", "--output", str(output))
        self.assertLessEqual(len(summary["diagnostics"]), 1)
        full = output.read_text(encoding="utf-8")
        audit = json.loads(full)
        self.assertEqual("ignored", audit["files"]["tasks/private.md"]["git_status"])
        self.assertEqual("asset", audit["files"]["custom/assets/data.tsv"]["kind"])
        self.assertNotIn("PRIVATE_BODY_ONLY", full)
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        plan_summary = self.command("plan", "--output", str(self.plan))
        self.assertNotIn("snapshot", plan_summary, "完整 hash 快照只写文件，避免全量输出进入模型上下文")
        self.assertEqual(len(audit["files"]), plan_summary["files"])
        report = self.command("check", "--plan", str(self.plan))
        self.assertEqual("no-op", report["status"])
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_archive_restore_and_recover_preserve_navigation_evidence_and_retrieval(self) -> None:
        private = (self.root / "tasks/private.md").read_bytes()
        self.action({"op": "archive", "path": "business/payment.md", "reason": "新规则已经生效，保留历史取舍。",
                     "effective_period": "2025-01 至 2026-10 迁移完成", "replacement": "business/current.md",
                     "evidence": self.evidence()})
        report = self.command("check", "--plan", str(self.plan))
        self.assertEqual("ready", report["status"], report)
        self.assertIn("business/archive/payment.md", report["diff"])
        self.assertTrue((self.root / "business/payment.md").exists(), "check 必须只读")
        self.command("apply", "--plan", str(self.plan), "--state-dir", str(self.state))
        archived = self.root / "business/archive/payment.md"
        content = archived.read_text(encoding="utf-8")
        self.assertIn("原有取舍必须保留", content)
        self.assertIn("../current.md#effective", content)
        metadata = yaml.safe_load(content.split("---", 2)[1])
        self.assertEqual("deprecated", metadata["status"])
        self.assertEqual({"owner": "billing", "unknown": [1, 2]}, metadata["custom"])
        self.assertIn("archive/payment.md#reason", (self.root / "quality/evidence.md").read_text())
        parent_index = (self.root / "business/index.md").read_text()
        self.assertNotIn("archive/payment.md", parent_index)
        self.assertIn("archive", parent_index)
        self.assertIn("payment.md", (archived.parent / "index.md").read_text())
        self.assertNotIn("archive/payment.md", self.search("历史支付规则"))
        self.assertIn("business/archive/payment.md", self.search("历史支付规则", history=True))

        # 新事务必须可以在已完成归档后执行，不能要求先撤销上一次治理。
        self.action({"op": "restore", "path": "business/archive/payment.md", "target": "business/payment.md",
                     "status": "draft", "reason": "重新提出旧规则，尚未生效。", "evidence": self.evidence()})
        self.command("check", "--plan", str(self.plan))
        self.command("apply", "--plan", str(self.plan), "--state-dir", str(self.state))
        self.assertIn("business/payment.md", self.search("历史支付规则"))
        self.assertNotIn("superseded_by:", (self.root / "business/payment.md").read_text())
        self.command("recover", "--state-dir", str(self.state))
        self.assertTrue(archived.exists(), "recover 只撤销最近一次恢复事务")
        self.assertFalse((self.root / "business/payment.md").exists())
        self.assertEqual(private, (self.root / "tasks/private.md").read_bytes())

    def test_external_reference_blocks_until_callers_and_snapshot_are_updated(self) -> None:
        caller = self.project / "AGENTS.md"
        caller.write_text("业务规则见 context-kg/business/payment.md。\n", encoding="utf-8")
        self.action({"op": "move", "path": "business/payment.md", "target": "business/rules/payment.md",
                     "reason": "按业务规则角色组织。"})
        report = self.command("check", "--plan", str(self.plan), expected=2)
        self.assertTrue(any(item["code"] == "external-ref" for item in report["blockers"]))
        self.assertTrue((self.root / "business/payment.md").exists())
        caller.write_text("业务规则见 context-kg/business/rules/payment.md。\n", encoding="utf-8")
        # 按消费方修改后的状态重新生成计划，避免复用失去审阅依据的快照。
        self.action({"op": "move", "path": "business/payment.md", "target": "business/rules/payment.md",
                     "reason": "按业务规则角色组织。"})
        self.command("check", "--plan", str(self.plan))


if __name__ == "__main__":
    unittest.main()

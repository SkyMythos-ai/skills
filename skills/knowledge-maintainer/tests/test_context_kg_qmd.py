"""通过 CLI 验证真实 QMD 边界；不以替身的检索算法证明中文召回。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "context_kg_qmd.py"
QMD = os.environ.get("CONTEXT_KG_QMD_EXECUTABLE") or shutil.which("qmd")
SPEC = importlib.util.spec_from_file_location("context_kg_qmd", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CommandHelpTest(unittest.TestCase):
    def test_help_does_not_need_qmd_or_create_cache(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        for command in ("sync", "search", "read", "watch", "status"):
            self.assertIn(command, result.stdout)


class LocalContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="knowledge-qmd-contract-")
        self.directory = Path(self.temporary.name).resolve()
        self.root = self.directory / "context-kg"
        self.root.mkdir()
        (self.root / "index.md").write_text("# root\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_paged_read_reassembles_escaped_lines_and_long_single_line(self) -> None:
        for content in ('"' * 90 + '\n') * 6 + 'END\n', ('中文\\\"' * 1400) + '\nEND\n':
            target = self.root / "escape.md"
            target.write_text(content, encoding="utf-8")
            line, column = 1, 0
            pages = []
            for _ in range(100):
                page = MODULE.read_source(self.root, "escape.md", start_line=line,
                                          start_column=column, lines=120, max_chars=1000)
                self.assertLessEqual(len(MODULE._json(page)), 1000)
                pages.append(page["content"])
                if not page["has_more"]:
                    break
                cursor = page["next_line"], page["next_column"]
                self.assertNotEqual((line, column), cursor)
                line, column = cursor
            else:
                self.fail("有界分页不能推进")
            self.assertEqual(content, "".join(pages))

    def test_qmd_eligibility_shares_archive_and_history_rules(self) -> None:
        eligible = MODULE.LocalIndex._eligible
        common = {"scope": None, "type_filter": None, "status_filter": None}
        self.assertFalse(eligible("business/archive/rule.md", {"status": "stable"},
                                  **common, history=False))
        self.assertFalse(eligible("quality/ARCHIVE/old.md", {"status": "deprecated"},
                                  **{**common, "status_filter": "deprecated"}, history=False))
        self.assertFalse(eligible("custom/archive/unknown.md", {"status": "mystery"},
                                  **common, history=False))
        self.assertTrue(eligible("technical/archive-storage.md", {"status": "stable"},
                                 **common, history=False))
        self.assertTrue(eligible("technical/archived-name.md", {"status": "stable"},
                                 **common, history=False))
        self.assertTrue(eligible("business/archive/rule.md", {"status": "stable"},
                                **common, history=True))
        self.assertTrue(eligible("tasks/session-summaries/summary.md",
                                 {"type": "Session Summary"}, **common, history=True))

    def test_scan_error_preserves_manifest_and_source_projection(self) -> None:
        branch = self.root / "technical"
        branch.mkdir()
        (branch / "rule.md").write_text("---\ntype: Rule\n---\n退款\n", encoding="utf-8")
        index = MODULE.LocalIndex(self.root, self.directory / "cache", "not-called")
        with index.lock(), patch.object(index, "check_version"), patch.object(index, "run_qmd", return_value=""):
            index.sync()
            before = index.manifest_path.read_bytes()
            scan = os.scandir

            def unreadable(path):
                if Path(path) == branch:
                    raise PermissionError("injected unreadable subtree")
                return scan(path)

            with patch.object(MODULE.os, "scandir", side_effect=unreadable):
                with self.assertRaises(MODULE.RetrievalError):
                    index.sync()
            self.assertEqual(before, index.manifest_path.read_bytes())
            self.assertEqual(1, len(list(index.documents.glob("*.md"))))

    def test_cache_lock_timeout_and_unsafe_cache_rejection(self) -> None:
        index = MODULE.LocalIndex(self.root, self.directory / "cache", "not-called")
        with index.lock():
            other = MODULE.LocalIndex(self.root, index.cache, "not-called")
            with self.assertRaises(MODULE.RetrievalError):
                with other.lock(timeout=0.1):
                    self.fail("持锁时另一个写者不能进入")
        unsafe = self.directory / "unrelated"
        unsafe.mkdir()
        (unsafe / "keep.txt").write_text("keep", encoding="utf-8")
        permissions = unsafe.stat().st_mode
        with self.assertRaises(MODULE.RetrievalError):
            MODULE.LocalIndex(self.root, unsafe, "not-called").prepare()
        self.assertEqual(["keep.txt"], [p.name for p in unsafe.iterdir()])
        self.assertEqual(permissions, unsafe.stat().st_mode)
        with self.assertRaises(MODULE.RetrievalError):
            MODULE._cache_for(self.root, self.directory)
        checkout = self.directory / "another-checkout"
        (checkout / ".git").mkdir(parents=True)
        with self.assertRaises(MODULE.RetrievalError):
            MODULE._cache_for(self.root, checkout / "cache")

    def test_model_commands_and_host_credentials_are_not_inherited(self) -> None:
        index = MODULE.LocalIndex(self.root, self.directory / "cache", "not-called")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only", "NODE_OPTIONS": "test-only",
                                     "QMD_EMBED_MODEL": "test-only", "QMD_DB_PATH": "test-only"}):
            env = index._environment()
        for key in ("OPENAI_API_KEY", "NODE_OPTIONS", "QMD_EMBED_MODEL", "QMD_DB_PATH"):
            self.assertNotIn(key, env)
        self.assertTrue(Path(env["HOME"]).is_relative_to(index.cache))
        for command in ("query", "vsearch", "embed", "pull"):
            with self.assertRaises(MODULE.RetrievalError):
                index.run_qmd(command)


@unittest.skipUnless(QMD, "设置 CONTEXT_KG_QMD_EXECUTABLE 以运行真实 QMD 2.8.3 集成检查")
class QmdIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="knowledge-qmd-test-")
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "context-kg"
        self.cache = self.directory / "cache"
        self.root.mkdir()
        (self.root / "index.md").write_text("# 测试知识库\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def concept(self, path: str, *, title: str = "支付规则", body: str = "退款保持幂等",
                status: str = "stable", type_: str = "Rule", extra: str = "") -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "---\n" + f"type: {type_}\ntitle: {json.dumps(title, ensure_ascii=False)}\n"
            + f"status: {status}\n{extra}---\n\n{body}\n", encoding="utf-8",
        )
        return target

    def command(self, *args: str, executable: str | None = None) -> list[str]:
        return [sys.executable, "-B", str(SCRIPT), "--cache-dir", str(self.cache),
                "--qmd", str(executable or QMD), str(self.root), *args]

    def invoke(self, *args: str, executable: str | None = None,
               success: bool = True) -> tuple[dict, subprocess.CompletedProcess]:
        result = subprocess.run(self.command(*args, executable=executable),
                                capture_output=True, text=True, timeout=45)
        if success:
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            return json.loads(result.stdout), result
        self.assertNotEqual(0, result.returncode, result.stderr + result.stdout)
        return {}, result

    def paths(self, query: str, *options: str) -> list[str]:
        payload, _ = self.invoke("search", query, *options)
        return [item["path"] for item in payload["candidates"]]

    def assert_model_free(self) -> None:
        self.assertEqual([], list(self.cache.rglob("*.gguf")))
        databases = list(self.cache.rglob("*.sqlite"))
        self.assertTrue(databases)
        for database in databases:
            # QMD 子进程已关闭；immutable 避免系统 SQLite 为只读探针创建 WAL sidecar。
            with sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
                self.assertEqual(0, connection.execute("SELECT count(*) FROM content_vectors").fetchone()[0], str(database))

    def test_chinese_aliases_exact_id_and_model_free_state(self) -> None:
        self.concept("business/付款规则.md", body="订单扣款需要去重，退款操作保持幂等。")
        self.concept("quality/opaque.md", title="TC-ORDER-042", type_="Test Case", body="用例说明")
        self.concept("technical/版本?.md", title="恢复策略", body="发生失败后恢复。")
        self.assertEqual(["business/付款规则.md"], self.paths("扣款 去重"))
        self.assertEqual(["business/付款规则.md"], self.paths("重复付钱", "--alternative", "退款 幂等"))
        self.assertEqual(["quality/opaque.md"], self.paths("TC-ORDER-042", "--type", "Test Case"))
        self.assertEqual(["technical/版本?.md"], self.paths("technical/版本?.md"))
        self.assertEqual([], self.paths("无匹配天文望远镜"))
        self.assert_model_free()

    def test_lifecycle_scope_and_type_filters_precede_limit(self) -> None:
        for number in range(12):
            self.concept(f"technical/old-{number}.md", title="退款 退款 退款", status="deprecated")
        self.concept("technical/current.md", type_="Unknown Type", title="当前规则")
        self.concept("technicality/wrong.md", title="退款 退款 退款", type_="Unknown Type")
        self.concept("technical/summary.md", title="退款", type_="Session Summary")
        self.concept("tasks/session-summaries/summary.md", title="退款")
        self.assertEqual(["technical/current.md"], self.paths(
            "退款", "--scope", "technical", "--type", "Unknown Type", "--limit", "1"))
        defaults = self.paths("退款", "--limit", "20")
        self.assertFalse(any("old-" in path or "summary" in path for path in defaults))
        old = self.paths("退款", "--status", "deprecated", "--limit", "20")
        self.assertEqual(12, len(old))
        history = self.paths("退款", "--history", "--limit", "20")
        self.assertIn("technical/summary.md", history)
        self.assertIn("tasks/session-summaries/summary.md", history)

    def test_archive_filter_is_applied_on_cached_index(self) -> None:
        self.concept("business/archive/rule.md", title="archive topic")
        self.concept("quality/ARCHIVE/old.md", title="archive topic", status="deprecated")
        self.concept("custom/archive/unknown.md", title="archive topic", status="mystery")
        self.concept("technical/archive-storage.md", title="archive topic")
        self.concept("custom/archived-name.md", title="archive topic")
        self.concept("technical/old.md", title="archive topic", status="deprecated")

        self.invoke("sync")
        initial = {"technical/archive-storage.md", "custom/archived-name.md"}
        self.assertEqual(initial, set(self.paths("archive topic")))
        # 无文件改动的下一次 sync 不应让历史过滤失效或改变源缓存。
        self.invoke("sync")
        self.assertEqual(initial, set(self.paths("archive topic")))
        self.assertEqual({
            "business/archive/rule.md", "quality/ARCHIVE/old.md",
            "custom/archive/unknown.md", "technical/archive-storage.md",
            "custom/archived-name.md", "technical/old.md",
        }, set(self.paths("archive topic", "--history", "--limit", "20")))
        self.assertEqual({"technical/old.md"}, set(self.paths(
            "archive topic", "--status", "deprecated", "--limit", "20")))

    def test_incremental_rename_atomic_save_same_stat_and_empty_file(self) -> None:
        original = self.concept("technical/旧名称.md", body="蜜蜂采蜜")
        self.assertEqual(["technical/旧名称.md"], self.paths("蜜蜂"))
        manifest = (self.cache / "manifest.json").read_bytes()
        mirrors = {p.name: p.stat().st_mtime_ns for p in (self.cache / "documents").glob("*.md")}
        self.invoke("sync")
        self.assertEqual(mirrors, {p.name: p.stat().st_mtime_ns for p in (self.cache / "documents").glob("*.md")})
        self.assertTrue(manifest)

        # 原子保存会更换 inode；同长度并恢复 mtime 的后续修改仍必须按内容发现。
        replacement = self.directory / "save.md"
        replacement.write_text(original.read_text().replace("蜜蜂采蜜", "蝴蝶飞舞"), encoding="utf-8")
        os.replace(replacement, original)
        stat = original.stat()
        original.write_text(original.read_text().replace("蝴蝶飞舞", "海豚游泳"), encoding="utf-8")
        os.utime(original, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual([], self.paths("蜜蜂"))
        self.assertEqual(["technical/旧名称.md"], self.paths("海豚"))

        renamed = original.with_name("新名称 #?.md")
        original.rename(renamed)
        self.assertEqual(["technical/新名称 #?.md"], self.paths("海豚"))
        renamed.write_bytes(b"")
        self.assertEqual([], self.paths("海豚"))
        self.concept("technical/新名称 #?.md", body="海豚游泳")
        self.assertEqual(["technical/新名称 #?.md"], self.paths("海豚"))
        renamed.unlink()
        self.assertEqual([], self.paths("海豚"))
        self.assert_model_free()

    def test_invalid_frontmatter_removes_old_result_and_decode_failure_is_not_deletion(self) -> None:
        target = self.concept("technical/rule.md", body="蝴蝶飞舞")
        self.assertEqual(["technical/rule.md"], self.paths("蝴蝶"))
        target.write_text("---\ntype: [broken\n---\n蝴蝶飞舞\n", encoding="utf-8")
        self.assertEqual([], self.paths("蝴蝶"))
        self.concept("technical/rule.md", body="蝴蝶飞舞")
        self.invoke("sync")
        manifest = (self.cache / "manifest.json").read_bytes()
        target.write_bytes(b"\xff\xfe")
        self.invoke("sync", success=False)
        self.assertEqual(manifest, (self.cache / "manifest.json").read_bytes())

    def test_missing_root_or_index_preserves_cache_and_refuses_stale_search(self) -> None:
        self.concept("technical/rule.md")
        self.invoke("sync")
        manifest = (self.cache / "manifest.json").read_bytes()
        index = self.root / "index.md"
        index.unlink()
        self.invoke("search", "退款", success=False)
        self.assertEqual(manifest, (self.cache / "manifest.json").read_bytes())
        index.write_text("# root\n", encoding="utf-8")
        moved = self.directory / "offline"
        self.root.rename(moved)
        self.invoke("sync", success=False)
        self.assertEqual(manifest, (self.cache / "manifest.json").read_bytes())
        moved.rename(self.root)
        self.assertEqual(["technical/rule.md"], self.paths("退款"))

    def test_read_is_bounded_and_rejects_stale_hash_and_path_escape(self) -> None:
        target = self.concept("technical/rule.md", body="退款\n" + "line\n" * 150)
        payload, _ = self.invoke("search", "退款")
        digest = payload["candidates"][0]["sha256"]
        read, _ = self.invoke("read", "technical/rule.md", "--start-line", "1",
                              "--lines", "10", "--expected-hash", digest)
        self.assertLessEqual(len(read["content"].splitlines()), 10)
        self.assertTrue(read["has_more"])
        target.write_text(target.read_text() + "changed\n", encoding="utf-8")
        self.invoke("read", "technical/rule.md", "--expected-hash", digest, success=False)
        self.invoke("read", "../outside.md", success=False)
        self.invoke("read", str(target), success=False)
        self.invoke("read", "technical/rule.md", "--lines", "0", success=False)
        outside = self.directory / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        (self.root / "technical/link.md").symlink_to(outside)
        self.invoke("read", "technical/link.md", success=False)

    def test_json_budget_and_source_snippet_are_bounded(self) -> None:
        for number in range(8):
            self.concept(f"technical/{number}.md", title="退款" + "长" * 1000,
                         body="退款" + "证据" * 4000,
                         extra=f"description: {'描述' * 2000}\ntags: [{','.join(['退款'] * 500)}]\n")
        payload, result = self.invoke("search", "退款", "--limit", "20", "--max-chars", "2000")
        self.assertLessEqual(len(result.stdout.rstrip("\n")), 2000)
        self.assertTrue(payload["truncated"])
        self.assertLess(len(payload["candidates"]), 8)
        for item in payload["candidates"]:
            self.assertLessEqual(len(item.get("snippet", "")), 240)
        for args in (("search", "退款", "--limit", "0"),
                     ("search", "退款", "--max-chars", "999"),
                     ("search", "退款", "--scope", "../"),
                     ("search", "退款", "--alternative", "two\nlines"),
                     ("search", "退款", "--alternative", "a", "--alternative", "b",
                      "--alternative", "c", "--alternative", "d")):
            self.invoke(*args, success=False)

    def test_failed_update_is_visible_and_next_sync_repairs_dirty_cache(self) -> None:
        target = self.concept("technical/rule.md", body="蜜蜂采蜜")
        self.invoke("sync")
        old_manifest = (self.cache / "manifest.json").read_bytes()
        target.write_text(target.read_text().replace("蜜蜂采蜜", "海豚游泳"), encoding="utf-8")
        failing = self.directory / "qmd-fail"
        failing.write_text(
            f"#!{sys.executable}\nimport sys\n"
            "if '--version' in sys.argv:\n print('qmd 2.8.3 (test)')\n"
            "else:\n print('injected update failure', file=sys.stderr)\n sys.exit(73)\n",
            encoding="utf-8",
        )
        failing.chmod(0o700)
        _, failure = self.invoke("search", "海豚", executable=str(failing), success=False)
        self.assertIn("injected update failure", failure.stderr)
        self.assertEqual(old_manifest, (self.cache / "manifest.json").read_bytes())
        self.assertEqual(["technical/rule.md"], self.paths("海豚"))
        self.assertEqual([], self.paths("蜜蜂"))

    def test_failed_update_then_source_revert_rebuilds_projection(self) -> None:
        target = self.concept("technical/rule.md", body="APPLE")
        self.invoke("sync")
        original = target.read_bytes()
        target.write_bytes(original.replace(b"APPLE", b"BANANA"))
        failing = self.directory / "qmd-fail"
        failing.write_text(f"#!{sys.executable}\nimport sys\n"
                           "if '--version' in sys.argv: print('qmd 2.8.3 (test)')\n"
                           "else: sys.exit(73)\n", encoding="utf-8")
        failing.chmod(0o700)
        self.invoke("sync", executable=str(failing), success=False)
        target.write_bytes(original)
        self.assertEqual(["technical/rule.md"], self.paths("APPLE"))
        self.assertEqual([], self.paths("BANANA"))

    def test_missing_and_orphan_projection_are_reconciled(self) -> None:
        self.concept("technical/rule.md", body="APPLE")
        self.invoke("sync")
        mirror = next((self.cache / "documents").glob("*.md"))
        mirror.unlink()
        self.assertEqual(["technical/rule.md"], self.paths("APPLE"))
        orphan = self.cache / "documents" / ("f" * 64 + ".md")
        orphan.write_text("# orphan\nBANANA\n", encoding="utf-8")
        (self.cache / "dirty").write_text("injected interrupted publication", encoding="utf-8")
        self.invoke("sync")
        self.assertFalse(orphan.exists())
        self.assertEqual([], self.paths("BANANA"))

    def test_crlf_documents_and_candidate_hash_race(self) -> None:
        target = self.concept("technical/rule.md", body="APPLE")
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(["technical/rule.md"], self.paths("APPLE"))
        proxy = self.directory / "qmd-race"
        proxy.write_text(f"#!{sys.executable}\nimport subprocess,sys\nfrom pathlib import Path\n"
                         f"r=subprocess.run([{str(QMD)!r},*sys.argv[1:]],capture_output=True,text=True)\n"
                         f"p=Path({str(target)!r})\n"
                         "if sys.argv[1]=='search': p.write_bytes(p.read_bytes().replace(b'APPLE',b'BANANA'))\n"
                         "sys.stdout.write(r.stdout)\nsys.stderr.write(r.stderr)\nsys.exit(r.returncode)\n",
                         encoding="utf-8")
        proxy.chmod(0o700)
        result, _ = self.invoke("search", "APPLE", executable=str(proxy))
        self.assertEqual([], result["candidates"])
        self.assertTrue(result["warnings"])

    def test_watch_updates_without_search_and_recovers_after_root_loss(self) -> None:
        target = self.concept("technical/rule.md", body="蜜蜂采蜜")
        process = subprocess.Popen(self.command("watch", "--interval", "0.1", "--debounce", "0.1",
                                                "--reconcile-seconds", "0.5"),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            self.wait_for_hash(target, process)
            moved = self.directory / "offline"
            self.root.rename(moved)
            time.sleep(0.7)
            self.assertIsNone(process.poll(), "root 消失时 watcher 应保留前台并重试")
            moved.rename(self.root)
            target.write_text(target.read_text().replace("蜜蜂采蜜", "海豚游泳"), encoding="utf-8")
            self.wait_for_hash(target, process)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
            _, errors = process.communicate(timeout=10)
        self.assertEqual(0, process.returncode, errors)
        self.assertEqual(["technical/rule.md"], self.paths("海豚"))

    def wait_for_hash(self, target: Path, process: subprocess.Popen) -> None:
        expected = hashlib.sha256(target.read_bytes()).hexdigest()
        deadline = time.monotonic() + 15
        manifest = self.cache / "manifest.json"
        while time.monotonic() < deadline:
            self.assertIsNone(process.poll(), "watcher 意外退出")
            if manifest.exists():
                # 观察发布的 manifest，而不是调用会主动同步的 search 来伪证 watcher。
                files = json.loads(manifest.read_text())["files"]
                entry = files.get("technical/rule.md", {})
                if entry.get("sha256") == expected:
                    return
            time.sleep(0.05)
        self.fail("watcher 未在期限内发布新 hash")


if __name__ == "__main__":
    unittest.main()

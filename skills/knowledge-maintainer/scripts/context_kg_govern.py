#!/usr/bin/env python3
"""显式规划、校验和可恢复地治理一个 context-kg bundle。"""

from __future__ import annotations

import argparse
import base64
import copy
import difflib
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit

from context_kg_inventory import (
    parse_document, reference_diagnostics, render_document, rewrite_document, scan_bundle,
)
from context_kg_lint import validate_concept, validate_index, validate_log


VERSION = 1
NAV = re.compile(r"^\s*[-*+]\s+\[[^\]]+\]\(([^)]+)\).*$")
MARKDOWN = {"index.md", "log.md"}


class GovernanceError(ValueError):
    """输入、快照或恢复冲突；调用方不得继续写入。"""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _valid_rel(value: Any, *, allow_parent: bool = False) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise GovernanceError(f"非法相对路径：{value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or "." in value.split("/"):
        raise GovernanceError(f"路径必须规范化且相对 bundle：{value}")
    parts = path.parts
    if not allow_parent and ".." in parts:
        raise GovernanceError(f"路径逃逸 bundle：{value}")
    if allow_parent:
        inside_parts = [part for part in parts if part != ".."]
        if parts != ("..",) * (len(parts) - len(inside_parts)) + tuple(inside_parts):
            raise GovernanceError(f"证据路径仅允许开头向上：{value}")
    return value


def _path(root: Path, rel: str) -> Path:
    root = root.resolve()
    _valid_rel(rel)
    candidate = root / rel
    # resolve() 也识别尚未创建的目标路径中已有的符号链接。
    if not candidate.resolve().is_relative_to(root):
        raise GovernanceError(f"符号链接使路径逃逸 bundle：{rel}")
    for parent in (candidate, *candidate.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise GovernanceError(f"bundle 路径含符号链接：{rel}")
    return candidate


def _read_tree(root: Path, inventory: dict[str, Any]) -> dict[str, bytes]:
    return {rel: _path(root, rel).read_bytes() for rel in inventory["files"]}


def _snapshot(inventory: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {rel: {"sha256": info["sha256"], "git_status": info["git_status"]}
            for rel, info in inventory["files"].items()}


def _load_plan(root: Path, file: Path) -> dict[str, Any]:
    try:
        plan = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"读取计划失败：{exc}") from exc
    if not isinstance(plan, dict) or plan.get("version") != VERSION or plan.get("root") != str(root):
        raise GovernanceError("计划版本或 bundle 根路径不匹配")
    if not isinstance(plan.get("snapshot"), dict) or not isinstance(plan.get("actions"), list):
        raise GovernanceError("计划缺少 snapshot 或 actions")
    if file.resolve().is_relative_to(root):
        raise GovernanceError("计划文件不得放在 bundle 内")
    return plan


def _check_snapshot(root: Path, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    for directory, directories, filenames in os.walk(root, followlinks=False):
        for name in directories + filenames:
            if (Path(directory) / name).is_symlink():
                raise GovernanceError(f"bundle 内有符号链接：{Path(directory, name).relative_to(root)}")
    inventory = scan_bundle(root)
    if set(inventory["files"]) != set(plan["snapshot"]):
        raise GovernanceError("bundle 文件集合已变化；请重新 plan")
    for rel, old in plan["snapshot"].items():
        if not isinstance(old, dict) or old.get("sha256") != inventory["files"][rel]["sha256"]:
            raise GovernanceError(f"bundle 文件内容已变化：{rel}")
        if old.get("git_status") != inventory["files"][rel]["git_status"]:
            raise GovernanceError(f"Git 边界已变化：{rel}")
    tree = _read_tree(root, inventory)
    for rel, raw in tree.items():
        if _hash(raw) != plan["snapshot"][rel]["sha256"]:
            raise GovernanceError(f"扫描后文件被并行修改：{rel}")
    return inventory, tree


def _project_root(root: Path) -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                            capture_output=True, text=True, check=False)
    if result.returncode:
        return root.parent
    return Path(result.stdout.strip()).resolve()


def _git_root(root: Path) -> Path | None:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                            capture_output=True, text=True, check=False)
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None


def _evidence(root: Path, action: dict[str, Any]) -> None:
    evidence = action.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise GovernanceError(f"{action['op']} 需要非空 evidence")
    project = _project_root(root)
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("note"), str) or not item["note"].strip():
            raise GovernanceError("evidence 必须含说明 note")
        rel = _valid_rel(item.get("path"), allow_parent=True)
        candidate = (root / rel).resolve()
        if not candidate.is_relative_to(project) or not candidate.is_file():
            raise GovernanceError(f"证据文件不存在或超出项目：{rel}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise GovernanceError(f"证据 hash 无效：{rel}")
        if _hash(candidate.read_bytes()) != item["sha256"]:
            raise GovernanceError(f"证据已变化：{rel}")


def _ignored(root: Path, rel: str) -> bool:
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root,
                      capture_output=True, check=False).returncode:
        return False
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", rel],
                            cwd=root, capture_output=True, check=False)
    if result.returncode not in (0, 1):
        raise GovernanceError("无法检查 Git ignored 边界")
    return result.returncode == 0


def _errors(root: Path, tree: dict[str, bytes]) -> Counter[tuple[str, str]]:
    failures: Counter[tuple[str, str]] = Counter()
    texts: dict[str, str] = {}
    for rel, raw in tree.items():
        if not rel.lower().endswith(".md"):
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            failures[(rel, "invalid_utf8")] += 1
            continue
        texts[rel] = text
        path = root / rel
        local: list[str] = []
        if path.name == "index.md":
            validate_index(path, root, text, local)
        elif path.name == "log.md":
            validate_log(path, text, local, [])
        else:
            validate_concept(path, text, local)
        # 一份文档原有的格式错误作为本地基线，不因路径迁移凭空变成新增。
        for message in local:
            failures[(rel, message.split(": ", 1)[-1])] += 1
    for item in reference_diagnostics(root, texts, set(tree)):
        if item["code"].startswith("broken_") or item["severity"] == "error" or item["code"] in ("missing_successor", "missing_concept_link"):
            message = item["message"]
            if item["code"] == "broken_markdown_link":
                raw = message.rsplit("：", 1)[-1].strip("<>")
                target = unquote(urlsplit(raw).path)
                if target.startswith("/"):
                    canonical = os.path.normpath(target.lstrip("/"))
                else:
                    canonical = os.path.normpath(os.path.join(os.path.dirname(item["path"]), target))
                message = canonical
            failures[(item["path"], item["code"] + ":" + message)] += 1
    return failures


def _nav_target(line: str, source: str) -> str | None:
    match = NAV.match(line)
    if not match:
        return None
    target = match.group(1).split("#", 1)[0]
    if re.match(r"^[a-z]+://", target):
        return None
    if target.startswith("/"):
        return target.lstrip("/")
    return os.path.normpath(os.path.join(os.path.dirname(source), target)).replace(os.sep, "/")


def _index_remove(tree: dict[str, bytes], parent: str, target: str) -> None:
    index = f"{parent}/index.md" if parent != "." else "index.md"
    if index not in tree:
        return
    lines = tree[index].decode("utf-8").splitlines(keepends=True)
    updated = "".join(line for line in lines if _nav_target(line, index) != target)
    if parent != "." and re.fullmatch(r"#{1,6}\s+[^\n]+", updated.strip()):
        tree.pop(index)
        _index_remove(tree, str(PurePosixPath(parent).parent), index)
    else:
        tree[index] = updated.encode("utf-8")


def _index_add(tree: dict[str, bytes], parent: str, target: str, title: str, reason: str) -> None:
    index = f"{parent}/index.md" if parent != "." else "index.md"
    text = tree[index].decode("utf-8") if index in tree else f"# {parent.rsplit('/', 1)[-1].title()}\n\n"
    if any(_nav_target(line, index) == target for line in text.splitlines()):
        return
    link = os.path.relpath(target, os.path.dirname(index) or ".").replace(os.sep, "/")
    entry = f"- [{title}]({link}) - {reason.strip()}\n"
    tree[index] = (text.rstrip() + "\n\n" + entry).encode("utf-8")


def _maintain_navigation(tree: dict[str, bytes], old: str, new: str | None, reason: str) -> None:
    old_parent = str(PurePosixPath(old).parent)
    _index_remove(tree, old_parent, old)
    if new is None:
        return
    new_parent = str(PurePosixPath(new).parent)
    name = PurePosixPath(new).stem.replace("-", " ").title()
    _index_add(tree, new_parent, new, name, reason)
    # 从新节点向根逐级补导航；已有人工条目原样保留。
    child = new_parent
    while child != ".":
        ancestor = str(PurePosixPath(child).parent)
        directory_index = f"{child}/index.md"
        if directory_index in tree:
            _index_add(tree, ancestor, directory_index,
                       PurePosixPath(child).name.replace("-", " ").title(), "目录索引")
        child = ancestor


def _remove_active_archive_navigation(tree: dict[str, bytes], old: str) -> None:
    for index in list(tree):
        if PurePosixPath(index).name != "index.md" or "archive" in PurePosixPath(index).parts:
            continue
        if index not in tree:
            continue
        text = tree[index].decode("utf-8")
        if any(_nav_target(line, index) == old for line in text.splitlines()):
            _index_remove(tree, str(PurePosixPath(index).parent), old)


def _append_log(tree: dict[str, bytes], path: str, op: str, reason: str, day: str,
                target: str | None = None) -> None:
    parent = PurePosixPath(path).parent
    while True:
        rel = f"{parent}/log.md" if str(parent) != "." else "log.md"
        if rel in tree:
            text = tree[rel].decode("utf-8")
            destination = f" → `{target}`" if target else ""
            entry = f"- **{op}** `{path}`{destination}：{reason.strip()}\n"
            heading = f"## {day}\n"
            if heading in text:
                text = text.replace(heading, heading + entry, 1)
            else:
                heading_start = re.search(r"^## ", text, re.MULTILINE)
                pos = heading_start.start() if heading_start else len(text)
                text = text[:pos].rstrip() + "\n\n" + heading + entry + "\n" + text[pos:]
            tree[rel] = text.encode("utf-8")
            return
        if str(parent) == ".":
            return
        parent = parent.parent


def _external_references(root: Path, moved: set[str], excluded: set[Path]) -> list[dict[str, str]]:
    if not moved:
        return []
    project = _project_root(root)
    if _git_root(root) is not None:
        result = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                cwd=project, capture_output=True, check=False)
        if result.returncode:
            raise GovernanceError("无法扫描 Git 外部消费者")
        relatives = [os.fsdecode(raw) for raw in result.stdout.split(b"\0") if raw]
    else:
        relatives = []
        def scan_error(error: OSError) -> None:
            raise GovernanceError(f"扫描外部消费者失败：{error}") from error

        for directory, dirs, files in os.walk(project, followlinks=False, onerror=scan_error):
            dirs[:] = [name for name in dirs if name not in {".git", "node_modules", "__pycache__", ".cache", ".venv"}
                      and not (Path(directory) / name).resolve().is_relative_to(root)
                      and not (Path(directory) / name / "owner.json").is_file()]
            for name in files:
                path = Path(directory) / name
                if not path.is_symlink():
                    relatives.append(path.relative_to(project).as_posix())
                    if len(relatives) > 10000:
                        raise GovernanceError("非 Git 项目外部文本超过扫描文件上限")
    bundle = root.relative_to(project).as_posix() if root.is_relative_to(project) else root.name
    needles = {token for old in moved for token in
               (old, old[:-3] if old.lower().endswith(".md") else old,
                f"{bundle}/{old}", f"{bundle}/{old[:-3]}" if old.lower().endswith(".md") else f"{bundle}/{old}")}
    needles = {needle for needle in needles if "/" in needle}
    findings = []
    scanned_bytes = 0
    for rel in relatives:
        path = project / rel
        if path.resolve() in excluded or path.is_relative_to(root) or any(part in {".git", "node_modules", "__pycache__", ".cache"} for part in path.parts):
            continue
        try:
            details = path.lstat()
            if not stat.S_ISREG(details.st_mode) or details.st_size > 2_000_000:
                continue
            scanned_bytes += details.st_size
            if scanned_bytes > 100_000_000:
                raise GovernanceError("外部文本超过扫描字节上限")
            content = path.read_bytes()
            if b"\x00" in content:
                continue
            text = content.decode("utf-8")
        except FileNotFoundError:
            # Git 中已删除的 tracked 文件没有当前消费者。
            continue
        except UnicodeError:
            continue
        except OSError as exc:
            raise GovernanceError(f"读取外部消费者失败：{rel}：{exc}") from exc
        hits = sorted(needle for needle in needles
                      if re.search(re.escape(needle) + r"(?![A-Za-z0-9_.-])", text))
        if hits:
            findings.append({"code": "external-ref", "severity": "error", "path": rel,
                             "message": f"外部文本仍引用旧路径/ID：{', '.join(hits[:5])}"})
    return findings


def _lifecycle(text: str, op: str, action: dict[str, Any], timestamp: str) -> str:
    metadata, body = parse_document(text)
    old_status = metadata.get("status", "stable")
    lifecycle = metadata.get("lifecycle")
    if lifecycle is None:
        lifecycle = {}
    if not isinstance(lifecycle, dict):
        raise GovernanceError("lifecycle 必须是 mapping")
    lifecycle = copy.deepcopy(lifecycle)
    if op == "archive":
        lifecycle["archive"] = {"effective_period": action["effective_period"],
                                "reason": action["reason"], "previous_status": old_status,
                                "original_path": action["path"],
                                "archived_at": timestamp,
                                "evidence": action["evidence"],
                                "replacement": action.get("replacement")}
        metadata["status"] = "deprecated"
        metadata["deprecated_reason"] = action["reason"]
        if action.get("replacement"):
            metadata["superseded_by"] = action["replacement"]
        marker = "<!-- context-kg-govern:archive -->"
        if marker not in body:
            body = (f"{marker}\n> 历史归档：{action['reason']}（适用期：{action['effective_period']}）\n"
                    "<!-- /context-kg-govern:archive -->\n\n" + body)
    else:
        archive = lifecycle.get("archive")
        if not isinstance(archive, dict):
            raise GovernanceError("恢复文档缺少可识别的归档记录")
        lifecycle["restore"] = {"reason": action["reason"], "status": action.get("status", "stable"),
                                "restored_at": timestamp, "evidence": action["evidence"]}
        metadata["status"] = action.get("status", "stable")
        metadata.pop("deprecated_reason", None)
        if metadata.get("superseded_by") == archive.get("replacement"):
            metadata.pop("superseded_by", None)
        body = re.sub(r"\A<!-- context-kg-govern:archive -->\n.*?\n<!-- /context-kg-govern:archive -->\n\n",
                      "", body, count=1, flags=re.DOTALL)
    metadata["lifecycle"] = lifecycle
    return render_document(metadata, body)


def _action_tree(root: Path, plan: dict[str, Any], inventory: dict[str, Any],
                 original: dict[str, bytes]) -> tuple[dict[str, bytes], dict[str, str], list[dict[str, str]]]:
    actions = plan["actions"]
    if not actions:
        return original.copy(), {}, []
    tree = original.copy()
    mapping: dict[str, str] = {}
    touched: set[str] = set()
    diagnostics: list[dict[str, str]] = []
    deletes: set[str] = set()
    try:
        timestamp = plan["created_at"]
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed_time.tzinfo is None:
            raise ValueError("missing timezone")
        day = parsed_time.date().isoformat()
    except (KeyError, AttributeError, ValueError) as exc:
        raise GovernanceError(f"计划 created_at 必须是带时区 ISO 时间：{exc}") from exc
    for number, action in enumerate(actions, 1):
        if not isinstance(action, dict):
            raise GovernanceError(f"action {number} 必须是 object")
        op = action.get("op")
        if op not in {"move", "update", "archive", "restore", "delete"}:
            raise GovernanceError(f"action {number} 的 op 无效")
        path = _valid_rel(action.get("path"))
        _path(root, path)
        if path not in original:
            raise GovernanceError(f"action 源文件不存在：{path}")
        if path in touched:
            raise GovernanceError(f"同一源文件重复 action：{path}")
        touched.add(path)
        reason = action.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise GovernanceError(f"action 缺少 reason：{path}")
        if op in {"update", "archive", "restore", "delete"}:
            _evidence(root, action)
        if op in {"archive", "restore", "update"} and inventory["files"][path]["kind"] != "concept":
            raise GovernanceError(f"{op} 只适用于 concept：{path}")
        if op == "delete" and inventory["files"][path]["kind"] in {"index", "log"}:
            raise GovernanceError("index/log 由导航和日志维护，不能直接 delete")
        if op == "move" and inventory["files"][path]["kind"] in {"index", "log"}:
            raise GovernanceError("index/log 由导航维护，不能直接 move")
        if op in {"move", "archive", "restore"}:
            target = action.get("target")
            if op == "archive" and target is None:
                parent = PurePosixPath(path).parent
                target = str(parent / "archive" / PurePosixPath(path).name)
            target = _valid_rel(target)
            if _path(root, target).is_dir():
                raise GovernanceError(f"迁移目标已是目录：{target}")
            if target == path:
                raise GovernanceError(f"迁移目标等于源文件：{path}")
            if op == "archive":
                if "archive" not in PurePosixPath(target).parts:
                    raise GovernanceError("archive 目标必须位于 archive 目录")
                if not isinstance(action.get("effective_period"), str) or not action["effective_period"].strip():
                    raise GovernanceError("archive 需要 effective_period")
                replacement = action.get("replacement")
                if replacement is not None:
                    replacement = _valid_rel(replacement if replacement.endswith(".md") else replacement + ".md")
                    if replacement not in original or replacement == path:
                        raise GovernanceError("replacement 必须指向已有的其他 concept")
                    action["replacement"] = replacement
            if op == "restore":
                if "archive" not in PurePosixPath(path).parts or "archive" in PurePosixPath(target).parts:
                    raise GovernanceError("restore 必须从 archive 目录迁回活动目录")
                if action.get("status", "stable") not in {"stable", "draft"}:
                    raise GovernanceError("restore status 仅允许 stable 或 draft")
            source_ignored = inventory["files"][path]["git_status"] == "ignored"
            if source_ignored != _ignored(root, target):
                raise GovernanceError(f"迁移跨越 Git ignored 边界：{path} -> {target}")
            mapping[path] = target
            if op in {"archive", "restore"}:
                tree[path] = _lifecycle(tree[path].decode("utf-8"), op, action, timestamp).encode("utf-8")
        elif op == "update":
            patch = action.get("metadata", {})
            if not isinstance(patch, dict) or any(not isinstance(key, str) for key in patch):
                raise GovernanceError("update.metadata 必须是 mapping")
            metadata, body = parse_document(tree[path].decode("utf-8"))
            metadata.update(patch)
            if metadata.get("status") not in (None, "draft", "stable", "deprecated"):
                raise GovernanceError("status 仅允许 draft/stable/deprecated")
            if "body" in action:
                if not isinstance(action["body"], str):
                    raise GovernanceError("update.body 必须是 string")
                body = action["body"]
            tree[path] = render_document(metadata, body).encode("utf-8")
        else:
            preservation = action.get("preservation")
            if not isinstance(preservation, dict) or not isinstance(preservation.get("note"), str) or not preservation["note"].strip():
                raise GovernanceError("delete 需要 preservation.note")
            target = preservation.get("target")
            if target is not None and (_valid_rel(target) not in original or target == path):
                raise GovernanceError("preservation.target 必须是已有的其他文件或 null")
            deletes.add(path)
    if len(set(mapping.values())) != len(mapping):
        raise GovernanceError("多个迁移指向同一目标")
    for action in actions:
        retained_target = (action.get("replacement") if action["op"] == "archive" else
                           action.get("preservation", {}).get("target") if action["op"] == "delete" else None)
        if retained_target in deletes:
            raise GovernanceError(f"处置目标也在同一计划中删除：{retained_target}")
    for old, new in mapping.items():
        if new in original:
            raise GovernanceError(f"迁移目标已经存在：{new}")
        if new in mapping or old in mapping.values():
            raise GovernanceError("迁移映射包含链或循环")
    for old in deletes:
        tree.pop(old)
        _maintain_navigation(tree, old, None, "")
        action = next(a for a in actions if a["path"] == old)
        preservation = action["preservation"]
        note = f"{action['reason']}；保留说明：{preservation['note']}"
        _append_log(tree, old, "delete", note, day, preservation.get("target"))
    known = set(original)
    for old, new in mapping.items():
        tree[new] = tree.pop(old)
    for action in actions:
        old = action["path"]
        if old in mapping:
            new = mapping[old]
            if action["op"] == "archive":
                _remove_active_archive_navigation(tree, old)
            _maintain_navigation(tree, old, new, action["reason"])
            _append_log(tree, old, action["op"], action["reason"], day, new)
            if action["op"] == "archive":
                diagnostics.append({"code": "archived", "severity": "info", "path": new,
                                    "message": "归档后需按 effective_period 和证据人工复核"})
        elif action["op"] == "update":
            _append_log(tree, old, "update", action["reason"], day)
    affected = set(mapping)
    for ref in inventory["references"]:
        if ref.get("resolved") in mapping or any(ref.get("target") in (old, old[:-3]) for old in mapping):
            affected.add(ref["path"])
    # 仅迁移自身及确有入链的文档改写；无关旧坏文档保持原字节。
    for rel, raw in list(tree.items()):
        if not rel.lower().endswith(".md"):
            continue
        source = next((old for old, new in mapping.items() if new == rel), rel)
        if source not in affected:
            continue
        text = raw.decode("utf-8")
        rewritten = rewrite_document(text, source, rel, mapping, root, known)
        if rewritten != text:
            tree[rel] = rewritten.encode("utf-8")
    folded: dict[str, str] = {}
    for rel in tree:
        key = rel.casefold()
        if key in folded and folded[key] != rel:
            raise GovernanceError(f"大小写不敏感目标冲突：{folded[key]} / {rel}")
        folded[key] = rel
    if "index.md" not in tree:
        raise GovernanceError("拟议结果缺少 bundle 根 index.md")
    for key, rel in folded.items():
        parent = PurePosixPath(key).parent
        while str(parent) != ".":
            if str(parent) in folded:
                raise GovernanceError(f"文件/目录路径冲突：{folded[str(parent)]} / {rel}")
            parent = parent.parent
    return tree, mapping, diagnostics


def _diff(before: dict[str, bytes], after: dict[str, bytes]) -> str:
    chunks = []
    for rel in sorted(set(before) | set(after)):
        old, new = before.get(rel), after.get(rel)
        if old == new:
            continue
        try:
            old_lines = old.decode("utf-8").splitlines(keepends=True) if old is not None else []
            new_lines = new.decode("utf-8").splitlines(keepends=True) if new is not None else []
        except UnicodeError:
            chunks.append(f"Binary: {rel} ({_hash(old or b'')[:12]} -> {_hash(new or b'')[:12]})\n")
            continue
        chunks.extend(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(chunks)


def audit_bundle(root: Path, limit: int = 30) -> dict[str, Any]:
    """只读完整盘点；limit 仅影响 CLI 标准输出，返回值保留完整诊断。"""
    if limit < 0:
        raise GovernanceError("limit 不得为负数")
    return scan_bundle(root.expanduser().resolve())


def create_plan(root: Path, output: Path) -> dict[str, Any]:
    """生成只含快照的计划；action 由宿主填入，调用不修改 bundle。"""
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if output.is_relative_to(root):
        raise GovernanceError("计划文件不得放在 bundle 内")
    inventory = scan_bundle(root)
    if any(item["code"] in ("missing_root", "missing_root_index") for item in inventory["diagnostics"]):
        raise GovernanceError("bundle 根目录或 index 缺失")
    plan = {"version": VERSION, "root": str(root), "created_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": _snapshot(inventory), "actions": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(output, _json(plan).encode("utf-8"))
    return plan


def _check_plan_details(root: Path, plan_file: Path) -> tuple[dict[str, Any], dict[str, bytes], dict[str, bytes]]:
    root = root.expanduser().resolve()
    plan = _load_plan(root, plan_file)
    inventory, before = _check_snapshot(root, plan)
    if not plan["actions"]:
        return {"status": "no-op", "actions": 0, "changed": [], "deleted": [],
                "warnings": ["计划没有 action"], "blockers": [], "diff": ""}, before, before.copy()
    after, mapping, warnings = _action_tree(root, plan, inventory, before)
    before_errors = _errors(root, before)
    after_errors = _errors(root, after)
    blockers = []
    for (path, issue), count in after_errors.items():
        baseline = before_errors.get((next((old for old, new in mapping.items() if new == path), path), issue), 0)
        if count > baseline:
            blockers.append({"code": "new-validation-error", "severity": "error", "path": path,
                             "message": f"新增 {count - baseline} 项格式/断链错误：{issue}"})
    blockers.extend(_external_references(root, set(mapping) | set(rel for rel in before if rel not in after),
                                         {plan_file.resolve()}))
    changed = sorted(rel for rel, raw in after.items() if before.get(rel) != raw)
    deleted = sorted(set(before) - set(after))
    report = {"status": "blocked" if blockers else "ready", "actions": len(plan["actions"]),
              "changed": changed, "deleted": deleted, "moves": mapping, "warnings": warnings,
              "blockers": blockers, "diff": _diff(before, after)}
    return report, before, after


def check_plan(root: Path, plan_file: Path) -> dict[str, Any]:
    """对全快照和拟议结果作只读检查；返回可审阅 diff 与 blocker。"""
    return _check_plan_details(root, plan_file)[0]


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else mode
    descriptor, name = tempfile.mkstemp(prefix=".context-kg-govern-", dir=path.parent)
    try:
        os.fchmod(descriptor, original_mode if original_mode is not None else 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _state(root: Path, state_dir: Path | None) -> Path:
    root = root.resolve()
    project = _git_root(root)
    base = (state_dir or (Path.home() / ".cache" / "context-kg-govern")).expanduser().resolve()
    if (project is not None and base.is_relative_to(project)) or base.is_relative_to(root):
        raise GovernanceError("状态目录必须位于项目/Git 工作区之外")
    existing_parent = base
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    enclosing_git = _git_root(existing_parent)
    if enclosing_git is not None and base.is_relative_to(enclosing_git):
        raise GovernanceError("状态目录不能位于其他 Git 工作区内")
    marker = base / "owner.json"
    if base.exists():
        if not base.is_dir() or (any(base.iterdir()) and not marker.is_file()):
            raise GovernanceError("状态目录非空且没有 owner 标记")
        if stat.S_IMODE(base.stat().st_mode) & 0o077:
            raise GovernanceError("状态目录必须仅当前用户可读写（mode 0700）")
    else:
        base.mkdir(parents=True, mode=0o700)
    if marker.exists():
        try:
            owner = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise GovernanceError(f"状态 owner 标记损坏：{exc}") from exc
        if owner != {"tool": "context-kg-govern", "version": VERSION}:
            raise GovernanceError("状态目录 owner 不匹配")
    else:
        _atomic_write(marker, _json({"tool": "context-kg-govern", "version": VERSION}).encode(), 0o600)
    isolated = base / _hash(str(root).encode())
    isolated.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(isolated.stat().st_mode) & 0o077:
        raise GovernanceError("bundle 状态子目录权限过宽")
    return isolated


@contextmanager
def _lock(state: Path) -> Iterator[None]:
    path = state / "lock"
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        try:
            identity = path.stat()
            pid = int(path.read_text(encoding="ascii").strip())
            os.kill(pid, 0)
        except ProcessLookupError:
            if path.stat().st_ino != identity.st_ino:
                raise GovernanceError("lock 并行变化，拒绝接管") from exc
            path.unlink()
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except (OSError, ValueError):
            raise GovernanceError("lock 所属进程无法判定，拒绝接管") from exc
        else:
            raise GovernanceError(f"治理状态目录被存活进程 {pid} 使用") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)


def _current(root: Path, rel: str) -> bytes | None:
    path = _path(root, rel)
    if path.exists():
        if not path.is_file():
            raise GovernanceError(f"目标不是普通文件：{rel}")
        return path.read_bytes()
    return None


def _current_mode(root: Path, rel: str) -> int | None:
    path = _path(root, rel)
    return stat.S_IMODE(path.stat().st_mode) if path.exists() else None


def _write_change(root: Path, rel: str, data: bytes | None, mode: int | None = None) -> None:
    path = _path(root, rel)
    if data is None:
        if path.exists():
            path.unlink()
            _fsync_dir(path.parent)
    else:
        _atomic_write(path, data, mode)


def _encoded(value: bytes | None) -> dict[str, str | None]:
    return {"sha256": _hash(value) if value is not None else None,
            "bytes": base64.b64encode(value).decode("ascii") if value is not None else None}


def _decoded(value: dict[str, str | None]) -> bytes | None:
    if value["bytes"] is None:
        return None
    data = base64.b64decode(value["bytes"], validate=True)
    if _hash(data) != value["sha256"]:
        raise GovernanceError("journal bytes 与 hash 不匹配")
    return data


def _save_journal(state: Path, journal: dict[str, Any]) -> None:
    _atomic_write(state / "journal.json", _json(journal).encode("utf-8"), 0o600)


def _recover_locked(root: Path, state: Path) -> dict[str, Any]:
    journal_file = state / "journal.json"
    if not journal_file.exists():
        raise GovernanceError("没有可恢复的 journal")
    try:
        journal = json.loads(journal_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GovernanceError(f"journal 无法读取：{exc}") from exc
    if journal.get("root") != str(root) or journal.get("version") != VERSION:
        raise GovernanceError("journal 所属 bundle 或版本不匹配")
    entries = journal.get("entries")
    if not isinstance(entries, list):
        raise GovernanceError("journal 缺少 entries")
    # 预检全部文件，再执行回滚，避免发现后段冲突时已修改前段文件。
    for entry in entries:
        rel = _valid_rel(entry["path"])
        old = _decoded(entry["before"])
        new = _decoded(entry["after"])
        current = _current(root, rel)
        if current not in (old, new):
            raise GovernanceError(f"恢复冲突：{rel} 已被并行修改，保留 journal")
        if current == new and _current_mode(root, rel) != entry.get("after_mode"):
            raise GovernanceError(f"恢复冲突：{rel} 的权限已被并行修改")
    for entry in reversed(entries):
        rel = entry["path"]
        old = _decoded(entry["before"])
        new = _decoded(entry["after"])
        current = _current(root, rel)
        if current not in (old, new):
            raise GovernanceError(f"恢复期间文件被并行修改：{rel}，保留 journal")
        if current == new and _current_mode(root, rel) != entry.get("after_mode"):
            raise GovernanceError(f"恢复期间文件权限被并行修改：{rel}")
        if current != old:
            _write_change(root, rel, old, entry.get("before_mode"))
    journal["state"] = "recovered"
    _save_journal(state, journal)
    return {"status": "recovered", "paths": [item["path"] for item in entries]}


def recover(root: Path, state_dir: Path | None = None) -> dict[str, Any]:
    """恢复 prepared/applying/committed 事务；并行修改导致冲突时不覆盖。"""
    root = root.expanduser().resolve()
    state = _state(root, state_dir)
    with _lock(state):
        return _recover_locked(root, state)


def apply_plan(root: Path, plan_file: Path, state_dir: Path | None = None) -> dict[str, Any]:
    """先复验计划，再持久化完整 journal，逐文件原子替换；异常尝试安全回滚。"""
    root = root.expanduser().resolve()
    state = _state(root, state_dir)
    with _lock(state):
        journal_file = state / "journal.json"
        old = None
        if journal_file.exists():
            old = json.loads(journal_file.read_text(encoding="utf-8"))
            if old.get("state") not in {"recovered", "committed"}:
                raise GovernanceError("已有待恢复事务；先 recover")
        report, before, after = _check_plan_details(root, plan_file)
        if report["blockers"]:
            raise GovernanceError("计划存在阻断项：" + "; ".join(item["message"] for item in report["blockers"]))
        if report["status"] == "no-op":
            return report
        if old is not None:
            history = state / "history"
            history.mkdir(mode=0o700, exist_ok=True)
            os.replace(journal_file, history / f"{uuid.uuid4().hex}.json")
            _fsync_dir(history)
            _fsync_dir(state)
        paths = sorted(set(before) | set(after))
        inverse_moves = {new: old for old, new in report["moves"].items()}
        entries = []
        for rel in paths:
            if before.get(rel) == after.get(rel):
                continue
            before_mode = _current_mode(root, rel)
            source = inverse_moves.get(rel)
            after_mode = (before_mode if after.get(rel) is not None and before_mode is not None else
                          _current_mode(root, source) if source else 0o644 if after.get(rel) is not None else None)
            entries.append({"path": rel, "before": _encoded(before.get(rel)),
                            "after": _encoded(after.get(rel)),
                            "before_mode": before_mode, "after_mode": after_mode})
        journal = {"version": VERSION, "root": str(root), "state": "prepared", "entries": entries}
        _save_journal(state, journal)
        try:
            journal["state"] = "applying"
            _save_journal(state, journal)
            for entry in entries:
                rel = entry["path"]
                if (_current(root, rel) != _decoded(entry["before"]) or
                        _current_mode(root, rel) != entry["before_mode"]):
                    raise GovernanceError(f"写入前文件已变化：{rel}")
                _write_change(root, rel, _decoded(entry["after"]), entry["after_mode"])
            journal["state"] = "committed"
            _save_journal(state, journal)
        except Exception:
            try:
                _recover_locked(root, state)
            except Exception as recovery_error:
                raise GovernanceError(f"执行失败且自动恢复未完成：{recovery_error}") from recovery_error
            raise
        return {**report, "status": "applied", "journal": str(journal_file)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("root", type=Path)
    audit.add_argument("--output", type=Path)
    audit.add_argument("--limit", type=int, default=30)
    plan = commands.add_parser("plan")
    plan.add_argument("root", type=Path)
    plan.add_argument("--output", type=Path, required=True)
    for name in ("check", "apply"):
        command = commands.add_parser(name)
        command.add_argument("root", type=Path)
        command.add_argument("--plan", type=Path, required=True)
        if name == "apply":
            command.add_argument("--state-dir", type=Path)
    recovery = commands.add_parser("recover")
    recovery.add_argument("root", type=Path)
    recovery.add_argument("--state-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = audit_bundle(args.root, args.limit)
            if args.output:
                output = args.output.expanduser().resolve()
                if output.is_relative_to(args.root.expanduser().resolve()):
                    raise GovernanceError("盘点输出不得放在 bundle 内")
                _atomic_write(output, _json(result).encode("utf-8"))
            print(_json({"root": result["root"], "counts": result["counts"],
                         "diagnostic_count": len(result["diagnostics"]),
                         "diagnostics": result["diagnostics"][:args.limit]}), end="")
        elif args.command == "plan":
            result = create_plan(args.root, args.output)
            print(_json({"root": result["root"], "created_at": result["created_at"],
                         "plan": str(args.output.expanduser().resolve()),
                         "files": len(result["snapshot"]), "actions": 0}), end="")
        elif args.command == "check":
            result = check_plan(args.root, args.plan)
            print(_json(result), end="")
            return 2 if result["blockers"] else 0
        elif args.command == "apply":
            print(_json(apply_plan(args.root, args.plan, args.state_dir)), end="")
        else:
            print(_json(recover(args.root, args.state_dir)), end="")
        return 0
    except (GovernanceError, ValueError, OSError) as exc:
        print(f"context-kg-govern: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

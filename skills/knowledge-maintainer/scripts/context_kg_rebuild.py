"""Rebuild 语义验收：完整判读、拟议树导航与无状态检索证明。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from context_kg_history import is_archive_path
from context_kg_inventory import _active_lines, _markdown_targets, _reference_target, parse_document, reference_diagnostics
from context_kg_lint import INDEX_ENTRY, link_target, validate_concept, validate_index, validate_log
from context_kg_search import search

DECISIONS = {"keep", "review", "move", "update", "archive", "delete", "merge"}
LIFECYCLES = {"current", "target", "historical", "review"}
UNKNOWN_ROLES = {"unknown", "unclassified"}


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": "error", "path": path, "message": message}


def _rel(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or value.startswith("/"):
        return None
    return value


def _concept(path: str) -> bool:
    return path.lower().endswith(".md") and PurePosixPath(path).name not in {"index.md", "log.md"}


def _archive(path: str) -> bool:
    return is_archive_path(path)


def _target(decision: dict[str, Any], action: dict[str, Any] | None) -> str:
    path = decision["path"]
    if action and action["op"] == "archive":
        return action.get("target") or str(PurePosixPath(path).parent / "archive" / PurePosixPath(path).name)
    if action and action.get("op") in {"move", "restore"}:
        return action.get("target", path)
    return path


def _taxonomy_for(path: str, taxonomy: list[dict[str, Any]]) -> dict[str, Any] | None:
    directory = str(PurePosixPath(path).parent)
    matches = [rule for rule in taxonomy if rule["directory"] == "." or
               directory == rule["directory"] or
               directory.startswith(rule["directory"] + "/")]
    return max(matches, key=lambda rule: len(rule["directory"])) if matches else None


def _read_metadata(path: str, tree: dict[str, bytes], blockers: list[dict[str, str]]) -> dict[str, Any]:
    try:
        metadata, _ = parse_document(tree[path].decode("utf-8"))
        return metadata
    except (UnicodeError, ValueError) as exc:
        blockers.append(_issue("invalid-concept", path, f"无法读取 concept：{exc}"))
        return {}


def _historical_navigation(root: Path, tree: dict[str, bytes], metadata: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    blockers = []
    for index, raw in tree.items():
        if PurePosixPath(index).name != "index.md" or _archive(index):
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            continue
        for linked in _markdown_targets(text):
            reference = _reference_target(index, linked, root, set(tree))
            resolved = reference[0] if reference else None
            if resolved in metadata and (_archive(resolved) or metadata[resolved].get("status") == "deprecated"):
                blockers.append(_issue("active-index-history", index,
                                       f"活动索引直接链接历史 concept：{resolved}"))
    return blockers


def _navigation_coverage(root: Path, tree: dict[str, bytes]) -> list[dict[str, str]]:
    """拟议/实际树的直属项应可逐层发现；不把此生产者约定加入 OKF lint 门禁。"""
    root = root.resolve()
    markdown = {path for path in tree if path.lower().endswith(".md")}
    directories = {"."}
    for path in markdown:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            directories.add(str(parent))
            parent = parent.parent
    blockers: list[dict[str, str]] = []
    for directory in sorted(directories):
        concepts = {path for path in markdown if _concept(path) and
                    str(PurePosixPath(path).parent) == directory}
        children = {child for child in directories if child != "." and
                    str(PurePosixPath(child).parent) == directory}
        if not concepts and not children:
            continue
        index = f"{directory}/index.md" if directory != "." else "index.md"
        if index not in tree:
            if directory == "." or len(concepts) + len(children) >= 2:
                blockers.append(_issue("missing-required-index", index,
                                       "根目录或至少两个直属项的目录必须有 index.md"))
            continue
        try:
            text = tree[index].decode("utf-8")
        except UnicodeError:
            continue
        active = "".join(masked for _, masked in _active_lines(text))
        linked_concepts: set[str] = set()
        linked_directories: set[str] = set()
        for raw_target, _ in INDEX_ENTRY.findall(active):
            target = link_target(root / index, root, raw_target)
            if target is None:
                continue
            resolved = target.resolve()
            if not resolved.is_relative_to(root):
                continue
            rel = resolved.relative_to(root).as_posix()
            if rel in concepts:
                linked_concepts.add(rel)
            elif rel in children:
                linked_directories.add(rel)
            elif rel.endswith("/index.md") and rel in tree and rel[:-9] in children:
                linked_directories.add(rel[:-9])
        for missing in sorted(concepts - linked_concepts):
            blockers.append(_issue("unlisted-direct-concept", index, f"索引未列出直属 concept：{missing}"))
        for missing in sorted(children - linked_directories):
            blockers.append(_issue("unlisted-direct-directory", index, f"索引未列出直属目录：{missing}"))
    return blockers


def _structure_and_references(root: Path, tree: dict[str, bytes]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """rebuild 完成态检查整棵树；普通 plan 的既有错误基线不受影响。"""
    blockers: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    for path, raw in tree.items():
        if not path.lower().endswith(".md"):
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            blockers.append(_issue("invalid-utf8", path, "Markdown 文件必须为 UTF-8"))
            continue
        texts[path] = text
        errors: list[str] = []
        full_path = root / path
        if full_path.name == "index.md":
            validate_index(full_path, root, text, errors)
        elif full_path.name == "log.md":
            validate_log(full_path, text, errors, [])
        else:
            validate_concept(full_path, text, errors)
        for error in errors:
            blockers.append(_issue("invalid-format", path, error))
    for item in reference_diagnostics(root, texts, set(tree)):
        if item["code"] == "unsupported_markdown_link":
            review.append({"code": item["code"], "path": item["path"], "message": item["message"]})
        elif item["code"] in {"broken_markdown_link", "broken_source_path", "missing_concept_link",
                              "missing_successor", "missing_archive_replacement",
                              "ambiguous_concept_link", "superseded_cycle"} or item["severity"] == "error":
            blockers.append(_issue(item["code"], item["path"], item["message"]))
    return blockers, review


def _probe_results(tree: dict[str, bytes], probes: list[dict[str, Any]],
                   metadata: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    results: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="context-kg-rebuild-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        for path, raw in tree.items():
            destination = root / path
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for parent in destination.parents:
                if parent == root.parent:
                    break
                parent.chmod(0o700)
            destination.write_bytes(raw)
            destination.chmod(0o600)
        for number, probe in enumerate(probes, 1):
            label = f"probe[{number}]"
            if not isinstance(probe, dict) or not isinstance(probe.get("query"), str) or not probe["query"].strip():
                blockers.append(_issue("invalid-probe", label, "query 必须非空"))
                continue
            scope = probe.get("scope")
            if scope is not None and _rel(scope) is None:
                blockers.append(_issue("invalid-probe", label, "scope 必须是 bundle 相对路径"))
                continue
            expected: dict[str, list[str]] = {}
            malformed = False
            for field in ("include", "exclude", "history_include"):
                values = probe.get(field, [])
                if not isinstance(values, list) or any(_rel(v) is None for v in values) or len(values) != len(set(values)):
                    blockers.append(_issue("invalid-probe", label, f"{field} 必须是不重复的相对路径数组"))
                    malformed = True
                    continue
                expected[field] = values
                for value in values:
                    if value not in metadata:
                        blockers.append(_issue("probe-path-missing", label, f"{field} 路径不存在：{value}"))
                    elif scope and not (value == scope or value.startswith(scope + "/")):
                        blockers.append(_issue("probe-outside-scope", label, f"{field} 不在 scope 内：{value}"))
            if malformed or any(v not in metadata for values in expected.values() for v in values):
                continue
            limit = max(1, len(metadata) + 1)
            try:
                ordinary = {hit.path for hit in search(root, probe["query"], scope=scope, limit=limit,
                                                        include_body=True)}
                historical = {hit.path for hit in search(root, probe["query"], scope=scope, limit=limit,
                                                          include_body=True, history=True)}
            except ValueError as exc:
                blockers.append(_issue("probe-search-failed", label, str(exc)))
                continue
            for path in expected["include"]:
                if path not in ordinary:
                    blockers.append(_issue("probe-include-missing", label, f"普通检索未命中：{path}"))
            for path in expected["exclude"]:
                if path in ordinary:
                    blockers.append(_issue("probe-exclude-hit", label, f"普通检索仍命中：{path}"))
            for path in expected["history_include"]:
                if path not in historical:
                    blockers.append(_issue("probe-history-missing", label, f"历史检索未命中：{path}"))
            results.append({"query": probe["query"], "scope": scope, "ordinary_hits": sorted(ordinary),
                            "history_hits": sorted(historical)})
    return results, blockers


def assess_rebuild(root: Path, plan: dict[str, Any], before_paths: set[str], tree: dict[str, bytes],
                   *, verify: bool = False) -> dict[str, Any]:
    """输入原计划路径及拟议/实际树，返回验收状态和阻断项；只读且不判断语义真伪。

    例如完整 keep 决策和正向 probe 可得 complete；漏掉一个原 concept 得 blocked。
    verify=True 时还检查应用后的文件集合，允许自动维护的 index/log 变化。
    """
    blockers: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    manifest = plan.get("rebuild")
    if plan.get("mode") != "rebuild" or not isinstance(manifest, dict):
        return {"completion": "blocked", "blockers": [_issue("missing-manifest", "", "缺少 rebuild manifest")],
                "review": []}
    taxonomy = manifest.get("taxonomy")
    decisions = manifest.get("decisions")
    probes = manifest.get("probes")
    if not isinstance(taxonomy, list) or not taxonomy:
        blockers.append(_issue("missing-taxonomy", "", "taxonomy 必须声明目标目录规则"))
        taxonomy = []
    if not isinstance(decisions, list):
        blockers.append(_issue("missing-decisions", "", "decisions 必须为数组"))
        decisions = []
    if not isinstance(probes, list):
        blockers.append(_issue("missing-probes", "", "probes 必须为数组"))
        probes = []
    good_rules = []
    directories = set()
    for number, rule in enumerate(taxonomy, 1):
        if (not isinstance(rule, dict) or (rule.get("directory") != "." and _rel(rule.get("directory")) is None) or
                not isinstance(rule.get("roles"), list) or not rule["roles"] or
                any(not isinstance(role, str) or not role.strip() or role.strip().casefold() in UNKNOWN_ROLES
                    for role in rule["roles"]) or
                not isinstance(rule.get("lifecycles"), list) or not rule["lifecycles"] or
                any(value not in LIFECYCLES for value in rule["lifecycles"]) or
                ("max_direct_concepts" in rule and
                 (type(rule["max_direct_concepts"]) is not int or rule["max_direct_concepts"] < 0))):
            blockers.append(_issue("invalid-taxonomy", f"taxonomy[{number}]", "目录、roles、lifecycles 或预算无效"))
            continue
        if rule["directory"] in directories:
            blockers.append(_issue("duplicate-taxonomy", rule["directory"], "目录规则重复"))
            continue
        directories.add(rule["directory"])
        good_rules.append(rule)
    actions = plan.get("actions", [])
    action_by_path = {action.get("path"): action for action in actions if isinstance(action, dict)}
    original_concepts = {path for path in before_paths if _concept(path)}
    final_concepts = {path for path in tree if _concept(path)}
    decision_by_path: dict[str, dict[str, Any]] = {}
    final_by_source: dict[str, str] = {}
    for number, decision in enumerate(decisions, 1):
        if not isinstance(decision, dict) or _rel(decision.get("path")) is None:
            blockers.append(_issue("invalid-decision", f"decision[{number}]", "path 无效"))
            continue
        path = decision["path"]
        if path in decision_by_path:
            blockers.append(_issue("duplicate-decision", path, "原 concept 决策重复"))
            continue
        decision_by_path[path] = decision
        if path not in original_concepts:
            blockers.append(_issue("unexpected-decision", path, "不是原 snapshot 中的 concept"))
            continue
        disposition = decision.get("disposition")
        lifecycle = decision.get("lifecycle")
        role = decision.get("role")
        if (disposition not in DECISIONS or lifecycle not in LIFECYCLES or
                not isinstance(role, str) or not role.strip() or role.strip().casefold() in UNKNOWN_ROLES or
                not isinstance(decision.get("reason"), str) or not decision["reason"].strip()):
            blockers.append(_issue("invalid-decision", path, "role/lifecycle/disposition/reason 无效"))
            continue
        action = action_by_path.get(path)
        expected_op = {"move": "move", "update": "update", "archive": "archive",
                       "delete": "delete", "merge": "delete"}.get(disposition)
        if disposition in {"keep", "review"} and action:
            blockers.append(_issue("action-mismatch", path, "keep/review 不得有同源 action"))
        elif expected_op and (not action or action.get("op") != expected_op):
            blockers.append(_issue("action-mismatch", path, f"{disposition} 必须对应 {expected_op} action"))
        if disposition == "merge" and action:
            preservation = action.get("preservation", {})
            target = preservation.get("target") if isinstance(preservation, dict) else None
            merged_action = action_by_path.get(target)
            if (not target or not merged_action or merged_action.get("op") != "update" or
                    decision.get("target") != target):
                blockers.append(_issue("merge-preservation", path, "merge 须声明目标且由目标 update + 来源 delete 保全"))
        if disposition in {"delete", "merge"}:
            if path in tree:
                blockers.append(_issue("source-retained", path, "delete/merge 来源仍存在"))
            continue
        final_path = _target(decision, action)
        if _rel(final_path) is None or not _concept(final_path):
            blockers.append(_issue("invalid-target", path, "目标必须是 concept 相对路径"))
            continue
        if "target" in decision and decision["target"] != final_path:
            blockers.append(_issue("target-mismatch", path, f"决策目标与实际 action 不符：{final_path}"))
        if final_path in final_by_source:
            blockers.append(_issue("target-collision", final_path, "多个原 concept 对应同一目标"))
        final_by_source[final_path] = path
        if final_path not in tree:
            blockers.append(_issue("target-missing", path, f"目标缺失：{final_path}"))
            continue
        if final_path != path and path in tree:
            blockers.append(_issue("source-retained", path, "迁移后来源仍存在"))
        rule = _taxonomy_for(final_path, good_rules)
        if rule is None or role not in rule["roles"] or lifecycle not in rule["lifecycles"]:
            blockers.append(_issue("taxonomy-mismatch", final_path, f"角色/生命周期不匹配目标目录：{role}/{lifecycle}"))
        if lifecycle == "review" or disposition == "review":
            review.append({"code": "declared-review", "path": final_path, "message": decision["reason"]})
        if lifecycle == "historical" and not _archive(final_path):
            blockers.append(_issue("history-path", final_path, "historical 必须位于 archive 目录"))
        if lifecycle in {"current", "target"} and _archive(final_path):
            blockers.append(_issue("active-in-archive", final_path, "current/target 不得位于 archive 目录"))
    for path in sorted(original_concepts - set(decision_by_path)):
        blockers.append(_issue("missing-decision", path, "原 concept 缺少完整判读"))
    for path in sorted(final_concepts - set(final_by_source)):
        blockers.append(_issue("uncovered-final", path, "最终 concept 无原决策覆盖"))
    if verify:
        if "index.md" not in tree:
            blockers.append(_issue("missing-root-index", "index.md", "应用后的根索引缺失"))
        for action in actions:
            if not isinstance(action, dict) or action.get("op") != "update":
                continue
            path = action.get("path")
            if path in tree and path in plan["snapshot"] and hashlib.sha256(tree[path]).hexdigest() == plan["snapshot"][path].get("sha256"):
                blockers.append(_issue("update-not-applied", path, "update 目标内容与原快照相同"))
        if not actions:
            for path, original in plan["snapshot"].items():
                if path not in tree or original.get("sha256") != hashlib.sha256(tree[path]).hexdigest():
                    blockers.append(_issue("no-action-file-changed", path,
                                           "全 keep 计划没有 action，实际文件与原快照不符"))
        expected_assets = {path for path in before_paths if not _concept(path) and
                           PurePosixPath(path).name not in {"index.md", "log.md"}}
        asset_actions = {path: action_by_path[path] for path in expected_assets if path in action_by_path}
        for path in expected_assets:
            action = asset_actions.get(path)
            target = _target({"path": path}, action) if action else path
            if action and action.get("op") == "delete":
                if path in tree:
                    blockers.append(_issue("asset-not-deleted", path, "附件 delete 后仍存在"))
            elif target not in tree:
                blockers.append(_issue("asset-missing", path, f"附件丢失：{target}"))
            elif (not action or action.get("op") == "move") and plan["snapshot"][path].get("sha256") != hashlib.sha256(tree[target]).hexdigest():
                blockers.append(_issue("asset-changed", path, "附件内容与原计划 hash 不符"))
        for path in tree:
            if not _concept(path) and PurePosixPath(path).name not in {"index.md", "log.md"} and path not in expected_assets and path not in {_target({"path": p}, a) for p, a in asset_actions.items()}:
                blockers.append(_issue("unexpected-asset", path, "出现原计划未覆盖的附件"))
    metadata = {path: _read_metadata(path, tree, blockers) for path in final_concepts}
    for path, fields in metadata.items():
        status = fields.get("status", "stable")
        if status == "deprecated" and not _archive(path):
            blockers.append(_issue("deprecated-active", path, "deprecated 留在活动目录"))
        if _archive(path) and status != "deprecated":
            blockers.append(_issue("archive-not-deprecated", path, "archive concept 必须标记 deprecated"))
        source = final_by_source.get(path)
        if source and decision_by_path[source].get("lifecycle") == "historical" and status != "deprecated":
            blockers.append(_issue("history-status", path, "historical 必须标记 deprecated"))
        tags = fields.get("tags", [])
        lifecycle_metadata = fields.get("lifecycle")
        marked_archive = (isinstance(tags, list) and any(str(tag).casefold() == "archive" for tag in tags) or
                          isinstance(lifecycle_metadata, dict) and bool(lifecycle_metadata.get("archive")))
        if marked_archive and not _archive(path):
            review.append({"code": "archive-marker-active", "path": path,
                           "message": "页面含 archive 标记但位于活动目录；决策理由需解释"})
            if source and not decision_by_path[source].get("reason", "").strip():
                blockers.append(_issue("archive-marker-unexplained", path, "archive 标记缺少决策依据"))
    blockers.extend(_historical_navigation(root, tree, metadata))
    blockers.extend(_navigation_coverage(root, tree))
    structure_blockers, structure_review = _structure_and_references(root, tree)
    blockers.extend(structure_blockers)
    review.extend(structure_review)
    direct_counts = Counter(str(PurePosixPath(path).parent) for path in final_concepts)
    for rule in good_rules:
        budget = rule.get("max_direct_concepts")
        if budget is not None and direct_counts[rule["directory"]] > budget:
            blockers.append(_issue("directory-budget", rule["directory"],
                                   f"直属 concept {direct_counts[rule['directory']]} 超过声明预算 {budget}"))
    positive = any(isinstance(probe, dict) and probe.get("include") for probe in probes)
    if not positive:
        blockers.append(_issue("missing-current-probe", "", "至少声明一个正向当前检索"))
    historical_paths = {path for path in final_concepts if _archive(path) or metadata[path].get("status") == "deprecated"}
    if historical_paths and not any(isinstance(probe, dict) and
                                    isinstance(probe.get("history_include", []), list) and
                                    isinstance(probe.get("exclude", []), list) and
                                    any(path in historical_paths and path in probe.get("exclude", [])
                                        for path in probe.get("history_include", []))
                                    for probe in probes):
        blockers.append(_issue("missing-history-probe", "", "历史页须同时验证 history_include 与普通 exclude"))
    probe_results, probe_blockers = _probe_results(tree, probes, metadata)
    blockers.extend(probe_blockers)
    actions_by_op = dict(sorted(Counter(action.get("op", "invalid") for action in actions if isinstance(action, dict)).items()))
    before_directories = dict(sorted(Counter(str(PurePosixPath(path).parent) for path in original_concepts).items()))
    after_directories = dict(sorted(direct_counts.items()))
    roles = dict(sorted(Counter(d.get("role") for d in decisions if isinstance(d, dict) and isinstance(d.get("role"), str)).items()))
    return {"completion": "blocked" if blockers else "needs-review" if review else "complete",
            "blockers": blockers, "review": review, "actions_by_op": actions_by_op,
            "moved": actions_by_op.get("move", 0), "archived": actions_by_op.get("archive", 0),
            "roles": roles, "directories_before": before_directories, "directories_after": after_directories,
            "historical_count": len(historical_paths), "review_count": len(review), "probes": probe_results}

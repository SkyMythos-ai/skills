#!/usr/bin/env python3
"""只读盘点 OKF bundle，并为显式迁移提供可预测的引用重写。"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from bisect import bisect_right
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import yaml


MAX_FILES = 10000
ROOTS = ("business", "technical", "quality", "tasks", "_meta")
RESERVED = {"index.md": "index", "log.md": "log"}
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_LINK = re.compile(
    r"(?P<prefix>!?\[[^\]\n]*\]\()(?P<target><[^>\n]*>|[^\s)]+)"
    r"(?P<suffix>\s+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^()\n]*\)))?\)"
)
REFERENCE_LINK = re.compile(
    r"(?P<prefix>^\s{0,3}\[[^\]\n]+\]:\s*)(?P<target><[^>\n]*>|\S+)", re.MULTILINE
)
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
STATUS_SUFFIX = re.compile(r"(?:^|-)(?:final|latest|current|draft|deprecated)$", re.I)


def _diagnostic(code: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "path": path, "message": message}


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted((_json_value(item) for item in value), key=str)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def parse_document(text: str) -> tuple[dict[str, Any], str]:
    """输入完整 Markdown；返回原类型 YAML mapping 与正文，缺失/损坏 frontmatter 抛 ValueError。"""
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        raise ValueError("缺少或未闭合的 YAML frontmatter")
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"frontmatter YAML 无效：{exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter 必须是 YAML mapping")
    return metadata, text[match.end():]


def render_document(metadata: dict[str, Any], body: str) -> str:
    """输入 metadata 与正文，输出 YAML frontmatter 文档；未知字段由 PyYAML 语义往返保留。"""
    if not isinstance(metadata, dict):
        raise ValueError("metadata 必须是 mapping")
    try:
        raw = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
    except yaml.YAMLError as exc:
        raise ValueError(f"metadata 无法序列化：{exc}") from exc
    return f"---\n{raw}---\n{body}"


def _walk(directory: Path) -> Iterator[Path]:
    """显式遍历以使目录中途失效成为错误；符号链接永不进入盘点。"""
    try:
        with os.scandir(directory) as scan:
            entries = sorted(scan, key=lambda entry: entry.name)
    except OSError as exc:
        raise ValueError(f"扫描目录失败：{directory}：{exc}") from exc
    for entry in entries:
        try:
            if entry.name == ".git" or entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                yield from _walk(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path)
        except OSError as exc:
            raise ValueError(f"扫描条目失败：{entry.path}：{exc}") from exc


def _git_sets(root: Path, paths: list[str]) -> tuple[set[str], set[str]] | None:
    try:
        check = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, check=False
        )
        if check.returncode:
            return None
        tracked = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--", "."], cwd=root,
            capture_output=True, check=True,
        )
        ignored = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"], cwd=root,
            input=b"\0".join(os.fsencode(path) for path in paths) + b"\0",
            capture_output=True, check=False,
        )
        if ignored.returncode not in (0, 1):
            raise ValueError("git check-ignore 失败")
        return (
            set(os.fsdecode(path) for path in tracked.stdout.split(b"\0") if path),
            set(os.fsdecode(path) for path in ignored.stdout.split(b"\0") if path),
        )
    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Git 状态读取失败：{exc}") from exc


def _role(path: str, metadata: dict[str, Any]) -> tuple[str, str, str]:
    name = str(metadata.get("type", "")).lower()
    branch = path.split("/", 1)[0]
    if branch == "business":
        choices = (("requirement", "requirements"), ("domain", "domain"),
                   ("rule", "rules"), ("decision", "decisions"))
    elif branch == "technical":
        choices = (("decision", "adr"), ("adr", "adr"), ("contract", "contracts"),
                   ("standard", "standards"), ("research", "research"),
                   ("operation", "operations"), ("architecture", "architecture"))
    elif branch == "quality":
        choices = (("standard", "standards"), ("test case", "test-cases"),
                   ("verification", "verification"), ("incident", "incidents"))
    elif branch in ("tasks", "_meta"):
        return branch, branch, "分支约定路径；不因 type 自动移动"
    else:
        return "unknown", str(PurePosixPath(path).parent), "自定义分支，交由项目 taxonomy 判读"
    for token, subdir in choices:
        if token in name:
            return subdir, f"{branch}/{subdir}", f"type 包含 {token}；仅作候选分类"
    return "unknown", str(PurePosixPath(path).parent), "未知或通用 type，保留当前分类"


def _expiry(value: Any, now: datetime) -> bool:
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    elif isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(value, datetime):
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now


def _metadata_diagnostics(path: str, metadata: dict[str, Any], now: datetime) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(metadata.get("type"), str) or not metadata["type"].strip():
        diagnostics.append(_diagnostic("missing_type", "error", path, "concept 缺少非空 type"))
    if "sources" not in metadata:
        diagnostics.append(_diagnostic("missing_sources", "info", path, "缺少来源信息，请按角色复核"))
    if "verified" not in metadata:
        diagnostics.append(_diagnostic("missing_verified", "info", path, "缺少验证信息，请按证据范围复核"))
    if _expiry(metadata.get("stale_after"), now):
        diagnostics.append(_diagnostic("stale_after_due", "review", path, "stale_after 已到期，需复核有效性"))
    status = metadata.get("status")
    if "archive" in (part.casefold() for part in PurePosixPath(path).parts) and status != "deprecated":
        diagnostics.append(_diagnostic("archive_status_mismatch", "review", path, "归档路径中的页面状态不是 deprecated"))
    lifecycle = metadata.get("lifecycle")
    archived = lifecycle.get("archive") if isinstance(lifecycle, dict) else None
    archive_reason = archived.get("reason") if isinstance(archived, dict) else None
    if status == "deprecated" and not (archive_reason or any(
        metadata.get(field) for field in ("deprecated_reason", "reason", "superseded_by")
    )):
        diagnostics.append(_diagnostic("deprecated_context_missing", "review", path, "deprecated 缺少理由或后继关系，请复核正文"))
    return diagnostics


def _name_diagnostics(path: str) -> list[dict[str, str]]:
    name = PurePosixPath(path).name
    if name in RESERVED:
        return []
    result = []
    if not KEBAB.fullmatch(name):
        result.append(_diagnostic("name_not_kebab_case", "warning", path, "文件名不符合默认小写 kebab-case；项目例外可保留"))
    if STATUS_SUFFIX.search(name[:-3]):
        result.append(_diagnostic("status_name_review", "review", path, "文件名含状态尾缀，请复核其语义"))
    return result


def _resolve_target(source: str, target: str, root: Path) -> tuple[Path, bool] | None:
    bare = target[1:-1] if target.startswith("<") and target.endswith(">") else target
    parsed = urlsplit(bare)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    decoded = unquote(parsed.path)
    if decoded.startswith("/"):
        return root / decoded.lstrip("/"), True
    return root / PurePosixPath(source).parent / decoded, False


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _reference_target(source: str, target: str, root: Path, known_paths: set[str]) -> tuple[str, str] | None:
    resolved = _resolve_target(source, target, root)
    if resolved is None:
        return None
    absolute = Path(os.path.normpath(resolved[0]))
    if not _inside(absolute, root):
        return None
    rel = absolute.relative_to(root).as_posix()
    if rel in known_paths:
        return rel, "file"
    index = f"{rel.rstrip('/')}/index.md"
    if index in known_paths:
        return index, "directory"
    return rel, "missing"


def _visible_lines(text: str) -> Iterator[tuple[str, bool]]:
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        opening = FENCE.match(line)
        if fence:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= fence[1]:
                fence = None
            yield line, False
        elif opening:
            fence = (opening.group(1)[0], len(opening.group(1)))
            yield line, False
        else:
            yield line, True


def _active_lines(text: str) -> Iterator[tuple[str, str]]:
    """输入 Markdown；输出原行和等长可解析行，代码围栏与配对反引号跨度以空格遮蔽。"""
    lines = list(_visible_lines(text))
    visible = "".join(line if active else "".join(
        char if char in "\r\n" else " " for char in line
    ) for line, active in lines)
    runs = [match for match in re.finditer(r"`+", visible)
            if not _escaped_backtick(visible, match.start())]
    by_length: dict[int, list[int]] = {}
    for index, run in enumerate(runs):
        by_length.setdefault(len(run.group()), []).append(index)
    masked = list(visible)
    index = 0
    while index < len(runs):
        opening = runs[index]
        same_length = by_length[len(opening.group())]
        next_at = bisect_right(same_length, index)
        if next_at == len(same_length):
            # CommonMark 中没有同长度闭合符的反引号按字面量处理。
            index += 1
            continue
        closing_index = same_length[next_at]
        for position in range(opening.start(), runs[closing_index].end()):
            if masked[position] not in "\r\n":
                masked[position] = " "
        index = closing_index + 1
    masked_text = "".join(masked)
    offset = 0
    for original, _ in lines:
        yield original, masked_text[offset:offset + len(original)]
        offset += len(original)


def _escaped_backtick(text: str, at: int) -> bool:
    preceding = 0
    at -= 1
    while at >= 0 and text[at] == "\\":
        preceding += 1
        at -= 1
    return preceding % 2 == 1


def _markdown_targets(text: str) -> Iterator[str]:
    for _, active in _active_lines(text):
        for pattern in (INLINE_LINK, REFERENCE_LINK):
            for match in pattern.finditer(active):
                yield match.group("target")


def _unsupported_markdown_lines(text: str) -> Iterator[str]:
    """识别当前重写器无法安全定位目标的 inline 链接，避免迁移时静默漏改。"""
    for line, active in _active_lines(text):
        matched = {match.start("target") - 2 for match in INLINE_LINK.finditer(active)
                   if "(" not in match.group("target") and "\\" not in match.group("target")}
        for candidate in re.finditer(r"\]\(", active):
            if candidate.start() not in matched and (candidate.start() == 0 or active[candidate.start() - 1] != "\\"):
                yield line.strip()
                break


def _metadata_targets(metadata: dict[str, Any]) -> Iterator[tuple[str, str]]:
    sources = metadata.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and isinstance(source.get("resource"), str):
                yield "source", source["resource"]
    links = metadata.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, str):
                yield "links", link
    successor = metadata.get("superseded_by")
    if isinstance(successor, str):
        yield "superseded_by", successor


def _concept_ref(value: str, known_paths: set[str]) -> tuple[str | None, bool]:
    if urlsplit(value).scheme or value.startswith("#"):
        return None, False
    candidate = value.removeprefix("/") if hasattr(str, "removeprefix") else value.lstrip("/")
    if "/" in candidate:
        path = candidate if candidate.endswith(".md") else candidate + ".md"
        return (path, False) if path in known_paths else (None, False)
    stem = candidate[:-3] if candidate.endswith(".md") else candidate
    matches = [path for path in known_paths if path.endswith(".md") and PurePosixPath(path).stem == stem]
    return (matches[0], False) if len(matches) == 1 else (None, len(matches) > 1)


def _resolved_concept_ref(value: str, source: str, root: Path,
                          known_paths: set[str]) -> tuple[str | None, bool]:
    # links 与 superseded_by 的 root/./../ 写法是路径；其余无斜杠写法是唯一 basename。
    if value.startswith(("/", "./", "../")):
        resolved = _resolve_target(source, value, root)
        if resolved is None:
            return None, False
        absolute = Path(os.path.normpath(resolved[0]))
        if not _inside(absolute, root):
            return None, False
        relative = absolute.relative_to(root).as_posix()
        candidate = relative if relative.endswith(".md") else relative + ".md"
        return (candidate, False) if candidate in known_paths else (None, False)
    return _concept_ref(value, known_paths)


def reference_diagnostics(root: Path, texts: dict[str, str], known_paths: set[str]) -> list[dict[str, str]]:
    """输入相对路径文本快照；返回本地断链、歧义及 superseded_by 缺目标/环诊断。"""
    root = root.resolve()
    diagnostics: list[dict[str, str]] = []
    successors: dict[str, str] = {}
    for path, text in sorted(texts.items()):
        try:
            metadata, body = parse_document(text)
        except ValueError:
            metadata, body = {}, text
        for line in _unsupported_markdown_lines(body):
            diagnostics.append(_diagnostic("unsupported_markdown_link", "review", path,
                                           f"无法安全解析 Markdown 链接：{line[:120]}"))
        for target in _markdown_targets(body):
            result = _reference_target(path, target, root, known_paths)
            if result and result[1] == "missing":
                diagnostics.append(_diagnostic("broken_markdown_link", "warning", path, f"本地链接缺失：{target}"))
        for kind, target in _metadata_targets(metadata):
            if kind == "source":
                resolved = _resolve_target(path, target, root)
                if resolved is None:
                    continue
                absolute = Path(os.path.normpath(resolved[0]))
                relative = absolute.relative_to(root).as_posix() if _inside(absolute, root) else None
                suffix = PurePosixPath(unquote(urlsplit(target).path)).suffix.lower()
                file_suffixes = {".md", ".yaml", ".yml", ".json", ".tsv", ".csv",
                                 ".txt", ".png", ".jpg", ".jpeg", ".svg", ".pdf"}
                if suffix in file_suffixes and relative not in known_paths and not absolute.is_file():
                    diagnostics.append(_diagnostic("broken_source_path", "warning", path,
                                                   f"本地来源文件缺失：{target}"))
                continue
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            resolved, ambiguous = _resolved_concept_ref(target, path, root, known_paths)
            if ambiguous:
                diagnostics.append(_diagnostic("ambiguous_concept_link", "review", path, f"概念 basename 不唯一：{target}"))
            elif resolved is None:
                code = "missing_successor" if kind == "superseded_by" else "missing_concept_link"
                diagnostics.append(_diagnostic(code, "warning", path, f"概念目标缺失：{target}"))
            elif kind == "superseded_by":
                successors[path] = resolved
    visited: set[str] = set()
    for start in successors:
        if start in visited:
            continue
        chain: dict[str, int] = {}
        current = start
        while current in successors and current not in visited:
            if current in chain:
                cycle = list(chain)[chain[current]:]
                for path in cycle:
                    diagnostics.append(_diagnostic("superseded_cycle", "error", path, "superseded_by 替代链形成环"))
                break
            chain[current] = len(chain)
            current = successors[current]
        visited.update(chain)
    return diagnostics


def scan_bundle(root: Path, now: datetime | None = None) -> dict[str, Any]:
    """输入 bundle 根目录；返回 JSON 友好盘点，读取故障抛 ValueError 且不产生部分结果。"""
    root = root.expanduser().resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    diagnostics: list[dict[str, str]] = []
    files: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    classifications: list[dict[str, str]] = []
    references: list[dict[str, str]] = []
    counts: dict[str, Any] = {"total": 0, "concept": 0, "index": 0, "log": 0, "asset": 0,
                              "tracked": 0, "ignored": 0, "untracked": 0, "unknown": 0}
    if not root.is_dir():
        diagnostics.append(_diagnostic("missing_root", "error", "", "bundle 根目录不存在"))
        return {"root": str(root), "files": files, "diagnostics": diagnostics, "counts": counts,
                "classifications": classifications, "references": references}
    paths = list(_walk(root))
    if len(paths) > MAX_FILES:
        raise ValueError(f"bundle 文件数超过上限 {MAX_FILES}")
    relatives = [path.relative_to(root).as_posix() for path in paths]
    git_sets = _git_sets(root, relatives)
    known_paths = set(relatives)
    if "index.md" not in known_paths:
        diagnostics.append(_diagnostic("missing_root_index", "error", "index.md", "bundle 根 index.md 缺失"))
    for path, relative in zip(paths, relatives):
        kind = RESERVED.get(path.name, "concept" if path.suffix.lower() == ".md" else "asset")
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8") if kind != "asset" else None
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"读取文件失败：{relative}：{exc}") from exc
        if git_sets is None:
            git_status = "unknown"
        elif relative in git_sets[0]:
            git_status = "tracked"
        elif relative in git_sets[1]:
            git_status = "ignored"
        else:
            git_status = "untracked"
        metadata: dict[str, Any] = {}
        if kind == "concept":
            try:
                metadata, _ = parse_document(text or "")
            except ValueError as exc:
                diagnostics.append(_diagnostic("invalid_frontmatter", "error", relative, str(exc)))
            diagnostics.extend(_metadata_diagnostics(relative, metadata, now))
            diagnostics.extend(_name_diagnostics(relative))
            role, suggested_directory, reason = _role(relative, metadata)
            classifications.append({"path": relative, "role": role,
                                    "suggested_directory": suggested_directory, "reason": reason})
        elif kind == "index" and text is not None and text.startswith("---"):
            try:
                metadata, _ = parse_document(text)
            except ValueError as exc:
                diagnostics.append(_diagnostic("invalid_frontmatter", "error", relative, str(exc)))
        files[relative] = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw),
                           "kind": kind, "git_status": git_status, "metadata": _json_value(metadata)}
        counts["total"] += 1
        counts[kind] += 1
        counts[git_status] += 1
        if text is not None:
            texts[relative] = text
    for relative, text in texts.items():
        try:
            metadata, body = parse_document(text)
        except ValueError:
            metadata, body = {}, text
        # 引用诊断负责报告无法安全重写的语法，盘点仍保留原文 hash。
        for target in _markdown_targets(body):
            resolved = _reference_target(relative, target, root, known_paths)
            if resolved:
                references.append({"path": relative, "field": "markdown", "target": target,
                                   "resolved": resolved[0]})
        for kind, target in _metadata_targets(metadata):
            reference = {"path": relative, "field": kind, "target": target}
            if kind == "source":
                source_target = _resolve_target(relative, target, root)
                if source_target is not None:
                    absolute = Path(os.path.normpath(source_target[0]))
                    if absolute.is_file():
                        reference["resolved"] = (absolute.relative_to(root).as_posix()
                                                 if _inside(absolute, root) else str(absolute))
            else:
                target_path, ambiguous = _resolved_concept_ref(target, relative, root, known_paths)
                if target_path and not ambiguous:
                    reference["resolved"] = target_path
            references.append(reference)
    diagnostics.extend(reference_diagnostics(root, texts, known_paths))
    return {"root": str(root), "files": files, "diagnostics": diagnostics, "counts": counts,
            "classifications": classifications, "references": references}


def _rebased_target(target: str, source: str, destination: str, mapping: dict[str, str],
                    root: Path, known_paths: set[str], *, source_field: bool = False) -> str:
    bracketed = target.startswith("<") and target.endswith(">")
    bare = target[1:-1] if bracketed else target
    parsed = urlsplit(bare)
    resolved = _resolve_target(source, target, root)
    if resolved is None:
        return target
    absolute = Path(os.path.normpath(resolved[0]))
    inside = _inside(absolute, root)
    original_rel = absolute.relative_to(root).as_posix() if inside else None
    if source_field and not (absolute.is_file() or original_rel in known_paths):
        return target
    if original_rel in mapping:
        absolute = root / mapping[original_rel]
    elif original_rel and original_rel + ".md" in mapping:
        absolute = root / mapping[original_rel + ".md"][:-3]
    elif original_rel and original_rel.rstrip("/") + "/index.md" in mapping:
        absolute = root / PurePosixPath(mapping[original_rel.rstrip("/") + "/index.md"]).parent
    if resolved[1]:
        if not _inside(absolute, root):
            return target
        new_path = "/" + absolute.relative_to(root).as_posix()
    else:
        new_path = os.path.relpath(absolute, root / PurePosixPath(destination).parent).replace(os.sep, "/")
        if parsed.path.endswith("/") and not new_path.endswith("/"):
            new_path += "/"
    encoded = quote(new_path, safe="/%:@+~!$&'*,;=-._") if "%" in parsed.path else new_path
    rebuilt = urlunsplit(("", "", encoded, parsed.query, parsed.fragment))
    return f"<{rebuilt}>" if bracketed else rebuilt


def rewrite_document(text: str, source_path: str, destination_path: str,
                     mapping: dict[str, str], root: Path, known_paths: set[str]) -> str:
    """输入迁移前文档及路径映射；输出重定向后的文档文本，不写磁盘。"""
    root = root.resolve()
    for path in (source_path, destination_path, *mapping.keys(), *mapping.values()):
        if path.startswith("/") or ".." in PurePosixPath(path).parts:
            raise ValueError(f"路径必须是 bundle 相对路径：{path}")
    try:
        metadata, body = parse_document(text)
        frontmatter = True
    except ValueError:
        if text.startswith("---"):
            raise
        metadata, body, frontmatter = {}, text, False
    original_metadata = deepcopy(metadata)
    original_body = body
    unsupported = next(_unsupported_markdown_lines(body), None)
    if unsupported is not None:
        raise ValueError(f"无法安全重写 Markdown 链接：{unsupported[:120]}")

    rewritten = []
    for line, active in _active_lines(body):
        matches = [*REFERENCE_LINK.finditer(active), *INLINE_LINK.finditer(active)]
        for match in sorted(matches, key=lambda item: item.start("target"), reverse=True):
            start, end = match.span("target")
            replacement = _rebased_target(line[start:end], source_path, destination_path,
                                          mapping, root, known_paths)
            line = line[:start] + replacement + line[end:]
        rewritten.append(line)
    if frontmatter:
        sources = metadata.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if isinstance(source, dict) and isinstance(source.get("resource"), str):
                    source["resource"] = _rebased_target(
                        source["resource"], source_path, destination_path, mapping,
                        root, known_paths, source_field=True,
                    )
        links = metadata.get("links")
        if isinstance(links, list):
            for index, link in enumerate(links):
                if not isinstance(link, str):
                    continue
                resolved, ambiguous = _resolved_concept_ref(link, source_path, root, known_paths)
                if ambiguous:
                    raise ValueError(f"links 概念 basename 不唯一：{link}")
                if link.startswith(("/", "./", "../")):
                    links[index] = _rebased_target(link, source_path, destination_path,
                                                   mapping, root, known_paths)
                elif resolved in mapping:
                    target = mapping[resolved]
                    links[index] = target if link.endswith(".md") else target[:-3]
        successor = metadata.get("superseded_by")
        if isinstance(successor, str):
            resolved, ambiguous = _resolved_concept_ref(successor, source_path, root, known_paths)
            if ambiguous:
                raise ValueError(f"superseded_by 概念 basename 不唯一：{successor}")
            if successor.startswith(("/", "./", "../")):
                metadata["superseded_by"] = _rebased_target(
                    successor, source_path, destination_path, mapping, root, known_paths
                )
            elif resolved in mapping:
                target = mapping[resolved]
                metadata["superseded_by"] = target if successor.endswith(".md") else target[:-3]
        new_body = "".join(rewritten)
        if metadata == original_metadata and new_body == original_body:
            return text
        frontmatter_text = render_document(metadata, "")
        if text.startswith("---\r\n"):
            frontmatter_text = frontmatter_text.replace("\n", "\r\n")
        return frontmatter_text + new_body
    new_body = "".join(rewritten)
    return text if new_body == original_body else new_body

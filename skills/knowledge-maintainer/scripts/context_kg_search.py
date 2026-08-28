#!/usr/bin/env python3
"""Stateless, progressively disclosed search for an OKF context-kg bundle."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the host environment
    yaml = None


RESERVED_FILES = {"index.md", "log.md"}
SESSION_SUMMARIES = PurePosixPath("tasks/session-summaries")
FIELD_WEIGHTS = {
    "path": 70,
    "filename": 80,
    "title": 100,
    "description": 45,
    "tags": 55,
    "type": 35,
    "body": 10,
}
EXACT_FIELD_BONUS = {
    "path": 2000,
    "filename": 2000,
    "title": 2000,
    "tags": 800,
    "description": 600,
    "type": 400,
    "body": 0,
}


@dataclass(frozen=True)
class SearchResult:
    path: str
    score: int
    matched_fields: tuple[str, ...]
    status: str
    freshness: str
    score_reason: str


@dataclass(frozen=True)
class Document:
    path: Path
    relative_path: str
    metadata: dict[str, Any]


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return "", text[4:]
    return text[4:end], text[end + 5 :]


def _load_document(path: Path, root: Path) -> Document | None:
    try:
        with path.open(encoding="utf-8") as stream:
            if stream.readline() != "---\n":
                raw = None
            else:
                frontmatter_lines: list[str] = []
                for line in stream:
                    if line == "---\n":
                        break
                    frontmatter_lines.append(line)
                else:
                    frontmatter_lines = []
                raw = "".join(frontmatter_lines)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"警告：跳过无法读取的文件 {path}：{exc}", file=sys.stderr)
        return None
    metadata: dict[str, Any] = {}
    if raw not in (None, "") and yaml is not None:
        try:
            loaded = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            print(f"警告：跳过 frontmatter 无法解析的文件 {path}：{exc}", file=sys.stderr)
            return None
        if isinstance(loaded, dict):
            metadata = loaded
    return Document(path, path.relative_to(root).as_posix(), metadata)


def _load_body(document: Document) -> str:
    try:
        text = document.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"警告：无法读取正文 {document.path}：{exc}", file=sys.stderr)
        return ""
    return split_frontmatter(text)[1]


def _normalise(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return str(value or "").casefold()


def _terms(query: str) -> tuple[str, ...]:
    # Whitespace gives predictable multi-term AND matching and leaves Chinese
    # phrases intact so callers are not dependent on a tokenizer.
    return tuple(part.casefold() for part in re.findall(r"\S+", query.strip()))


def _field_terms(value: Any, terms: tuple[str, ...]) -> tuple[str, ...]:
    normalised = _normalise(value)
    return tuple(term for term in terms if term in normalised)


def _score_fields(
    fields: Iterable[tuple[str, Any]], terms: tuple[str, ...], query: str
) -> tuple[int, tuple[str, ...], str]:
    field_values = tuple(fields)
    matches = [
        (name, _field_terms(value, terms))
        for name, value in field_values
    ]
    matches = [(name, field_terms) for name, field_terms in matches if field_terms]
    covered = {term for _, field_terms in matches for term in field_terms}
    if covered != set(terms):
        return 0, (), ""
    matched = tuple(name for name, _ in matches)
    score = sum(FIELD_WEIGHTS[name] * len(field_terms) for name, field_terms in matches)
    reasons = [
        f"{name}({FIELD_WEIGHTS[name]}x{len(field_terms)})"
        for name, field_terms in matches
    ]
    normalised_query = query.strip().casefold()
    exact_fields = [
        name
        for name, value in field_values
        if _normalise(value).strip() == normalised_query
    ]
    if exact_fields:
        exact_bonus = max(EXACT_FIELD_BONUS[name] for name in exact_fields)
        score += exact_bonus
        reasons.append(f"exact({exact_bonus}:{','.join(exact_fields)})")
    reason = " + ".join(reasons)
    return score, matched, reason


def _metadata_fields(document: Document) -> tuple[tuple[str, Any], ...]:
    return (
        ("path", document.relative_path),
        ("filename", document.path.stem),
        ("title", document.metadata.get("title")),
        ("description", document.metadata.get("description")),
        ("tags", document.metadata.get("tags")),
        ("type", document.metadata.get("type")),
    )


def _status(metadata: dict[str, Any]) -> str:
    value = _normalise(metadata.get("status", "stable"))
    return value or "stable"


def _freshness(metadata: dict[str, Any], now: datetime) -> str:
    raw = metadata.get("stale_after")
    if raw is None:
        return "未声明 stale_after"
    if isinstance(raw, datetime):
        deadline = raw
    else:
        try:
            deadline = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return f"stale_after 无法解析：{raw}"
    if deadline.tzinfo is None:
        return f"stale_after 无时区：{raw}"
    return "已过 stale_after" if deadline < now else f"有效至 {deadline.isoformat()}"


def _clean_scope(scope: str | None) -> str | None:
    if not scope:
        return None
    clean = scope.strip().strip("/")
    return clean or None


def _under_scope(relative_path: str, scope: str | None) -> bool:
    if not scope:
        return True
    path = PurePosixPath(relative_path)
    target = PurePosixPath(scope)
    return path == target or target in path.parents


def _is_session_summary(relative_path: str) -> bool:
    return SESSION_SUMMARIES in PurePosixPath(relative_path).parents


def search(
    context_kg: Path,
    query: str,
    *,
    type_filter: str | None = None,
    status_filter: str | None = None,
    scope: str | None = None,
    limit: int = 10,
    history: bool = False,
    include_body: bool = False,
    now: datetime | None = None,
) -> list[SearchResult]:
    """Search without writing an index or cache.

    Metadata is the first-stage candidate set. Body reads become visible only
    when that stage is empty, unless ``include_body`` explicitly enables them.
    """
    if not context_kg.is_dir():
        raise ValueError(f"context-kg 不存在或不是目录：{context_kg}")
    if yaml is None:
        raise ValueError("PyYAML 未安装，无法检索 concept frontmatter")
    terms = _terms(query)
    if not terms:
        raise ValueError("query 不能为空")
    if limit <= 0:
        raise ValueError("limit 必须大于 0")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    documents: list[Document] = []
    clean_scope = _clean_scope(scope)
    for path in sorted(context_kg.rglob("*.md")):
        if path.name in RESERVED_FILES:
            continue
        relative_path = path.relative_to(context_kg).as_posix()
        if not history and _is_session_summary(relative_path):
            continue
        document = _load_document(path, context_kg)
        if document is None:
            continue
        status = _status(document.metadata)
        if (
            status == "deprecated"
            and not history
            and _normalise(status_filter) != "deprecated"
        ):
            continue
        if type_filter and _normalise(document.metadata.get("type")) != type_filter.casefold():
            continue
        if status_filter and status != status_filter.casefold():
            continue
        if not _under_scope(relative_path, clean_scope):
            continue
        documents.append(document)

    metadata_hits: dict[str, tuple[int, tuple[str, ...], str]] = {}
    for document in documents:
        metadata_hits[document.relative_path] = _score_fields(
            _metadata_fields(document), terms, query
        )

    has_metadata_candidates = any(score for score, _, _ in metadata_hits.values())
    use_body = include_body or (not has_metadata_candidates and bool(clean_scope))
    results: list[SearchResult] = []
    for document in documents:
        score, matched, reason = metadata_hits[document.relative_path]
        if use_body:
            score, matched, reason = _score_fields(
                (*_metadata_fields(document), ("body", _load_body(document))),
                terms,
                query,
            )
        if not score:
            continue
        status = _status(document.metadata)
        results.append(
            SearchResult(
                path=document.relative_path,
                score=score,
                matched_fields=matched,
                status=status,
                freshness=_freshness(document.metadata, current_time),
                score_reason=reason,
            )
        )
    results.sort(key=lambda item: (-item.score, item.path))
    return results[:limit]


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _session_time(document: Document) -> datetime | None:
    generated = document.metadata.get("generated")
    if isinstance(generated, dict) and "at" in generated:
        if parsed := _timestamp(generated["at"]):
            return parsed
    match = re.match(r"(\d{4}-\d{2}-\d{2})", document.path.name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)


def latest_session(context_kg: Path, *, history: bool = False) -> SearchResult | None:
    """Return the newest Session Summary without reading its body."""
    if not context_kg.is_dir():
        raise ValueError(f"context-kg 不存在或不是目录：{context_kg}")
    if yaml is None:
        raise ValueError("PyYAML 未安装，无法检索 concept frontmatter")
    root = context_kg / SESSION_SUMMARIES
    if not root.is_dir():
        return None
    candidates: list[tuple[datetime, Document]] = []
    for path in sorted(root.rglob("*.md")):
        if path.name in RESERVED_FILES:
            continue
        document = _load_document(path, context_kg)
        if document is None:
            continue
        if _normalise(document.metadata.get("type")) != "session summary":
            continue
        if _status(document.metadata) == "deprecated" and not history:
            continue
        if session_time := _session_time(document):
            candidates.append((session_time, document))
    if not candidates:
        return None
    session_time, document = max(candidates, key=lambda item: (item[0], item[1].relative_path))
    return SearchResult(
        path=document.relative_path,
        score=0,
        matched_fields=("generated.at",),
        status=_status(document.metadata),
        freshness=_freshness(document.metadata, datetime.now(timezone.utc)),
        score_reason=f"latest-session({session_time.isoformat()})",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="无状态搜索 context-kg；默认元数据优先且排除历史内容。"
    )
    parser.add_argument("context_kg", type=Path, help="context-kg 根目录")
    parser.add_argument("query", nargs="?", help="搜索词；空格分隔的词采用 AND 匹配")
    parser.add_argument("--type", dest="type_filter", help="按 type 精确过滤（允许未知类型）")
    parser.add_argument(
        "--status", dest="status_filter", choices=("draft", "stable", "deprecated")
    )
    parser.add_argument("--scope", help="限制到 bundle 相对路径或目录")
    parser.add_argument("--limit", type=int, default=10, help="最多输出的候选数（默认 10）")
    parser.add_argument(
        "--history",
        action="store_true",
        help="纳入 deprecated 与 tasks/session-summaries/",
    )
    parser.add_argument(
        "--body", dest="include_body", action="store_true", help="显式同时搜索正文"
    )
    parser.add_argument(
        "--latest-session",
        action="store_true",
        help="不需要 query，返回 generated.at 最新的 Session Summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.latest_session:
            if args.query:
                raise ValueError("--latest-session 不接受 query")
            latest = latest_session(args.context_kg, history=args.history)
            results = [latest] if latest is not None else []
        else:
            results = search(
                args.context_kg,
                args.query or "",
                type_filter=args.type_filter,
                status_filter=args.status_filter,
                scope=args.scope,
                limit=args.limit,
                history=args.history,
                include_body=args.include_body,
            )
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    if not results:
        if args.latest_session:
            print("未找到 Session Summary。")
        elif not _clean_scope(args.scope) and not args.include_body:
            print("未找到元数据候选；请用 --scope 限定正文回退范围，或显式使用 --body。")
        else:
            print("未找到候选知识。")
        return 0
    for result in results:
        print(result.path)
        print(f"  命中字段：{', '.join(result.matched_fields)}")
        print(f"  状态/时效：{result.status}；{result.freshness}")
        print(f"  score={result.score}：{result.score_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

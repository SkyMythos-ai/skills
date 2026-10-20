"""共享 Context-KG 历史内容隔离规则。"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


SESSION_SUMMARIES = PurePosixPath("tasks/session-summaries")


def is_archive_path(relative_path: str) -> bool:
    """仅当 bundle 相对路径包含完整的 archive segment 时返回 True。"""
    return any(part.casefold() == "archive" for part in PurePosixPath(relative_path).parts)


def is_session_summary(relative_path: str, metadata: dict[str, Any] | None = None) -> bool:
    """识别约定目录及显式 Session Summary 类型。"""
    path = PurePosixPath(relative_path)
    if SESSION_SUMMARIES in path.parents:
        return True
    return str((metadata or {}).get("type", "")).casefold() == "session summary"


def history_allowed(
    relative_path: str,
    metadata: dict[str, Any],
    *,
    history: bool,
    status_filter: str | None = None,
) -> bool:
    """判断历史内容能否进入本次搜索；显式 deprecated 不绕过 archive。"""
    if history:
        return True
    if is_archive_path(relative_path) or is_session_summary(relative_path, metadata):
        return False
    status = str(metadata.get("status") or "stable").casefold()
    return status != "deprecated" or (status_filter or "").casefold() == "deprecated"

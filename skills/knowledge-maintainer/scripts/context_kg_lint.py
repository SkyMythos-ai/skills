#!/usr/bin/env python3
"""Validate an OKF v0.2 context-kg bundle with maintainer warnings."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the host environment
    yaml = None


VALID_STATUS = {"draft", "stable", "deprecated"}
DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
INDEX_ENTRY = re.compile(r"^\s*[*+-]\s+\[[^\]]+\]\(([^)]+)\)(.*)$", re.MULTILINE)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return "", text[4:]
    return text[4:end], text[end + 5 :]


def load_frontmatter(raw: str, path: Path, errors: list[str]) -> dict[str, Any]:
    if yaml is None:
        errors.append(f"{path}: PyYAML 未安装，无法验证 YAML 可解析性")
        return {}
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        errors.append(f"{path}: frontmatter 不是可解析的 YAML：{exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path}: frontmatter 必须是 YAML mapping")
        return {}
    return data


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_timestamp(value: Any) -> bool:
    if isinstance(value, datetime):
        return value.tzinfo is not None and value.utcoffset() is not None
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_actor_event(
    value: Any, field: str, path: Path, errors: list[str], *, allow_list: bool
) -> None:
    events = value if allow_list and isinstance(value, list) else [value]
    if allow_list and not isinstance(value, (dict, list)):
        errors.append(f"{path}: {field} 必须是 mapping 或 mapping 列表")
        return
    for event in events:
        if not isinstance(event, dict):
            errors.append(f"{path}: {field} 的每项必须是 mapping")
            continue
        missing = []
        if not nonempty_string(event.get("by")):
            missing.append("by")
        if field == "verified" and "at" not in event:
            missing.append("at")
        if missing:
            errors.append(f"{path}: {field} 缺少非空字段：{', '.join(missing)}")
        if "at" in event and not valid_timestamp(event["at"]):
            errors.append(f"{path}: {field}.at 必须是带 UTC offset 的 ISO 8601 datetime")


def validate_concept(path: Path, text: str, errors: list[str]) -> None:
    raw, _ = split_frontmatter(text)
    if raw is None:
        errors.append(f"{path}: concept 缺少 YAML frontmatter")
        return
    if raw == "":
        errors.append(f"{path}: frontmatter 未闭合")
        return

    fields = load_frontmatter(raw, path, errors)
    if not nonempty_string(fields.get("type")):
        errors.append(f"{path}: 缺少非空 type")

    status = fields.get("status")
    if status is not None and status not in VALID_STATUS:
        errors.append(f"{path}: status 必须是 draft、stable 或 deprecated")

    sources = fields.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            errors.append(f"{path}: sources 必须是来源 mapping 列表")
        else:
            for source in sources:
                if not isinstance(source, dict) or not nonempty_string(source.get("resource")):
                    errors.append(f"{path}: sources 的每项必须包含非空 resource")

    if "generated" in fields:
        validate_actor_event(fields["generated"], "generated", path, errors, allow_list=False)
    if "verified" in fields:
        validate_actor_event(fields["verified"], "verified", path, errors, allow_list=True)
    if "stale_after" in fields and not valid_timestamp(fields["stale_after"]):
        errors.append(f"{path}: stale_after 必须是带 UTC offset 的 ISO 8601 datetime")
    if fields.get("type") == "Attested Computation" and not nonempty_string(
        fields.get("runtime")
    ):
        errors.append(f"{path}: Attested Computation 缺少非空 runtime")


def validate_index(path: Path, root: Path, text: str, errors: list[str]) -> str:
    raw, body = split_frontmatter(text)
    if raw is None:
        body = text
    elif raw == "":
        errors.append(f"{path}: frontmatter 未闭合")
    elif path != root / "index.md":
        errors.append(f"{path}: 只有 bundle 根 index.md 可以包含 frontmatter")
    else:
        fields = load_frontmatter(raw, path, errors)
        if set(fields) - {"okf_version"}:
            errors.append(f"{path}: 根 index.md frontmatter 仅允许 okf_version")
        if "okf_version" in fields and str(fields["okf_version"]) != "0.2":
            errors.append(f"{path}: okf_version 必须为 \"0.2\"")
    if not re.search(r"^#{1,6}\s+\S", body, flags=re.MULTILINE):
        errors.append(f"{path}: index.md 必须包含 section heading")
    if not INDEX_ENTRY.search(body):
        errors.append(f"{path}: index.md 必须包含 Markdown 列表链接条目")
    return body


def validate_log(path: Path, text: str, errors: list[str], warnings: list[str]) -> None:
    raw, body = split_frontmatter(text)
    if raw is not None:
        if raw == "":
            errors.append(f"{path}: frontmatter 未闭合")
        else:
            warnings.append(f"{path}: context-kg 生产者约定不在 log.md 中使用 frontmatter")
    h2_values = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)
    if any(not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in h2_values):
        errors.append(f"{path}: log.md 的二级标题必须是 YYYY-MM-DD")
    dates = DATE_HEADING.findall(body)
    if not dates:
        errors.append(f"{path}: log.md 必须包含至少一个 YYYY-MM-DD 日期分组")
    for value in dates:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            errors.append(f"{path}: log.md 包含无效日期：{value}")
    if dates != sorted(dates, reverse=True):
        errors.append(f"{path}: log.md 日期必须按最新在前排列")


def link_target(path: Path, root: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    decoded = unquote(parsed.path)
    return root / decoded.lstrip("/") if decoded.startswith("/") else path.parent / decoded


def direct_knowledge_items(directory: Path) -> list[Path]:
    concepts = [path for path in directory.glob("*.md") if path.name not in {"index.md", "log.md"}]
    subdirectories = [
        path for path in directory.iterdir() if path.is_dir() and any(path.rglob("*.md"))
    ]
    return sorted(concepts + subdirectories)


def validate_index_profile(
    directory: Path, root: Path, body: str, warnings: list[str]
) -> None:
    referenced = {
        target.resolve()
        for raw_target, _ in INDEX_ENTRY.findall(body)
        if (target := link_target(directory / "index.md", root, raw_target)) is not None
    }
    for item in direct_knowledge_items(directory):
        if item.resolve() not in referenced:
            warnings.append(f"{directory / 'index.md'}: 未列出直属项 {item.name}")
    for raw_target, suffix in INDEX_ENTRY.findall(body):
        if not re.match(r"^\s+-\s+\S", suffix):
            warnings.append(
                f"{directory / 'index.md'}: 索引条目缺少短描述：{raw_target}"
            )


def lint(context_kg: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    if not context_kg.is_dir():
        print(f"lint 结果：\n✗ context-kg 不存在：{context_kg}")
        return 2

    md_files = sorted(context_kg.rglob("*.md"))
    concept_count = 0
    index_count = 0
    index_bodies: dict[Path, str] = {}
    for path in md_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{path}: 文件必须使用 UTF-8 编码")
            continue
        body = text
        if path.name == "index.md":
            index_count += 1
            body = validate_index(path, context_kg, text, errors)
            index_bodies[path.parent] = body
        elif path.name == "log.md":
            validate_log(path, text, errors, warnings)
        else:
            concept_count += 1
            validate_concept(path, text, errors)

        for raw_target in MARKDOWN_LINK.findall(body):
            target = link_target(path, context_kg, raw_target)
            if target is not None and not target.exists():
                warnings.append(f"{path}: 断开的 Markdown 链接：{raw_target}")

    for directory in [context_kg, *sorted(path for path in context_kg.rglob("*") if path.is_dir())]:
        items = direct_knowledge_items(directory)
        index_path = directory / "index.md"
        should_have_index = directory == context_kg or len(items) >= 2
        if should_have_index and directory not in index_bodies:
            warnings.append(f"{index_path}: 缺失；导航将退化为当前层动态合成")
        elif directory in index_bodies:
            validate_index_profile(directory, context_kg, index_bodies[directory], warnings)

    docs_design = context_kg.parent / "docs" / "design"
    if docs_design.is_dir() and any(docs_design.rglob("*.md")):
        warnings.append("docs/design 中存在 Markdown；长期设计知识应评估迁入 context-kg")

    print("lint 结果：")
    print(f"✓ concept：{concept_count}")
    print(f"✓ index：{index_count}")
    for warning in warnings:
        print(f"⚠ {warning}")
    for error in errors:
        print(f"✗ {error}")
    if errors:
        return 1
    print("✓ OKF v0.2 基础结构检查通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint an OKF v0.2 context-kg bundle.")
    parser.add_argument("context_kg", nargs="?", default="context-kg", help="context-kg 路径")
    args = parser.parse_args()
    return lint(Path(args.context_kg).resolve())


if __name__ == "__main__":
    sys.exit(main())

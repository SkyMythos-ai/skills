#!/usr/bin/env python3
"""仓库级静态校验：Skill 元数据、相对链接与示例标记。

只用 Python 3 标准库，不依赖 PyYAML，不执行仓库中的示例代码。当前检查项：

1. `skills/<name>/SKILL.md` 的 frontmatter 可解析，`name` 与目录名一致，并含 `description`。
2. 全仓库 Markdown 相对链接可解析；bundle 根链接（`/xxx`）按 `context-kg/` 解析。
3. `example:` 标记必须成对（`<id>-bad` / `<id>-good`）且 ID 全仓库唯一。
4. `gate-example:` 标记 ID 唯一；成对写法的 `-bad`/`-good` 必须配对。片段类标记
   只要求唯一，并在汇总里单独计数，不当成已校验的断言。

围栏代码块与行内代码中的链接/标记不作为真实结构扫描，避免把示例本身当成链接。

退出码：0 全部通过；1 存在错误；2 仓库根目录不可用。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_UNUSABLE = 2

EXAMPLE = re.compile(r"<!--\s*example:\s*([A-Za-z0-9._-]+)\s*-->")
GATE_EXAMPLE = re.compile(r"<!--\s*gate-example:\s*([A-Za-z0-9._-]+)\s*-->")
GATE_FRAGMENT = re.compile(r"<!--\s*gate-fragment:\s*([A-Za-z0-9._-]+)\s*-->")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
EXPLICIT_ANCHOR = re.compile(r"<a\s+id=\"([^\"]+)\"")
EXTERNAL_SCHEME = ("http://", "https://", "mailto:", "tel:", "ftp://")

EXAMPLE_KINDS = {"bad", "good"}


def split_fences(text: str) -> tuple[str, list[str]]:
    """返回（去掉围栏代码块的正文，围栏代码块内容列表）。

    标记与链接只在正文中扫描，避免把示例里的链接或标题当成真实结构。
    """
    prose: list[str] = []
    blocks: list[str] = []
    current: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if inside:
                blocks.append("\n".join(current))
                current = []
            inside = not inside
            prose.append("")
            continue
        if inside:
            current.append(line)
        else:
            prose.append(line)
    if current:
        blocks.append("\n".join(current))
    return "\n".join(prose), blocks


def slugify(heading: str) -> str:
    """近似 GitHub 的标题锚点规则；保留 CJK，丢弃标点。"""
    kept = []
    for char in heading.strip().lower():
        if char.isalnum() or char in "-_":
            kept.append(char)
        elif char.isspace():
            kept.append("-")
    return "".join(kept)


def anchors(text: str) -> set[str]:
    prose, _ = split_fences(text)
    found: set[str] = set()
    for match in EXPLICIT_ANCHOR.finditer(prose):
        found.add(match.group(1))
    for _, heading in HEADING.findall(prose):
        base = slugify(heading)
        candidate = base
        index = 1
        while candidate in found:
            candidate = f"{base}-{index}"
            index += 1
        found.add(candidate)
    return found


def read_frontmatter(text: str) -> dict[str, str] | None:
    """最小 frontmatter 读取器：只解析顶层 `key: value`，不引入 YAML 依赖。"""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.md") if ".git" not in path.relative_to(root).parts
    )


def resolve_link(root: Path, bundle: Path, source: Path, target: str) -> Path | None:
    """把链接解析为文件系统路径；外部链接与纯锚点返回 None。"""
    raw = target.strip()
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    raw = raw.split(maxsplit=1)[0]
    if not raw or raw.startswith("#"):
        return None
    if raw.lower().startswith(EXTERNAL_SCHEME):
        return None
    path = raw.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return None
    decoded = path.replace("%20", " ")
    if decoded.startswith("/"):
        return bundle / decoded.lstrip("/")
    return source.parent / decoded


def check_skills(root: Path, errors: list[str]) -> None:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        errors.append(f"{skills_dir}: 缺少 skills 目录")
        return
    for document in sorted(skills_dir.glob("*/SKILL.md")):
        name = document.parent.name
        fields = read_frontmatter(document.read_text(encoding="utf-8"))
        if fields is None:
            errors.append(f"{document}: 缺少可解析的 YAML frontmatter")
            continue
        if fields.get("name") != name:
            errors.append(f"{document}: frontmatter name 必须是目录名 {name!r}")
        if not fields.get("description"):
            errors.append(f"{document}: frontmatter 必须声明 description")


def check_links(root: Path, files: list[Path], errors: list[str]) -> int:
    bundle = root / "context-kg"
    anchor_cache: dict[Path, set[str]] = {}
    checked = 0
    for document in files:
        text = document.read_text(encoding="utf-8")
        prose, _ = split_fences(text)
        relative = document.relative_to(root)
        for match in MARKDOWN_LINK.finditer(prose):
            # 行内代码里的 `[示例](路径)` 是格式说明，不是真实链接。
            before = prose[match.start() - 1] if match.start() else ""
            after = prose[match.end()] if match.end() < len(prose) else ""
            if before == "`" and after == "`":
                continue
            target = match.group(1)
            resolved = resolve_link(root, bundle, document, target)
            if resolved is None:
                continue
            checked += 1
            if not resolved.exists():
                errors.append(f"{relative}: 链接目标不存在：{target}")
                continue
            anchor = target.split("#", 1)[1] if "#" in target else ""
            if not anchor or not resolved.is_file():
                continue
            if resolved not in anchor_cache:
                anchor_cache[resolved] = anchors(resolved.read_text(encoding="utf-8"))
            if anchor not in anchor_cache[resolved]:
                errors.append(f"{relative}: 链接锚点不存在：{target}")
    return checked


def check_markers(files: list[Path], errors: list[str]) -> tuple[int, int, int]:
    """example / gate-example 成对且唯一；片段类 gate 标记只查唯一性。"""
    seen: dict[str, Path] = {}
    pairs: dict[tuple[Path, str], set[str]] = {}
    gate_pairs: dict[tuple[Path, str], set[str]] = {}
    gate_ids: dict[str, Path] = {}
    fragments: dict[str, Path] = {}
    for document in files:
        prose, _ = split_fences(document.read_text(encoding="utf-8"))
        for marker in EXAMPLE.finditer(prose):
            identifier = marker.group(1)
            if identifier in seen:
                errors.append(
                    f"{document}: example ID 重复：{identifier}（另见 {seen[identifier]}）"
                )
                continue
            seen[identifier] = document
            base, _, kind = identifier.rpartition("-")
            if kind not in EXAMPLE_KINDS or not base:
                errors.append(f"{document}: example 必须以 -bad/-good 结尾：{identifier}")
                continue
            pairs.setdefault((document, base), set()).add(kind)
        for marker in GATE_EXAMPLE.finditer(prose):
            identifier = marker.group(1)
            if identifier in gate_ids:
                errors.append(
                    f"{document}: gate-example ID 重复：{identifier}"
                    f"（另见 {gate_ids[identifier]}）"
                )
                continue
            gate_ids[identifier] = document
            base, _, kind = identifier.rpartition("-")
            if kind in EXAMPLE_KINDS and base:
                gate_pairs.setdefault((document, base), set()).add(kind)
        for marker in GATE_FRAGMENT.finditer(prose):
            identifier = marker.group(1)
            if identifier in fragments:
                errors.append(
                    f"{document}: gate-fragment ID 重复：{identifier}"
                    f"（另见 {fragments[identifier]}）"
                )
                continue
            fragments[identifier] = document
    for (document, base), kinds in sorted(pairs.items()):
        if kinds != EXAMPLE_KINDS:
            errors.append(f"{document}: {base} 的 bad/good 未配对：{sorted(kinds)}")
    for (document, base), kinds in sorted(gate_pairs.items()):
        if kinds != EXAMPLE_KINDS:
            errors.append(f"{document}: {base} 的 gate-example 未配对：{sorted(kinds)}")
    loose = len(gate_ids) - sum(len(kinds) for kinds in gate_pairs.values())
    return len(seen), len(gate_pairs), loose + len(fragments)


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f"check_repo: 仓库根目录不存在：{root}", file=sys.stderr)
        return EXIT_UNUSABLE
    errors: list[str] = []
    files = markdown_files(root)
    check_skills(root, errors)
    links = check_links(root, files, errors)
    examples, gate_groups, gate_fragments = check_markers(files, errors)
    print(
        f"检查 Markdown：{len(files)} 份；相对链接 {links} 条；"
        f"example {examples} 个；gate 可执行对 {gate_groups} 组；"
        f"gate 片段/单标记 {gate_fragments} 个"
    )
    for message in errors:
        print(f"✗ {message}")
    if errors:
        print(f"check_repo 失败：{len(errors)} 项")
        return EXIT_INVALID
    print("✓ check_repo 通过")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
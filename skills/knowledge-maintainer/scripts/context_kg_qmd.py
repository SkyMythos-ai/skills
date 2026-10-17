#!/usr/bin/env python3
"""以隔离的 QMD 2.8.3 全文索引检索 OKF context-kg，不调用模型。"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from urllib.parse import unquote, urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - 由宿主 Python 提供
    yaml = None

try:
    from context_kg_search import _freshness, _is_session_summary
except ImportError:  # importlib 加载本脚本时也须可用
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from context_kg_search import _freshness, _is_session_summary

SCHEMA_VERSION = 1
MAX_DOCUMENTS = 10000
ALLOWED_QMD_COMMANDS = {"--version", "update", "search", "cleanup", "status"}
RESERVED = {"index.md", "log.md"}


class RetrievalError(Exception):
    """可向 CLI 用户说明且退出码为 2 的边界错误。"""


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _atomic_write(path: Path, content: str) -> None:
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _git_checkout_root(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _cache_for(root: Path, override: Path | None) -> Path:
    if override is None:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
        cache = base / "knowledge-maintainer" / "qmd" / hashlib.sha256(str(root).encode()).hexdigest()
    else:
        cache = override
    cache = cache.expanduser().resolve()
    checkout = _git_checkout_root(root)
    if (_inside(cache, root) or _inside(root, cache)
            or (checkout and _inside(cache, checkout))
            or _git_checkout_root(cache)):
        raise RetrievalError("缓存目录不得位于 bundle、其祖先或任何 Git checkout 内")
    return cache


class LocalIndex:
    """一个根目录对应一个私有索引；sync/search 调用者必须持有 lock。"""

    def __init__(self, root: Path, cache: Path, qmd: str, timeout: float = 60.0):
        self.root = root.expanduser().resolve()
        self.cache = cache.expanduser().resolve()
        self.qmd = qmd
        self.timeout = timeout
        self.documents = self.cache / "documents"
        self.config = self.cache / "config"
        self.runtime_cache = self.cache / "runtime-cache"
        self.manifest_path = self.cache / "manifest.json"
        self.owner_path = self.cache / "owner.json"
        self.dirty_path = self.cache / "dirty"
        self.db_path = self.runtime_cache / "qmd" / "index.sqlite"

    def prepare(self) -> None:
        """验证私有缓存所有权后才改权限或创建文件；非空无标记目录拒绝接管。"""
        _cache_for(self.root, self.cache)
        existed = self.cache.exists()
        if existed and not self.cache.is_dir():
            raise RetrievalError(f"缓存路径不是目录：{self.cache}")
        if existed and not self.owner_path.is_file() and any(self.cache.iterdir()):
            raise RetrievalError(f"缓存目录非空且无归属标记，拒绝接管：{self.cache}")
        self.cache.mkdir(parents=True, exist_ok=True)
        owner = {"schema_version": SCHEMA_VERSION, "root": str(self.root)}
        if not self.owner_path.exists():
            try:
                with self.owner_path.open("x", encoding="utf-8") as stream:
                    stream.write(_json(owner))
            except FileExistsError:
                pass
        try:
            actual = json.loads(self.owner_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RetrievalError(f"缓存归属标记无效：{exc}") from exc
        if actual != owner:
            raise RetrievalError(f"缓存归属其他 bundle，拒绝使用：{self.cache}")
        self.cache.chmod(0o700)
        self.documents.mkdir(exist_ok=True)
        self.config.mkdir(exist_ok=True)
        self.runtime_cache.mkdir(exist_ok=True)
        (self.cache / "home").mkdir(exist_ok=True)

    @contextlib.contextmanager
    def lock(self, timeout: float = 10.0) -> Iterator[None]:
        """输入超时秒数；独占 sync/search 的扫描、QMD 更新和查询，超时失败且不改索引。"""
        self.prepare()
        with (self.cache / "lock").open("a+b") as stream:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RetrievalError("索引锁等待超时，另一进程正在同步或检索")
                    time.sleep(0.05)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _environment(self) -> dict[str, str]:
        # 只传执行 Node/QMD 所需的普通进程变量；宿主 QMD/模型/云凭据变量不继承。
        allowed = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR"}
        env = {key: value for key, value in os.environ.items() if key in allowed}
        env["HOME"] = str(self.cache / "home")
        env["QMD_CONFIG_DIR"] = str(self.config)
        env["XDG_CONFIG_HOME"] = str(self.cache / "xdg-config")
        env["XDG_CACHE_HOME"] = str(self.runtime_cache)
        env["QMD_FORCE_CPU"] = "1"
        return env

    def run_qmd(self, *args: str) -> str:
        """只运行白名单 QMD 子命令；失败或超时抛错，调用者保留 dirty 标记。"""
        if not args or args[0] not in ALLOWED_QMD_COMMANDS:
            raise RetrievalError("不允许的 QMD 子命令")
        try:
            result = subprocess.run(
                [self.qmd, *args], cwd=self.cache, env=self._environment(),
                capture_output=True, text=True, timeout=self.timeout, check=False,
            )
        except FileNotFoundError as exc:
            raise RetrievalError("未找到 QMD；请安装固定版本 2.8.3，或使用 context_kg_search.py 回退") from exc
        except subprocess.TimeoutExpired as exc:
            raise RetrievalError(f"QMD {args[0]} 超时（{self.timeout:g}s）") from exc
        if result.returncode:
            message = (result.stderr or result.stdout).strip()[:500]
            raise RetrievalError(f"QMD {args[0]} 失败（{result.returncode}）：{message}")
        return result.stdout

    def check_version(self) -> None:
        output = self.run_qmd("--version").strip()
        if not re.match(r"^qmd 2\.8\.3(?:\s|$)", output):
            raise RetrievalError(f"仅支持 QMD 2.8.3，当前：{output[:100]}")

    def load_manifest(self) -> dict[str, Any] | None:
        if not self.manifest_path.is_file():
            return None
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RetrievalError(f"manifest 无法读取：{exc}") from exc
        if (manifest.get("schema_version") != SCHEMA_VERSION
                or manifest.get("root") != str(self.root)
                or not isinstance(manifest.get("files"), dict)):
            raise RetrievalError("manifest 版本或根目录不匹配；请使用新的缓存目录")
        return manifest

    def _config_text(self) -> str:
        # 绝不存在的本地文件使模型能力即使被意外调用也无法下载或连接宿主模型。
        missing = self.cache / "unavailable-models"
        config = {
            "collections": {"knowledge": {"path": str(self.documents), "pattern": "**/*.md"}},
            "models": {key: str(missing / (key + ".gguf")) for key in ("embed", "generate", "rerank")},
        }
        return yaml.safe_dump(config, allow_unicode=True, sort_keys=True)

    def _configure(self) -> None:
        path = self.config / "index.yml"
        desired = self._config_text()
        if not path.is_file() or path.read_text(encoding="utf-8") != desired:
            _atomic_write(path, desired)

    def _scan(self) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
        """全量读取源文件 SHA-256；无效概念记警告并从新 manifest 排除，I/O 故障硬失败。"""
        if not self.root.is_dir() or not (self.root / "index.md").is_file():
            raise RetrievalError(f"bundle 根目录或 index.md 不存在：{self.root}")
        entries: dict[str, dict[str, Any]] = {}
        changed_text: dict[str, str] = {}
        warnings: list[str] = []
        old = self.load_manifest()
        previous = old["files"] if old else {}

        def walk(directory: Path) -> Iterator[Path]:
            try:
                with os.scandir(directory) as scan:
                    listing = sorted(scan, key=lambda item: item.name)
            except OSError as exc:
                raise RetrievalError(f"扫描目录失败：{directory}：{exc}") from exc
            for item in listing:
                try:
                    if item.is_symlink():
                        continue
                    if item.is_dir(follow_symlinks=False):
                        yield from walk(Path(item.path))
                    elif item.is_file(follow_symlinks=False) and item.name.endswith(".md") and item.name not in RESERVED:
                        yield Path(item.path)
                except OSError as exc:
                    raise RetrievalError(f"扫描文件失败：{item.path}：{exc}") from exc

        scanned = 0
        for path in walk(self.root):
            scanned += 1
            if scanned > MAX_DOCUMENTS:
                raise RetrievalError(f"概念数量超过上限 {MAX_DOCUMENTS}")
            relative = path.relative_to(self.root).as_posix()
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise RetrievalError(f"读取文件失败：{relative}：{exc}") from exc
            digest = hashlib.sha256(raw).hexdigest()
            before = previous.get(relative)
            # dirty 表示上次可能已经覆盖镜像却没有提交 manifest；即使源 hash
            # 恢复到旧值，也必须从权威源文件重建投影，不能复用可能属于中间版本的镜像。
            if (not self.dirty_path.exists() and before and before.get("sha256") == digest
                    and self.documents.joinpath(before.get("mirror", "")).is_file()):
                entries[relative] = before
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RetrievalError(f"文件不是 UTF-8：{relative}：{exc}") from exc
            try:
                metadata = self._metadata(content)
            except ValueError as exc:
                warnings.append(f"跳过 {relative}：{exc}")
                continue
            mirror = hashlib.sha256(relative.encode("utf-8")).hexdigest() + ".md"
            entries[relative] = {"sha256": digest, "metadata": metadata, "mirror": mirror}
            changed_text[relative] = content
        return entries, changed_text, warnings

    @staticmethod
    def _metadata(content: str) -> dict[str, Any]:
        # 仅解析时归一换行；源 SHA 和镜像仍保留原始 CRLF/CR 字节语义。
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        if not content:
            raise ValueError("空文件")
        if not content.startswith("---\n"):
            raise ValueError("缺少 YAML frontmatter")
        end = content.find("\n---\n", 4)
        if end < 0:
            raise ValueError("YAML frontmatter 未闭合")
        try:
            metadata = yaml.safe_load(content[4:end])
        except yaml.YAMLError as exc:
            raise ValueError(f"YAML frontmatter 无效：{exc}") from exc
        if not isinstance(metadata, dict) or not isinstance(metadata.get("type"), str) or not metadata["type"].strip():
            raise ValueError("缺少有效 type")
        return json.loads(_json(metadata))

    def sync(self) -> dict[str, Any]:
        """同步源概念到私有镜像；成功发布 manifest，失败保留旧 manifest 和 dirty 以阻止查询。"""
        if yaml is None:
            raise RetrievalError("缺少 PyYAML")
        self.check_version()
        new_files, texts, warnings = self._scan()
        old_manifest = self.load_manifest()
        old_files = old_manifest["files"] if old_manifest else {}
        removed = set(old_files) - set(new_files)
        added = set(new_files) - set(old_files)
        changed = {path for path in new_files.keys() & old_files.keys() if new_files[path]["sha256"] != old_files[path]["sha256"]}
        unchanged = len(new_files) - len(added) - len(changed)
        config_path = self.config / "index.yml"
        config_ready = config_path.is_file() and config_path.read_text(encoding="utf-8") == self._config_text()
        expected_mirrors = {entry["mirror"] for entry in new_files.values()}
        orphan_mirrors = {path for path in self.documents.glob("*.md")
                          if re.fullmatch(r"[a-f0-9]{64}\.md", path.name)
                          and path.name not in expected_mirrors}
        needs_update = bool(added or changed or removed or texts or orphan_mirrors
                            or self.dirty_path.exists()
                            or not self.db_path.is_file() or not old_manifest or not config_ready)
        stats = {"added": len(added), "changed": len(changed), "deleted": len(removed), "unchanged": unchanged, "warnings": warnings}
        if not needs_update:
            return stats
        # dirty 先于镜像/索引改写发布，进程中断或 QMD 失败后下次重做 update。
        _atomic_write(self.dirty_path, datetime.now(timezone.utc).isoformat())
        self._configure()
        for relative, content in texts.items():
            metadata = new_files[relative]["metadata"]
            title = str(metadata.get("title") or Path(relative).stem).replace("\n", " ")
            mirror = self.documents / new_files[relative]["mirror"]
            _atomic_write(mirror, f"# {title}\n\n原始路径: {relative}\n\n{content}")
        for mirror in orphan_mirrors:
            mirror.unlink(missing_ok=True)
        self.run_qmd("update")
        if removed or orphan_mirrors:
            self.run_qmd("cleanup")
        manifest = {"schema_version": SCHEMA_VERSION, "root": str(self.root), "files": new_files,
                    "updated_at": datetime.now(timezone.utc).isoformat()}
        _atomic_write(self.manifest_path, _json(manifest))
        self.dirty_path.unlink()
        return stats

    def _matches(self, query: str) -> list[dict[str, Any]]:
        raw = self.run_qmd("search", query, "--all", "--format", "json", "-c", "knowledge")
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise RetrievalError("QMD search 返回无效 JSON") from exc
        if not isinstance(parsed, list):
            raise RetrievalError("QMD search 返回格式不符合 2.8.3 契约")
        return [row for row in parsed if isinstance(row, dict)]

    @staticmethod
    def _matched_path(row: dict[str, Any], mirror_to_path: dict[str, str]) -> str | None:
        raw = str(row.get("file") or row.get("path") or row.get("uri") or "")
        # qmd://knowledge/<ASCII mirror> 是唯一可信映射；不接受任意原始路径。
        parsed = urlparse(raw)
        if parsed.scheme != "qmd" or parsed.netloc != "knowledge":
            return None
        name = unquote(parsed.path).lstrip("/")
        if not re.fullmatch(r"[a-f0-9]{64}\.md", name):
            return None
        return mirror_to_path.get(name)

    @staticmethod
    def _eligible(path: str, metadata: dict[str, Any], *, scope: str | None,
                  type_filter: str | None, status_filter: str | None, history: bool) -> bool:
        if scope:
            clean_scope = scope.strip("/")
            if any(part in (".", "..") for part in PurePosixPath(clean_scope).parts):
                raise RetrievalError("scope 必须是 bundle 相对路径")
            target = PurePosixPath(clean_scope)
            candidate = PurePosixPath(path)
            if candidate != target and target not in candidate.parents:
                return False
        status = str(metadata.get("status") or "stable").casefold()
        if status_filter and status != status_filter.casefold():
            return False
        if type_filter and str(metadata.get("type", "")).casefold() != type_filter.casefold():
            return False
        if not history and status == "deprecated" and status_filter != "deprecated":
            return False
        if not history and (_is_session_summary(path)
                            or str(metadata.get("type", "")).casefold() == "session summary"):
            return False
        return True

    @staticmethod
    def _snippet(content: str, queries: list[str]) -> tuple[str, int]:
        lines = content.splitlines()
        terms = [term.casefold() for query in queries for term in re.findall(r"\S+", query)]
        for number, line in enumerate(lines, 1):
            folded = line.casefold()
            if any(term in folded for term in terms):
                return line.strip()[:240], number
        return (lines[0].strip()[:240], 1) if lines else ("", 1)

    def search(self, query: str, *, alternatives: list[str] | None = None, limit: int = 5,
               max_chars: int = 12000, scope: str | None = None, type_filter: str | None = None,
               status_filter: str | None = None, history: bool = False) -> dict[str, Any]:
        """全 hash sync 后做 BM25+RRF；只输出实时源文件验证过的受限候选，绝不输出 QMD 正文。"""
        queries = [query.strip()] + [item.strip() for item in (alternatives or [])]
        queries = list(dict.fromkeys(item for item in queries if item))
        if not queries or len(queries) > 4 or any(len(q) > 300 or "\n" in q for q in queries):
            raise RetrievalError("需要 1 条单行查询及最多 3 条单行 alternative，每条不超过 300 字符")
        if not 1 <= limit <= 20 or not 1000 <= max_chars <= 20000:
            raise RetrievalError("limit 必须为 1..20；max-chars 必须为 1000..20000")
        if scope and (scope.startswith("/") or any(part in (".", "..") for part in PurePosixPath(scope).parts)):
            raise RetrievalError("scope 必须是 bundle 相对路径")
        stats = self.sync()
        if self.dirty_path.exists():
            raise RetrievalError("索引未完成同步，不能查询")
        manifest = self.load_manifest()
        files = manifest["files"] if manifest else {}
        mirror_to_path = {entry["mirror"]: path for path, entry in files.items()}
        scores: dict[str, float] = {}
        hits: dict[str, list[str]] = {}
        for q in queries:
            seen: set[str] = set()
            for rank, row in enumerate(self._matches(q), 1):
                path = self._matched_path(row, mirror_to_path)
                if path is None or path in seen:
                    continue
                seen.add(path)
                scores[path] = scores.get(path, 0.0) + 1.0 / (60 + rank)
                hits.setdefault(path, []).append(q)
        # 精确元数据匹配直接纳入，补 QMD 分词对路径/ID/标题可能漏召回的情况。
        for path, entry in files.items():
            title = str(entry["metadata"].get("title") or "")
            exact_fields = (path.casefold(), Path(path).stem.casefold(), title.casefold())
            for q in queries:
                if q.casefold() in exact_fields:
                    scores[path] = scores.get(path, 0.0) + 1.0
                    hits.setdefault(path, []).append(q)
        ordered = sorted(scores, key=lambda path: (-scores[path], path))
        candidates: list[dict[str, Any]] = []
        warnings = list(stats["warnings"])
        now = datetime.now(timezone.utc)
        for path in ordered:
            entry = files[path]
            metadata = entry["metadata"]
            if not self._eligible(path, metadata, scope=scope, type_filter=type_filter,
                                  status_filter=status_filter, history=history):
                continue
            source = self.root / path
            try:
                if source.is_symlink():
                    raise OSError("源文件变为符号链接")
                raw = source.read_bytes()
                if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                    raise OSError("源文件 hash 已变化")
                content = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                warnings.append(f"跳过已变化文件 {path}：{exc}")
                continue
            snippet, line = self._snippet(content, hits[path])
            tags = metadata.get("tags")
            if not isinstance(tags, list):
                tags = []
            item = {"path": path, "title": str(metadata.get("title") or Path(path).stem)[:160],
                    "description": str(metadata.get("description") or "")[:240],
                    "tags": [str(tag)[:60] for tag in tags[:12]],
                    "type": metadata.get("type"), "status": metadata.get("status") or "stable",
                    "freshness": _freshness(metadata, now), "sha256": entry["sha256"],
                    "score": round(scores[path], 6), "matched_queries": list(dict.fromkeys(hits[path])),
                    "snippet": snippet, "start_line": line}
            candidates.append(item)
        result: dict[str, Any] = {"candidates": [], "truncated": False, "warnings": warnings}
        for item in candidates[:limit]:
            proposed = {**result, "candidates": [*result["candidates"], item],
                        "truncated": len(candidates) > len(result["candidates"]) + 1}
            if len(_json(proposed)) > max_chars:
                result["truncated"] = True
                break
            result = proposed
        if len(candidates) > len(result["candidates"]):
            result["truncated"] = True
        while len(_json(result)) > max_chars and result["candidates"]:
            result["candidates"].pop()
            result["truncated"] = True
        if len(_json(result)) > max_chars:
            result["warnings"] = ["警告内容超出输出预算"]
        return result

    def status(self) -> dict[str, Any]:
        """只报告磁盘事实；manifest 与 DB 都存在且无 dirty 才视为可查询。"""
        manifest = self.load_manifest()
        return {"root": str(self.root), "cache_dir": str(self.cache),
                "manifest_present": manifest is not None, "dirty": self.dirty_path.exists(),
                "index_ready": manifest is not None and self.db_path.is_file() and not self.dirty_path.exists(),
                "files": len(manifest["files"]) if manifest else 0,
                "updated_at": manifest.get("updated_at") if manifest else None}


def read_source(root: Path, relative: str, *, start_line: int = 1, lines: int = 60,
                start_column: int = 0, expected_hash: str | None = None,
                max_chars: int = 6000) -> dict[str, Any]:
    """实时读取 root 内非符号链接原文；期望 hash 不同则报错要求重新 search。"""
    root = root.expanduser().resolve()
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
        raise RetrievalError("read 路径必须是 bundle 内相对路径")
    if not 1 <= start_line or start_column < 0 or not 1 <= lines <= 120 or not 1000 <= max_chars <= 20000:
        raise RetrievalError("start-line >=1，start-column >=0，lines 1..120，max-chars 1000..20000")
    source = root / relative
    if any(part.is_symlink() for part in (source, *source.parents) if _inside(part, root)):
        raise RetrievalError("read 不允许符号链接")
    if not _inside(source.resolve(), root):
        raise RetrievalError("read 路径越过 bundle")
    try:
        raw = source.read_bytes()
        content = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RetrievalError(f"read 无法读取文件：{exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if expected_hash and expected_hash != digest:
        raise RetrievalError("源文件 SHA-256 已变化，请重新 search")
    all_lines = content.splitlines(keepends=True)
    if start_line <= len(all_lines) and start_column > len(all_lines[start_line - 1]):
        raise RetrievalError("start-column 超出当前行长度")
    selected = all_lines[start_line - 1:start_line - 1 + lines]
    fragments = [line[start_column:] if number == 0 else line
                 for number, line in enumerate(selected)]
    window = "".join(fragments)

    def build(taken: int) -> dict[str, Any]:
        # 游标由最终放入 JSON 的字符数推导，不能按预裁剪行数推导，否则转义会跳字。
        remaining = taken
        next_line = None
        next_column = None
        line_truncated = False
        for offset, fragment in enumerate(fragments):
            if remaining < len(fragment):
                next_line = start_line + offset
                next_column = (start_column if offset == 0 else 0) + remaining
                line_truncated = remaining > 0
                break
            remaining -= len(fragment)
        else:
            after = start_line + len(fragments)
            if after <= len(all_lines):
                next_line, next_column = after, 0
        return {"path": relative, "start_line": start_line, "start_column": start_column,
                "content": window[:taken], "next_line": next_line,
                "next_column": next_column, "has_more": next_line is not None,
                "line_truncated": line_truncated, "sha256": digest}

    low, high = 0, len(window)
    while low < high:
        middle = (low + high + 1) // 2
        if len(_json(build(middle))) <= max_chars:
            low = middle
        else:
            high = middle - 1
    result = build(low)
    if len(_json(result)) > max_chars or (window and low == 0):
        raise RetrievalError("read 输出预算不足以容纳路径和一个正文字符")
    return result


def _stat_snapshot(root: Path) -> tuple[tuple[str, int, int, int], ...]:
    if not root.is_dir() or not (root / "index.md").is_file():
        raise RetrievalError(f"bundle 根目录或 index.md 不存在：{root}")
    entries: list[tuple[str, int, int, int]] = []
    def on_error(exc: OSError) -> None:
        raise RetrievalError(f"watch 扫描目录失败：{exc}") from exc

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=on_error):
        dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if name.endswith(".md") and not path.is_symlink():
                stat = path.stat()
                entries.append((path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size, stat.st_ino))
    return tuple(sorted(entries))


def watch(index: LocalIndex, *, interval: float = 1.0, debounce: float = 0.4,
          reconcile_seconds: float = 30.0) -> int:
    """前台轮询：stat 变化去抖，周期全 hash；失败保留 dirty/旧 manifest 并重试。"""
    if interval <= 0 or debounce < 0 or reconcile_seconds <= 0:
        raise RetrievalError("watch 时间参数必须为正，debounce 可为 0")
    last_snapshot = None
    changed_at = None
    next_reconcile = 0.0
    try:
        while True:
            now = time.monotonic()
            try:
                snapshot = _stat_snapshot(index.root)
                if last_snapshot != snapshot:
                    last_snapshot = snapshot
                    changed_at = now
                if now >= next_reconcile or (changed_at is not None and now - changed_at >= debounce):
                    with index.lock():
                        result = index.sync()
                    print(_json({"event": "sync", **result}), flush=True)
                    changed_at = None
                    next_reconcile = time.monotonic() + reconcile_seconds
            except (RetrievalError, OSError) as exc:
                print(_json({"event": "error", "error": str(exc)}), flush=True)
                next_reconcile = time.monotonic() + interval
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="隔离的 QMD 2.8.3 本地全文概念检索")
    parser.add_argument("--qmd", default="qmd", help="QMD 2.8.3 可执行文件")
    parser.add_argument("--cache-dir", type=Path, help="bundle 和 Git checkout 外的私有缓存目录")
    parser.add_argument("--timeout", type=float, default=60.0, help="每个 QMD 子进程的秒数上限")
    parser.add_argument("root", type=Path, help="context-kg 根目录")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--alternative", action="append", default=[])
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--max-chars", type=int, default=12000)
    search.add_argument("--scope")
    search.add_argument("--type", dest="type_filter")
    search.add_argument("--status", choices=("draft", "stable", "deprecated"))
    search.add_argument("--history", action="store_true")
    read = commands.add_parser("read")
    read.add_argument("path")
    read.add_argument("--start-line", type=int, default=1)
    read.add_argument("--start-column", type=int, default=0)
    read.add_argument("--lines", type=int, default=60)
    read.add_argument("--expected-hash")
    read.add_argument("--max-chars", type=int, default=6000)
    watching = commands.add_parser("watch")
    watching.add_argument("--interval", type=float, default=1.0)
    watching.add_argument("--debounce", type=float, default=0.4)
    watching.add_argument("--reconcile-seconds", type=float, default=30.0)
    commands.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = args.root.expanduser().resolve()
        if not root.is_dir() or not (root / "index.md").is_file():
            raise RetrievalError(f"bundle 根目录或 index.md 不存在：{root}")
        if args.timeout <= 0:
            raise RetrievalError("timeout 必须大于 0")
        if args.command == "read":
            result = read_source(root, args.path, start_line=args.start_line, lines=args.lines,
                                 start_column=args.start_column, expected_hash=args.expected_hash,
                                 max_chars=args.max_chars)
        else:
            cache = _cache_for(root, args.cache_dir)
            qmd = str(Path(args.qmd).expanduser().absolute()) if "/" in args.qmd else args.qmd
            index = LocalIndex(root, cache, qmd, timeout=args.timeout)
            if args.command == "watch":
                return watch(index, interval=args.interval, debounce=args.debounce,
                             reconcile_seconds=args.reconcile_seconds)
            if args.command == "status":
                result = index.status()
            else:
                with index.lock():
                    if args.command == "sync":
                        result = index.sync()
                    else:
                        result = index.search(args.query, alternatives=args.alternative, limit=args.limit,
                                              max_chars=args.max_chars, scope=args.scope,
                                              type_filter=args.type_filter, status_filter=args.status,
                                              history=args.history)
        print(_json(result))
        return 0
    except (RetrievalError, OSError) as exc:
        print(_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

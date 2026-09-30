#!/usr/bin/env python3
"""探测所选本地工具能否启动；版本匹配仅校验显式 --expect，不执行质量检查。"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


# 版本命令实际执行，避免将 macOS Java 占位程序误判为可用 JDK。
TOOLS = {
    "go": (["go", "version"], r"\bgo(\d+\.\d+[^\s]*)", "准备项目指定的 Go 工具链"),
    "golangci-lint": (["golangci-lint", "version"], r"version v?(\d+\.\d+[^\s]*)", "准备与项目 Go 版本兼容的固定 golangci-lint 版本"),
    "rustc": (["rustc", "--version"], r"rustc (\S+)", "按 rust-toolchain.toml 准备工具链"),
    "cargo": (["cargo", "--version"], r"cargo (\S+)", "按项目工具链准备 Cargo"),
    "rustfmt": (["cargo", "fmt", "--version"], r"rustfmt (\S+)", "为项目工具链安装 rustfmt 组件"),
    "clippy": (["cargo", "clippy", "--version"], r"clippy (\S+)", "为项目工具链安装 clippy 组件"),
    "cargo-audit": (["cargo", "audit", "--version"], r"cargo-audit (\S+)", "按项目策略准备固定 cargo-audit 版本"),
    "java": (["java", "-version"], r'version "([^"]+)"', "准备项目指定 JDK 并配置 JAVA_HOME"),
    "javac": (["javac", "-version"], r"javac (\S+)", "准备完整 JDK，JRE 不包含编译器"),
    "sonar-scanner": (["sonar-scanner", "--version"], r"SonarScanner(?: CLI)? (\S+)", "按项目选择 CLI 或 Maven/Gradle scanner，不重复安装"),
}
LANGUAGES = {
    "go": ["go", "golangci-lint"],
    "rust": ["rustc", "cargo", "rustfmt", "clippy"],
    "java": ["java", "javac"],
}


def probe(name, project, expected, timeout):
    """缺失/启动失败/版本不符 -> 明确状态；成功仅证明版本命令执行成功。"""
    command, pattern, hint = TOOLS[name]
    command = list(command)
    if name in ("java", "javac") and os.environ.get("JAVA_HOME"):
        command[0] = str(Path(os.environ["JAVA_HOME"]) / "bin" / name)
    path = shutil.which(command[0])
    result = {"tool": name, "command": command, "path": path, "expected": expected}
    if path is None:
        return dict(result, status="missing", hint=hint)
    # 使用本次解析出的路径；cwd 保留 rustup 等工具的项目版本选择语义。
    command[0] = path
    try:
        completed = subprocess.run(
            command, cwd=project, capture_output=True, text=True,
            errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return dict(result, status="timeout", hint=hint)
    except OSError as error:
        return dict(result, status="unavailable", detail=str(error), hint=hint)
    output = (completed.stdout + "\n" + completed.stderr).strip()
    match = re.search(pattern, output)
    version = match.group(1) if match else None
    result.update(exit=completed.returncode, version=version, detail=output[:600])
    if completed.returncode != 0:
        return dict(result, status="unavailable", hint=hint)
    if expected is not None and version != expected:
        return dict(result, status="version-mismatch", hint=hint)
    return dict(result, status="available")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="在此项目目录执行版本探测")
    parser.add_argument("--language", choices=LANGUAGES, action="append", default=[], help="可重复；只探测本次涉及的语言")
    parser.add_argument("--require", choices=TOOLS, action="append", default=[], help="额外必需工具，可重复")
    parser.add_argument("--expect", action="append", default=[], metavar="TOOL=VERSION", help="精确版本断言，可重复；未指定不声称版本匹配")
    parser.add_argument("--timeout", type=float, default=15, help="每个版本命令超时秒数")
    args = parser.parse_args()
    if not args.project.is_dir() or not 0 < args.timeout <= 60:
        parser.error("项目目录必须存在，timeout 必须在 (0, 60] 内")
    selected = list(dict.fromkeys([
        name for language in args.language for name in LANGUAGES[language]
    ] + args.require))
    if not selected:
        parser.error("至少选择一个 --language 或 --require")
    expected = {}
    for value in args.expect:
        name, separator, version = value.partition("=")
        if not separator or name not in selected or not version or name in expected:
            parser.error("expect 必须为已选工具的 TOOL=VERSION，且不能重复")
        expected[name] = version
    project = args.project.resolve()
    results = [probe(name, project, expected.get(name), args.timeout) for name in selected]
    success = all(item["status"] == "available" for item in results)
    print(json.dumps({
        "project": str(project),
        "scope": "仅检查选定工具启动与显式版本断言；不代表配置、依赖、源码检查或 Sonar 服务通过",
        "available": success,
        "tools": results,
    }, ensure_ascii=False, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())

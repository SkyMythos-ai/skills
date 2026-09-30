#!/usr/bin/env python3
"""编译规范中的 bad/good 程序，仅执行 good 的行为断言。"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(
    r"<!-- example: ([a-z0-9-]+) -->\s*\n```(go|rust|java)\n(.*?)\n```",
    re.DOTALL,
)


def run(command, cwd=None, timeout=60):
    """保留失败诊断；命令使用参数数组，不经 shell 插值。"""
    return subprocess.run(
        command, cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )


def docker_run(image, work, command):
    """仅挂载当前示例的临时目录；超时后清理自己创建的容器。"""
    name = "coding-case-" + uuid.uuid4().hex
    args = [
        "docker", "run", "--name", name, "--rm", "--pull=never",
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=128", "--memory=512m",
        "--tmpfs", "/tmp:rw,nosuid,size=64m",
        "--mount", f"type=bind,src={work},dst=/work",
        "--workdir", "/work", image, *command,
    ]
    try:
        run(args, timeout=45)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["docker", "rm", "--force", name],
            capture_output=True, timeout=15, check=False,
        )
        raise


def check_toolchain(language, java_image):
    commands = {"go": [["go", "version"]], "rust": [["rustc", "--version"]],
                "java": [["javac", "-version"], ["java", "-version"]]}
    if language == "java" and java_image:
        run(["docker", "image", "inspect", java_image], timeout=10)
        return
    for command in commands[language]:
        if not shutil.which(command[0]):
            raise RuntimeError(f"缺少工具: {command[0]}")
        run(command, timeout=10)


def verify(language, code, kind, work, java_image, race):
    if language == "go":
        source = work / "main.go"
        source.write_text(code + "\n", encoding="utf-8")
        command = ["go", "build"] + (["-race"] if race else [])
        run([*command, "-o", str(work / "example"), str(source)], cwd=work)
        if kind == "good":
            run([str(work / "example")], cwd=work, timeout=10)
    elif language == "rust":
        source = work / "main.rs"
        source.write_text(code + "\n", encoding="utf-8")
        run(["rustc", "--edition=2021", str(source), "-o", str(work / "example")], cwd=work)
        if kind == "good":
            run([str(work / "example")], cwd=work, timeout=10)
    else:
        (work / "Example.java").write_text(code + "\n", encoding="utf-8")
        compile_cmd = ["javac", "-encoding", "UTF-8", "--release", "17", "Example.java"]
        execute_cmd = ["java", "-ea", "-cp", ".", "Example"]
        if java_image:
            docker_run(java_image, work, compile_cmd)
            if kind == "good":
                docker_run(java_image, work, execute_cmd)
        else:
            run(compile_cmd, cwd=work)
            if kind == "good":
                run(execute_cmd, cwd=work, timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=["go", "rust", "java"], action="append")
    parser.add_argument("--java-image", help="使用已在本地的 JDK 容器镜像；不会拉取镜像")
    parser.add_argument("--race", action="store_true", help="Go 程序启用竞争检测")
    options = parser.parse_args()
    languages = options.language or ["go", "rust", "java"]
    failures, skipped, compiled, executed = [], [], 0, 0
    seen = set()
    with tempfile.TemporaryDirectory(prefix="personal-coding-cases-") as directory:
        for language in dict.fromkeys(languages):
            document = ROOT / "references" / f"cases-{language}.md"
            content = document.read_text(encoding="utf-8")
            examples = BLOCK.findall(content)
            marker_count = content.count("<!-- example:")
            if not examples or len(examples) != marker_count:
                raise ValueError(f"{document}: 标记与代码块不匹配")
            pairs = {}
            for identifier, actual_language, _ in examples:
                if identifier in seen or actual_language != language:
                    raise ValueError(f"重复 ID 或语言不符: {identifier}")
                seen.add(identifier)
                base, kind = identifier.rsplit("-", 1)
                if kind not in {"bad", "good"}:
                    raise ValueError(f"未知案例类型: {identifier}")
                pairs.setdefault(base, set()).add(kind)
            if any(kinds != {"bad", "good"} for kinds in pairs.values()):
                raise ValueError(f"{document}: bad/good 未配对")
            try:
                check_toolchain(language, options.java_image)
            except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                skipped.append(language)
                print(f"未验证 {language}: {error}", flush=True)
                continue
            for identifier, _, code in examples:
                work = Path(directory) / identifier
                work.mkdir()
                try:
                    verify(language, code, identifier.rsplit("-", 1)[1], work,
                           options.java_image, options.race)
                    compiled += 1
                    if identifier.endswith("-good"):
                        executed += 1
                    print(f"通过 {identifier}", flush=True)
                except (OSError, subprocess.SubprocessError) as error:
                    failures.append(identifier)
                    print(f"失败 {identifier}: {error}", flush=True)
                    print(getattr(error, "stderr", "") or "", flush=True)
    print(f"编译通过 {compiled}，good 执行通过 {executed}，失败 {len(failures)}，未验证语言 {skipped}")
    return 1 if failures else (2 if skipped else 0)


if __name__ == "__main__":
    raise SystemExit(main())

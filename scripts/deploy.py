"""Shared deployment logic. Only the standard library is needed to bootstrap."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_CHECK = """
import json, sys
from importlib.metadata import version
import dotenv, playwright.sync_api
assert sys.version_info >= (3, 11), 'Python 3.11+ is required'
print(json.dumps({
    'python': sys.version,
    'packages': {name: version(name) for name in
                 ('playwright', 'python-dotenv', 'tzdata', 'pyee', 'greenlet')},
}))
"""
BROWSER_CHECK = """
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
"""
HEADLESS_CONFIG = """
from pathlib import Path
from dotenv import dotenv_values, set_key
from app.accounts import load_accounts

accounts = load_accounts()
files = [Path('.env')]
if accounts:
    files.extend(account.env_file for account in accounts)
for path in dict.fromkeys(files):
    if not path.is_file():
        raise RuntimeError(f'账号环境文件不存在: {path}')
for path in dict.fromkeys(files):
    if dotenv_values(path).get('HEADLESS') != 'true':
        set_key(path, 'HEADLESS', 'true', quote_mode='never')
        print(f'已设置 {path}: HEADLESS=true（隐藏浏览器窗口）。', flush=True)
"""


def execute(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=PROJECT_ROOT, check=True, text=True, encoding="utf-8",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def environment_health(python: Path) -> dict | None:
    try:
        return json.loads(execute([str(python), "-c", HEALTH_CHECK], capture=True).stdout)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def initialize_config() -> None:
    # Exclusive creation preserves existing settings, including empty files.
    for source, destination in ((".env.example", ".env"), ("config.example.json", "config.json")):
        template = (PROJECT_ROOT / source).read_text(encoding="utf-8")
        try:
            with (PROJECT_ROOT / destination).open("x", encoding="utf-8") as output:
                output.write(template)
            print(f"已创建 {destination}，请按需编辑。", flush=True)
        except FileExistsError:
            print(f"保留已有 {destination}。", flush=True)
    (PROJECT_ROOT / "artifacts").mkdir(exist_ok=True)


def prepare(uv: str, refresh: bool = False) -> Path:
    venv = PROJECT_ROOT / ".venv"
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not venv.exists():
        print("[1/4] 创建项目虚拟环境……", flush=True)
        execute([uv, "--no-config", "venv", "--python", sys.executable, str(venv)])
    else:
        # Never silently delete an existing environment or its data.
        try:
            execute([str(python), "-c", "import sys; assert sys.version_info >= (3, 11)"], capture=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("现有 .venv 不可用或 Python 低于 3.11，请先将 .venv 重命名后重试。") from exc
        print("[1/4] 复用已有虚拟环境。", flush=True)

    requirements = PROJECT_ROOT / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = venv / ".deploy-state.json"
    try:
        previous = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    health = environment_health(python)
    state = {"requirements": digest, "environment": health}
    if refresh or not health or previous != state:
        print("[2/4] 使用 uv 安装依赖（复用下载缓存）……", flush=True)
        command = [uv, "--no-config", "pip", "install", "--python", str(python), "-r", str(requirements)]
        if refresh:
            command.append("--upgrade")
        execute(command)
        health = environment_health(python)
        if not health:
            raise RuntimeError("依赖检查失败，请重试；仍失败时将 .venv 重命名后重新部署。")
        state["environment"] = health
    else:
        print("[2/4] 依赖未变化，跳过安装。", flush=True)

    # Playwright checks its own versioned cache, and repairs missing downloads.
    # Install full Chromium as well as the headless shell: login needs a GUI.
    print("[3/4] 检查 Chromium，已有版本直接复用……", flush=True)
    execute([str(python), "-m", "playwright", "install", "chromium"])
    execute([str(python), "-c", BROWSER_CHECK])
    marker.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[4/4] 初始化配置……", flush=True)
    initialize_config()
    # Use the installed interpreter: the bootstrap interpreter may lack dotenv.
    # Persist the setting for direct run.py / scheduled tasks as well as launchers.
    execute([str(python), "-c", HEADLESS_CONFIG])
    return python


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Windows / macOS 一键部署；默认仅准备环境，不发送消息。")
    parser.add_argument("action", nargs="?", default="setup", choices=("setup", "login", "dry-run", "run"))
    parser.add_argument("--refresh", action="store_true", help="重新解析并升级 requirements.txt 允许范围内的依赖")
    parser.add_argument("--uv", default="uv", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    os.environ["PYTHONUTF8"] = "1"
    # Override an inherited HEADLESS=false for one-click dry runs and sending.
    os.environ["HEADLESS"] = "true"
    try:
        python = prepare(args.uv, args.refresh)
        launcher = ".\\deploy.bat" if sys.platform == "win32" else "sh ./deploy.sh"
        if args.action == "setup":
            print(
                "\n部署完成！请先编辑 config.json 中的好友和消息。\n"
                "已启用无头模式，试运行和正式运行不显示浏览器窗口。扫码登录时会显示窗口。\n"
                f"扫码登录：{launcher} login\n"
                f"验证配置：{launcher} dry-run\n"
                f"正式运行：{launcher} run\n"
                "未创建定时任务；每次 run 执行一次。定时运行请参考 docs/quick-deploy.md。",
                flush=True,
            )
            return 0
        if args.action == "login":
            command = [str(python), str(PROJECT_ROOT / "scripts" / "login.py")]
        else:
            command = [str(python), str(PROJECT_ROOT / "run.py")]
            if args.action == "dry-run":
                command.append("--dry-run")
        execute(command)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"\n操作失败（退出码 {exc.returncode}）。请查看上方错误后重试。", file=sys.stderr)
        return exc.returncode if 0 < exc.returncode < 256 else 1
    except (OSError, RuntimeError) as exc:
        print(f"\n部署失败：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

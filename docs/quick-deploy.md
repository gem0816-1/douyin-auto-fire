# Windows / macOS 一键部署

下载并解压项目，或通过 Git clone 获取后，在项目目录执行下面的入口。无需提前安装 Python、Docker、Node.js，也无需管理员权限。首次部署需要联网下载 uv、Python（本机没有合适版本时）、依赖和 Chromium；耗时取决于网络速度。

## Windows

直接双击根目录的 **`deploy.bat`**。也可以在 PowerShell 中运行：

```powershell
.\deploy.bat
```

脚本会在当前进程中使用执行策略参数，不修改系统的 PowerShell 执行策略。支持 Windows PowerShell 5.1，无需安装 PowerShell 7。

## macOS（Apple Silicon / Intel）

打开终端，进入项目目录，执行：

```sh
sh ./deploy.sh
```

若想使用 Finder 双击入口，先运行一次：

```sh
chmod +x deploy.command
```

以后双击 `deploy.command` 即可。ZIP 解压后可能不保留执行权限；上面的 `sh ./deploy.sh` 始终不依赖文件执行权限。系统若拦截下载的脚本，请按 macOS 提示检查来源并允许打开。

## 部署后开始使用

默认入口只准备环境和配置，**不会发送消息，也不会注册定时任务**。

部署按 [Windows 教程](windows.md) 的环境安装、配置、扫码登录、Dry Run 和无头模式流程准备环境。脚本自动将 `.env` 及已启用账号的环境文件设为 `HEADLESS=true`，试运行、正式运行和后续定时执行均隐藏浏览器窗口。扫码登录仍会打开浏览器供本人操作。

1. 编辑 `config.json`，把示例好友和消息替换为自己的配置。
2. 执行 `login`，在打开的浏览器中扫码，登录成功后回到终端按 Enter。
3. 执行 `dry-run`，验证登录状态和好友定位。
4. 确认结果后执行 `run`，发送一次消息。

| 操作 | Windows（PowerShell） | macOS（终端） |
| --- | --- | --- |
| 部署 / 检查环境 | `.\deploy.bat` | `sh ./deploy.sh` |
| 扫码登录 | `.\deploy.bat login` | `sh ./deploy.sh login` |
| 试运行，不发送 | `.\deploy.bat dry-run` | `sh ./deploy.sh dry-run` |
| 正式执行一次 | `.\deploy.bat run` | `sh ./deploy.sh run` |
| 更新允许范围内的依赖 | `.\deploy.bat --refresh` | `sh ./deploy.sh --refresh` |
| 查看帮助 | `.\deploy.bat --help` | `sh ./deploy.sh --help` |

每个命令都会检查环境，不需要手动激活 `.venv`。脚本始终从项目目录运行，支持含空格或中文的路径。已有配置除 `HEADLESS` 外保留，登录凭证不变；缺少的 `.env` 和 `config.json` 从对应 example 文件生成。使用 Cookie 或多账号时，按已有教程配置，跳过单账号 `login`。

## 为什么后续部署更快

- 优先使用已安装的 uv；没有时通过 [uv 官方安装器](https://docs.astral.sh/uv/getting-started/installation/)安装到项目内的 `.tools/uv`，不修改 PATH 或 Shell 配置。
- uv 自动寻找 Python 3.11+，需要时下载 Python，依赖安装使用 uv 缓存。
- 复用 `.venv`。依赖文件和环境中的包版本未变化且导入检查成功时，跳过依赖安装。
- Playwright 复用当前版本的 Chromium 缓存；浏览器缓存被删除时会重新安装。每次部署会启动一个空白的无头浏览器确认可用，不会访问抖音或发送消息。
- 不执行每次都更新 pip、删除虚拟环境或重新下载所有依赖的操作。

修改 `requirements.txt` 后直接再次部署即可。更新项目代码仍需自行 `git pull` 或重新下载；`--refresh` 只升级依赖，不拉取项目代码。未改动且缓存完整时，后续部署可以离线执行；登录和发送仍需要联网。

## 下载加速与排错

默认使用官方源，不强制覆盖你已经设置的代理和下载镜像。网络较慢时，可以按实际网络情况设置 `UV_INDEX_URL`（Python 包源）、`UV_PYTHON_INSTALL_MIRROR`（Python 下载镜像）、`PLAYWRIGHT_DOWNLOAD_HOST`（浏览器下载镜像）或 `HTTPS_PROXY`，再运行入口。只使用自己信任的镜像。uv 本身首次安装需要能访问 `astral.sh` 和 GitHub；也可以提前安装 uv 并加入 PATH。

例如，仅切换 Python 包源：

```powershell
# Windows；把地址换成你可访问的 Python 包源
$env:UV_INDEX_URL = 'https://your-mirror.example/simple'
.\deploy.bat
```

```sh
# macOS
UV_INDEX_URL='https://your-mirror.example/simple' sh ./deploy.sh
```

中途下载失败时直接重跑；脚本返回非零退出码，并保留安装器的原始错误。若原有 `.venv` 损坏、来自其他电脑或 Python 低于 3.11，脚本会停止并提示将它重命名，再重新部署，不会自动删除它。不要在发送任务运行期间升级依赖。

## 每天自动执行

脚本的 `run` 每次只执行一次。Windows 可参考 [任务计划程序配置](windows.md#13-配置-windows-任务计划程序)，使用项目内 `.venv\Scripts\python.exe`，参数 `run.py`，起始目录设为项目根目录。

macOS 可以用用户级 `launchd` 调度 `.venv/bin/python` 执行 `run.py`：`ProgramArguments` 中使用 Python 和脚本的绝对路径，`WorkingDirectory` 设为项目根目录，`StartCalendarInterval` 设置每日时间。定时任务直接调用已部署环境，不必每次检查或安装依赖。电脑需要在任务执行时保持开机、唤醒并联网；建议先手动试运行，再配置定时任务。部署时已设置 `HEADLESS=true`。

登录凭证可能失效，届时需重新扫码或更新 Cookie。已有 Windows、Docker、GitHub Actions 和服务器部署方式仍可继续使用。

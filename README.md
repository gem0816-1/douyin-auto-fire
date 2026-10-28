# 抖音自动续火花

基于 Python 3.11+ 和 Playwright，按配置向抖音好友发送文字、图片或原生表情。支持多好友、多账号、随机消息、防重复发送、钉钉及 Webhook 通知，失败时保存日志、截图和 Trace。

## 本地部署

下载项目后，在项目目录操作：

- **Windows**：双击 `deploy.bat`。
- **macOS**：终端执行 `sh ./deploy.sh`。

脚本自动准备 Python、依赖和 Chromium，复用缓存，并设置 `HEADLESS=true` 隐藏日常运行的浏览器窗口；其余已有配置保留。扫码登录时会显示窗口。默认只部署，不发送消息、不创建定时任务。

部署完成后，先编辑 `config.json` 中的好友和消息，再依次登录、试运行、正式执行：

| 操作 | Windows（PowerShell） | macOS（终端） |
| --- | --- | --- |
| 扫码登录 | `.\deploy.bat login` | `sh ./deploy.sh login` |
| 试运行，不发送 | `.\deploy.bat dry-run` | `sh ./deploy.sh dry-run` |
| 正式执行一次 | `.\deploy.bat run` | `sh ./deploy.sh run` |
| 更新依赖 | `.\deploy.bat --refresh` | `sh ./deploy.sh --refresh` |

详细配置、下载加速和定时运行见 [一键部署教程](docs/quick-deploy.md)。

## 其他部署方式

| 方式 | 适用场景 |
| --- | --- |
| [GitHub Actions](docs/github-actions.md) | 无需电脑常开，配置 Secrets 后定时执行 |
| [Docker](docs/docker.md) | 服务器或 NAS，通过 Docker Cron 定时执行 |
| [Linux 服务器](docs/server.md) | Python + systemd Timer |
| [Windows 手动部署](docs/windows.md) | 手动安装环境、配置任务计划程序 |

## 配置与注意事项

- `config.json` 设置好友和消息[https://douyin-config.pages.dev/]  ，`.env` 设置登录凭证、浏览器模式及通知。示例见 [config.example.json](config.example.json) 和 [.env.example](.env.example)。
- 登录支持扫码生成的 `storage-state.json` 或 Cookie；凭证失效后需重新登录。
- 修改配置后先执行 `dry-run`；同一账号避免同时运行多个发送任务。
- 本地定时执行需要电脑保持开机、唤醒并联网。
- 不要公开 Cookie、Storage State、`.env` 或包含聊天信息的运行产物。

## License

[PolyForm Noncommercial License 1.0.0](LICENSE)。允许个人学习、研究及非商业使用；商业用途须取得授权。
